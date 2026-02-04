"""Tests for demand forecasting service using Prophet."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from src.services.forecast import (
    DEFAULT_FORECAST_WEEKS,
    MIN_TRAINING_DAYS,
    MIN_TRAINING_WEEKS,
    TARGET_MAPE,
    ForecastPoint,
    ForecastResult,
    ModelPerformance,
    calculate_safety_stock,
    create_wine_holidays,
    generate_forecast,
    get_training_data,
    train_forecast_model,
    train_forecast_model_for_sku,
    validate_model,
)


class TestCreateWineHolidays:
    """Tests for the create_wine_holidays function."""

    def test_returns_dataframe(self) -> None:
        """Test that function returns a DataFrame."""
        holidays = create_wine_holidays()
        assert isinstance(holidays, pd.DataFrame)

    def test_has_required_columns(self) -> None:
        """Test that DataFrame has required columns for Prophet."""
        holidays = create_wine_holidays()
        assert "holiday" in holidays.columns
        assert "ds" in holidays.columns
        assert "lower_window" in holidays.columns
        assert "upper_window" in holidays.columns

    def test_includes_nye(self) -> None:
        """Test that NYE holidays are included."""
        holidays = create_wine_holidays()
        nye_holidays = holidays[holidays["holiday"] == "NYE"]
        assert len(nye_holidays) > 0
        # Should have 7-day lead-up for champagne demand
        assert (nye_holidays["lower_window"] == -7).all()
        assert (nye_holidays["upper_window"] == 1).all()

    def test_includes_valentines(self) -> None:
        """Test that Valentine's Day holidays are included."""
        holidays = create_wine_holidays()
        valentines = holidays[holidays["holiday"] == "Valentines"]
        assert len(valentines) > 0
        # Check a specific year's Valentine's Day
        val_2025 = valentines[valentines["ds"].dt.year == 2025]
        assert len(val_2025) == 1
        assert val_2025.iloc[0]["ds"].month == 2
        assert val_2025.iloc[0]["ds"].day == 14

    def test_includes_mothers_day(self) -> None:
        """Test that Mother's Day holidays are included."""
        holidays = create_wine_holidays()
        mothers_day = holidays[holidays["holiday"] == "MothersDay"]
        assert len(mothers_day) > 0
        # Mother's Day should be in May
        assert (mothers_day["ds"].dt.month == 5).all()
        # Should be on a Sunday
        assert (mothers_day["ds"].dt.dayofweek == 6).all()

    def test_includes_thanksgiving(self) -> None:
        """Test that Thanksgiving holidays are included."""
        holidays = create_wine_holidays()
        thanksgiving = holidays[holidays["holiday"] == "Thanksgiving"]
        assert len(thanksgiving) > 0
        # Thanksgiving should be in November
        assert (thanksgiving["ds"].dt.month == 11).all()
        # Should be on a Thursday
        assert (thanksgiving["ds"].dt.dayofweek == 3).all()

    def test_mothers_day_2025_is_correct(self) -> None:
        """Test that Mother's Day 2025 is May 11 (second Sunday)."""
        holidays = create_wine_holidays()
        mothers_day_2025 = holidays[
            (holidays["holiday"] == "MothersDay") &
            (holidays["ds"].dt.year == 2025)
        ]
        assert len(mothers_day_2025) == 1
        assert mothers_day_2025.iloc[0]["ds"].day == 11

    def test_thanksgiving_2025_is_correct(self) -> None:
        """Test that Thanksgiving 2025 is November 27 (fourth Thursday)."""
        holidays = create_wine_holidays()
        thanksgiving_2025 = holidays[
            (holidays["holiday"] == "Thanksgiving") &
            (holidays["ds"].dt.year == 2025)
        ]
        assert len(thanksgiving_2025) == 1
        assert thanksgiving_2025.iloc[0]["ds"].day == 27

    def test_covers_year_range(self) -> None:
        """Test that holidays cover 2020-2030 range."""
        holidays = create_wine_holidays()
        years = holidays["ds"].dt.year.unique()
        assert 2020 in years
        assert 2030 in years


class TestTrainForecastModel:
    """Tests for the train_forecast_model function."""

    def test_requires_ds_column(self) -> None:
        """Test that function requires 'ds' column."""
        df = pd.DataFrame({
            "date": pd.date_range("2022-01-01", periods=730, freq="D"),
            "y": [100] * 730,
        })
        with pytest.raises(ValueError, match="must have 'ds' and 'y' columns"):
            train_forecast_model(df)

    def test_requires_y_column(self) -> None:
        """Test that function requires 'y' column."""
        df = pd.DataFrame({
            "ds": pd.date_range("2022-01-01", periods=730, freq="D"),
            "quantity": [100] * 730,
        })
        with pytest.raises(ValueError, match="must have 'ds' and 'y' columns"):
            train_forecast_model(df)

    def test_requires_minimum_data(self) -> None:
        """Test that function requires minimum training data."""
        # Less than 2 years (104 weeks * 7 days = 728 days)
        df = pd.DataFrame({
            "ds": pd.date_range("2022-01-01", periods=100, freq="D"),
            "y": [100] * 100,
        })
        with pytest.raises(ValueError, match="Insufficient training data"):
            train_forecast_model(df)

    def test_trains_with_minimum_data(self) -> None:
        """Test that function trains with exactly minimum data."""
        df = pd.DataFrame({
            "ds": pd.date_range("2022-01-01", periods=MIN_TRAINING_DAYS, freq="D"),
            "y": [100 + i % 7 for i in range(MIN_TRAINING_DAYS)],
        })
        model = train_forecast_model(df)
        assert model is not None
        # Check model was fitted
        assert hasattr(model, "history")

    def test_uses_multiplicative_seasonality(self) -> None:
        """Test that model uses multiplicative seasonality (critical for champagne)."""
        df = pd.DataFrame({
            "ds": pd.date_range("2022-01-01", periods=MIN_TRAINING_DAYS, freq="D"),
            "y": [100 + i % 7 for i in range(MIN_TRAINING_DAYS)],
        })
        model = train_forecast_model(df)
        assert model.seasonality_mode == "multiplicative"

    def test_uses_linear_growth(self) -> None:
        """Test that model uses linear growth."""
        df = pd.DataFrame({
            "ds": pd.date_range("2022-01-01", periods=MIN_TRAINING_DAYS, freq="D"),
            "y": [100 + i % 7 for i in range(MIN_TRAINING_DAYS)],
        })
        model = train_forecast_model(df)
        assert model.growth == "linear"

    def test_has_yearly_seasonality(self) -> None:
        """Test that model has yearly seasonality enabled."""
        df = pd.DataFrame({
            "ds": pd.date_range("2022-01-01", periods=MIN_TRAINING_DAYS, freq="D"),
            "y": [100 + i % 7 for i in range(MIN_TRAINING_DAYS)],
        })
        model = train_forecast_model(df)
        assert model.yearly_seasonality is True or "yearly" in model.seasonalities

    def test_has_weekly_seasonality(self) -> None:
        """Test that model has weekly seasonality enabled."""
        df = pd.DataFrame({
            "ds": pd.date_range("2022-01-01", periods=MIN_TRAINING_DAYS, freq="D"),
            "y": [100 + i % 7 for i in range(MIN_TRAINING_DAYS)],
        })
        model = train_forecast_model(df)
        assert model.weekly_seasonality is True or "weekly" in model.seasonalities

    def test_uses_wine_holidays_by_default(self) -> None:
        """Test that wine holidays are used by default."""
        df = pd.DataFrame({
            "ds": pd.date_range("2022-01-01", periods=MIN_TRAINING_DAYS, freq="D"),
            "y": [100 + i % 7 for i in range(MIN_TRAINING_DAYS)],
        })
        model = train_forecast_model(df)
        # Prophet stores holidays in the model
        assert model.holidays is not None
        assert "NYE" in model.holidays["holiday"].values

    def test_accepts_custom_holidays(self) -> None:
        """Test that custom holidays can be provided."""
        df = pd.DataFrame({
            "ds": pd.date_range("2022-01-01", periods=MIN_TRAINING_DAYS, freq="D"),
            "y": [100 + i % 7 for i in range(MIN_TRAINING_DAYS)],
        })
        custom_holidays = pd.DataFrame({
            "holiday": ["CustomEvent"],
            "ds": [pd.Timestamp("2023-06-15")],
            "lower_window": [-3],
            "upper_window": [1],
        })
        model = train_forecast_model(df, holidays=custom_holidays)
        assert "CustomEvent" in model.holidays["holiday"].values


class TestGenerateForecast:
    """Tests for the generate_forecast function."""

    @pytest.fixture
    def trained_model(self) -> MagicMock:
        """Create a mock trained Prophet model."""
        model = MagicMock()
        model.interval_width = 0.80

        # Mock make_future_dataframe
        future_dates = pd.date_range(
            start="2024-01-01",
            periods=DEFAULT_FORECAST_WEEKS,
            freq="W",
        )
        model.make_future_dataframe.return_value = pd.DataFrame({"ds": future_dates})

        # Mock predict
        forecast_df = pd.DataFrame({
            "ds": future_dates,
            "yhat": [100.0] * DEFAULT_FORECAST_WEEKS,
            "yhat_lower": [80.0] * DEFAULT_FORECAST_WEEKS,
            "yhat_upper": [120.0] * DEFAULT_FORECAST_WEEKS,
        })
        model.predict.return_value = forecast_df

        return model

    def test_returns_dataframe(self, trained_model: MagicMock) -> None:
        """Test that function returns a DataFrame."""
        result = generate_forecast(trained_model)
        assert isinstance(result, pd.DataFrame)

    def test_returns_correct_columns(self, trained_model: MagicMock) -> None:
        """Test that result has required columns."""
        result = generate_forecast(trained_model)
        assert "ds" in result.columns
        assert "yhat" in result.columns
        assert "yhat_lower" in result.columns
        assert "yhat_upper" in result.columns

    def test_returns_correct_number_of_periods(self, trained_model: MagicMock) -> None:
        """Test that result has correct number of forecast periods."""
        result = generate_forecast(trained_model, periods=26)
        assert len(result) == 26

    def test_uses_weekly_frequency(self, trained_model: MagicMock) -> None:
        """Test that forecast uses weekly frequency."""
        generate_forecast(trained_model)
        trained_model.make_future_dataframe.assert_called_once_with(
            periods=DEFAULT_FORECAST_WEEKS, freq="W"
        )

    def test_updates_interval_width(self, trained_model: MagicMock) -> None:
        """Test that interval width is updated when different."""
        trained_model.interval_width = 0.80
        generate_forecast(trained_model, interval_width=0.95)
        assert trained_model.interval_width == 0.95


class TestForecastPointDataclass:
    """Tests for the ForecastPoint dataclass."""

    def test_create_forecast_point(self) -> None:
        """Test creating a ForecastPoint instance."""
        now = datetime.now(UTC)
        point = ForecastPoint(
            ds=now,
            yhat=100.0,
            yhat_lower=80.0,
            yhat_upper=120.0,
        )
        assert point.ds == now
        assert point.yhat == 100.0
        assert point.yhat_lower == 80.0
        assert point.yhat_upper == 120.0

    def test_forecast_point_immutable(self) -> None:
        """Test that ForecastPoint is immutable."""
        point = ForecastPoint(
            ds=datetime.now(UTC),
            yhat=100.0,
            yhat_lower=80.0,
            yhat_upper=120.0,
        )
        with pytest.raises(AttributeError):
            point.yhat = 200.0  # type: ignore


class TestForecastResultDataclass:
    """Tests for the ForecastResult dataclass."""

    def test_create_forecast_result(self) -> None:
        """Test creating a ForecastResult instance."""
        sku_id = uuid.uuid4()
        now = datetime.now(UTC)
        forecasts = [
            ForecastPoint(ds=now, yhat=100.0, yhat_lower=80.0, yhat_upper=120.0)
        ]
        result = ForecastResult(
            sku="UFBub250",
            sku_id=sku_id,
            forecasts=forecasts,
            model_trained_at=now,
            training_data_start=now.date(),
            training_data_end=now.date(),
            training_data_points=730,
        )
        assert result.sku == "UFBub250"
        assert result.sku_id == sku_id
        assert len(result.forecasts) == 1
        assert result.training_data_points == 730

    def test_forecast_result_immutable(self) -> None:
        """Test that ForecastResult is immutable."""
        sku_id = uuid.uuid4()
        now = datetime.now(UTC)
        result = ForecastResult(
            sku="UFBub250",
            sku_id=sku_id,
            forecasts=[],
            model_trained_at=now,
            training_data_start=now.date(),
            training_data_end=now.date(),
            training_data_points=730,
        )
        with pytest.raises(AttributeError):
            result.sku = "NewSKU"  # type: ignore


class TestModelPerformanceDataclass:
    """Tests for the ModelPerformance dataclass."""

    def test_create_model_performance(self) -> None:
        """Test creating a ModelPerformance instance."""
        perf = ModelPerformance(
            sku="UFBub250",
            mape=0.10,
            rmse=15.5,
            mae=12.3,
            coverage=0.85,
            horizon_days=90,
        )
        assert perf.sku == "UFBub250"
        assert perf.mape == 0.10
        assert perf.rmse == 15.5
        assert perf.mae == 12.3
        assert perf.coverage == 0.85
        assert perf.horizon_days == 90

    def test_model_performance_immutable(self) -> None:
        """Test that ModelPerformance is immutable."""
        perf = ModelPerformance(
            sku="UFBub250",
            mape=0.10,
            rmse=15.5,
            mae=12.3,
            coverage=0.85,
            horizon_days=90,
        )
        with pytest.raises(AttributeError):
            perf.mape = 0.20  # type: ignore


class TestValidateModel:
    """Tests for the validate_model function."""

    def test_returns_model_performance(self) -> None:
        """Test that function returns ModelPerformance."""
        # Create test data
        df = pd.DataFrame({
            "ds": pd.date_range("2022-01-01", periods=MIN_TRAINING_DAYS, freq="D"),
            "y": [100 + i % 7 + (i // 365) * 5 for i in range(MIN_TRAINING_DAYS)],
        })
        model = train_forecast_model(df)

        with (
            patch("src.services.forecast.cross_validation") as mock_cv,
            patch("src.services.forecast.performance_metrics") as mock_pm,
        ):
            # Mock cross_validation result
            mock_cv.return_value = pd.DataFrame({
                "ds": pd.date_range("2024-01-01", periods=10, freq="D"),
                "yhat": [100.0] * 10,
                "y": [102.0] * 10,
            })

            # Mock performance_metrics result
            mock_pm.return_value = pd.DataFrame({
                "mape": [0.08],
                "rmse": [10.0],
                "mae": [8.0],
                "coverage": [0.82],
            })

            perf = validate_model(model, df)

            assert isinstance(perf, ModelPerformance)
            assert perf.mape == 0.08
            assert perf.rmse == 10.0
            assert perf.mae == 8.0
            assert perf.coverage == 0.82


class TestGetTrainingData:
    """Tests for the get_training_data function."""

    @pytest.mark.asyncio
    async def test_returns_dataframe(self) -> None:
        """Test that function returns a DataFrame."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        df = await get_training_data(mock_session, sku_id)

        assert isinstance(df, pd.DataFrame)
        assert "ds" in df.columns
        assert "y" in df.columns

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_data(self) -> None:
        """Test that function returns empty DataFrame when no data."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        df = await get_training_data(mock_session, sku_id)

        assert len(df) == 0

    @pytest.mark.asyncio
    async def test_fills_missing_dates_with_zero(self) -> None:
        """Test that missing dates are filled with zero."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Return data with a gap
        mock_result.all.return_value = [
            (datetime(2024, 1, 1).date(), 100),
            (datetime(2024, 1, 3).date(), 150),  # Jan 2 is missing
        ]
        mock_session.execute.return_value = mock_result

        sku_id = uuid.uuid4()
        df = await get_training_data(mock_session, sku_id)

        # Should have 3 rows (Jan 1, 2, 3)
        assert len(df) == 3
        # Jan 2 should be filled with 0
        jan_2_row = df[df["ds"] == pd.Timestamp("2024-01-02")]
        assert len(jan_2_row) == 1
        assert jan_2_row.iloc[0]["y"] == 0


class TestTrainForecastModelForSku:
    """Tests for the train_forecast_model_for_sku function."""

    @pytest.mark.asyncio
    async def test_raises_on_insufficient_data(self) -> None:
        """Test that function raises error with insufficient data."""
        mock_session = AsyncMock()

        # Mock product query
        mock_product = MagicMock()
        mock_product.sku = "UFBub250"
        mock_product.id = uuid.uuid4()

        product_result = MagicMock()
        product_result.scalar_one.return_value = mock_product

        # Mock training data query - return insufficient data (only 100 days)
        training_result = MagicMock()
        start_date = datetime(2024, 1, 1)
        training_result.all.return_value = [
            ((start_date + pd.Timedelta(days=i)).date(), 100)
            for i in range(100)
        ]

        mock_session.execute.side_effect = [product_result, training_result]

        sku_id = uuid.uuid4()
        with pytest.raises(ValueError, match="Insufficient training data"):
            await train_forecast_model_for_sku(mock_session, sku_id, validate=False)


class TestCalculateSafetyStock:
    """Tests for the calculate_safety_stock function."""

    def test_basic_calculation(self) -> None:
        """Test basic safety stock calculation."""
        forecast = pd.DataFrame({
            "yhat": [100.0, 100.0, 100.0],
            "yhat_upper": [120.0, 120.0, 120.0],
        })
        result = calculate_safety_stock(forecast, service_level=0.80)
        # Safety stock = average of (yhat_upper - yhat) = 20
        assert result == 20.0

    def test_scales_for_95_service_level(self) -> None:
        """Test that safety stock is scaled for 95% service level."""
        forecast = pd.DataFrame({
            "yhat": [100.0, 100.0, 100.0],
            "yhat_upper": [120.0, 120.0, 120.0],
        })

        ss_80 = calculate_safety_stock(forecast, service_level=0.80)
        ss_95 = calculate_safety_stock(forecast, service_level=0.95)

        # 95% should be higher than 80%
        assert ss_95 > ss_80

    def test_returns_zero_for_negative(self) -> None:
        """Test that function returns 0 for negative calculations."""
        # This shouldn't happen in practice, but test the guard
        forecast = pd.DataFrame({
            "yhat": [100.0],
            "yhat_upper": [80.0],  # Lower than yhat (invalid but testing guard)
        })
        result = calculate_safety_stock(forecast, service_level=0.80)
        assert result == 0


class TestConstants:
    """Tests for module constants."""

    def test_min_training_weeks(self) -> None:
        """Test minimum training weeks is 2 years."""
        assert MIN_TRAINING_WEEKS == 104

    def test_min_training_days(self) -> None:
        """Test minimum training days matches weeks."""
        assert MIN_TRAINING_DAYS == MIN_TRAINING_WEEKS * 7

    def test_default_forecast_weeks(self) -> None:
        """Test default forecast horizon is 26 weeks."""
        assert DEFAULT_FORECAST_WEEKS == 26

    def test_target_mape(self) -> None:
        """Test target MAPE is 12%."""
        assert TARGET_MAPE == 0.12


class TestIntegration:
    """Integration tests for the forecasting pipeline."""

    def test_full_training_pipeline(self) -> None:
        """Test training a model with synthetic data."""
        # Create 2+ years of synthetic data with weekly seasonality
        # and a NYE spike pattern
        dates = pd.date_range("2022-01-01", periods=MIN_TRAINING_DAYS, freq="D")
        base_demand = 100

        y_values = []
        for d in dates:
            # Base demand with weekly pattern
            weekly_factor = 1 + 0.2 * (d.dayofweek == 5)  # Higher on Saturdays
            # NYE spike (late December)
            nye_factor = 1 + 3.0 * (d.month == 12 and d.day >= 25)
            # Add some noise
            noise = (hash(str(d)) % 20 - 10) / 100

            y_values.append(base_demand * weekly_factor * nye_factor * (1 + noise))

        df = pd.DataFrame({"ds": dates, "y": y_values})

        # Train model
        model = train_forecast_model(df)
        assert model is not None

        # Generate forecast
        forecast = generate_forecast(model, periods=26)
        assert len(forecast) == 26

        # Check forecast has reasonable values
        assert (forecast["yhat"] > 0).all()
        assert (forecast["yhat_lower"] < forecast["yhat"]).all()
        assert (forecast["yhat_upper"] > forecast["yhat"]).all()

    def test_forecast_captures_seasonality(self) -> None:
        """Test that forecast captures yearly seasonality."""
        # Create data with clear December spike
        dates = pd.date_range("2022-01-01", periods=MIN_TRAINING_DAYS, freq="D")

        y_values = []
        for d in dates:
            if d.month == 12:
                y_values.append(500)  # December spike
            else:
                y_values.append(100)  # Normal demand

        df = pd.DataFrame({"ds": dates, "y": y_values})

        model = train_forecast_model(df)
        forecast = generate_forecast(model, periods=52)  # Full year

        # Convert to DataFrame with dates for analysis
        forecast["month"] = forecast["ds"].dt.month

        # December forecasts should be higher than average
        dec_avg = forecast[forecast["month"] == 12]["yhat"].mean()
        non_dec_avg = forecast[forecast["month"] != 12]["yhat"].mean()

        # December should show elevated demand (multiplicative seasonality)
        assert dec_avg > non_dec_avg * 1.5
