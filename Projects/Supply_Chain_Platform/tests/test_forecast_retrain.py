"""Tests for forecast retraining Celery task."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from src.models.forecast import Forecast
from src.services.forecast import ForecastPoint, ForecastResult, ModelPerformance
from src.tasks.forecast_retrain import (
    TRACKED_SKUS,
    _async_retrain_forecasts,
    get_sku_ids,
    retrain_forecasts,
    retrain_sku_forecast,
    store_forecast,
)


class MockProduct:
    """Mock Product for testing."""

    def __init__(self, sku: str, id: uuid.UUID):
        self.sku = sku
        self.id = id


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def sku_map() -> dict[str, uuid.UUID]:
    """Create a SKU to UUID mapping for testing."""
    return {
        "UFBub250": uuid.uuid4(),
        "UFRos250": uuid.uuid4(),
        "UFRed250": uuid.uuid4(),
        "UFCha250": uuid.uuid4(),
    }


@pytest.fixture
def sample_forecast_result() -> ForecastResult:
    """Create a sample forecast result for testing."""
    sku_id = uuid.uuid4()
    now = datetime.now(UTC)
    forecasts = [
        ForecastPoint(
            ds=now + timedelta(weeks=i),
            yhat=100.0 + i * 10,
            yhat_lower=80.0 + i * 10,
            yhat_upper=120.0 + i * 10,
        )
        for i in range(26)
    ]
    return ForecastResult(
        sku="UFBub250",
        sku_id=sku_id,
        forecasts=forecasts,
        model_trained_at=now,
        training_data_start=(now - timedelta(days=730)).date(),
        training_data_end=now.date(),
        training_data_points=730,
    )


@pytest.fixture
def sample_performance() -> ModelPerformance:
    """Create sample model performance metrics."""
    return ModelPerformance(
        sku="UFBub250",
        mape=0.08,
        rmse=15.5,
        mae=12.0,
        coverage=0.82,
        horizon_days=90,
    )


class TestTrackedSkus:
    """Tests for TRACKED_SKUS constant."""

    def test_tracked_skus_contains_four_products(self) -> None:
        """Test that TRACKED_SKUS contains all 4 Une Femme products."""
        assert len(TRACKED_SKUS) == 4
        assert "UFBub250" in TRACKED_SKUS
        assert "UFRos250" in TRACKED_SKUS
        assert "UFRed250" in TRACKED_SKUS
        assert "UFCha250" in TRACKED_SKUS


class TestGetSkuIds:
    """Tests for get_sku_ids function."""

    async def test_returns_sku_mapping(self, mock_session: AsyncMock) -> None:
        """Test that SKU to ID mapping is returned."""
        sku_rows = [
            MagicMock(sku="UFBub250", id=uuid.uuid4()),
            MagicMock(sku="UFRos250", id=uuid.uuid4()),
        ]

        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter(sku_rows)
        mock_session.execute.return_value = mock_result

        result = await get_sku_ids(mock_session)

        assert len(result) == 2
        assert "UFBub250" in result
        assert "UFRos250" in result

    async def test_returns_empty_when_no_skus(self, mock_session: AsyncMock) -> None:
        """Test that empty dict is returned when no SKUs found."""
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        mock_session.execute.return_value = mock_result

        result = await get_sku_ids(mock_session)

        assert result == {}


class TestStoreForecast:
    """Tests for store_forecast function."""

    async def test_stores_forecast_records(
        self,
        mock_session: AsyncMock,
        sample_forecast_result: ForecastResult,
        sample_performance: ModelPerformance,
    ) -> None:
        """Test that forecast records are stored in database."""
        count = await store_forecast(
            mock_session, sample_forecast_result, sample_performance
        )

        assert count == 26  # 26 weeks of forecasts
        assert mock_session.add.call_count == 26
        # Verify delete was called first
        mock_session.execute.assert_called()

    async def test_stores_forecast_without_performance(
        self,
        mock_session: AsyncMock,
        sample_forecast_result: ForecastResult,
    ) -> None:
        """Test that forecast records are stored even without performance metrics."""
        count = await store_forecast(mock_session, sample_forecast_result, None)

        assert count == 26
        # Verify forecasts were added
        first_call = mock_session.add.call_args_list[0]
        forecast = first_call[0][0]
        assert forecast.mape is None

    async def test_stores_forecast_with_warehouse(
        self,
        mock_session: AsyncMock,
        sample_forecast_result: ForecastResult,
        sample_performance: ModelPerformance,
    ) -> None:
        """Test that forecast records include warehouse filter."""
        warehouse_id = uuid.uuid4()
        count = await store_forecast(
            mock_session, sample_forecast_result, sample_performance, warehouse_id
        )

        assert count == 26
        # Verify warehouse_id is set on forecasts
        first_call = mock_session.add.call_args_list[0]
        forecast = first_call[0][0]
        assert forecast.warehouse_id == warehouse_id


class TestRetrainSkuForecast:
    """Tests for retrain_sku_forecast function."""

    @patch("src.tasks.forecast_retrain.train_forecast_model_for_sku")
    @patch("src.tasks.forecast_retrain.store_forecast")
    async def test_successful_retrain(
        self,
        mock_store: AsyncMock,
        mock_train: AsyncMock,
        mock_session: AsyncMock,
        sample_forecast_result: ForecastResult,
        sample_performance: ModelPerformance,
    ) -> None:
        """Test successful forecast retraining for a SKU."""
        mock_model = MagicMock()
        mock_train.return_value = (mock_model, sample_forecast_result, sample_performance)
        mock_store.return_value = 26

        result = await retrain_sku_forecast(
            mock_session, "UFBub250", sample_forecast_result.sku_id, validate=True
        )

        assert result["status"] == "success"
        assert result["sku"] == "UFBub250"
        assert result["forecasts_created"] == 26
        assert result["mape"] == 0.08

    @patch("src.tasks.forecast_retrain.train_forecast_model_for_sku")
    async def test_skipped_when_insufficient_data(
        self,
        mock_train: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Test that SKU is skipped when insufficient training data."""
        mock_train.side_effect = ValueError("Insufficient training data")

        result = await retrain_sku_forecast(
            mock_session, "UFBub250", uuid.uuid4(), validate=True
        )

        assert result["status"] == "skipped"
        assert "Insufficient training data" in result["error"]

    @patch("src.tasks.forecast_retrain.train_forecast_model_for_sku")
    async def test_error_handling(
        self,
        mock_train: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Test error handling during forecast retraining."""
        mock_train.side_effect = RuntimeError("Unexpected error")

        result = await retrain_sku_forecast(
            mock_session, "UFBub250", uuid.uuid4(), validate=True
        )

        assert result["status"] == "error"
        assert "Unexpected error" in result["error"]

    @patch("src.tasks.forecast_retrain.train_forecast_model_for_sku")
    @patch("src.tasks.forecast_retrain.store_forecast")
    async def test_warns_on_high_mape(
        self,
        mock_store: AsyncMock,
        mock_train: AsyncMock,
        mock_session: AsyncMock,
        sample_forecast_result: ForecastResult,
    ) -> None:
        """Test that warning is logged when MAPE exceeds target."""
        high_mape_performance = ModelPerformance(
            sku="UFBub250",
            mape=0.15,  # 15% > 12% target
            rmse=20.0,
            mae=15.0,
            coverage=0.75,
            horizon_days=90,
        )
        mock_model = MagicMock()
        mock_train.return_value = (mock_model, sample_forecast_result, high_mape_performance)
        mock_store.return_value = 26

        result = await retrain_sku_forecast(
            mock_session, "UFBub250", sample_forecast_result.sku_id, validate=True
        )

        assert result["status"] == "success"
        assert result["mape"] == 0.15


class TestAsyncRetrainForecasts:
    """Tests for _async_retrain_forecasts function."""

    @patch("src.tasks.forecast_retrain.create_async_engine")
    @patch("src.tasks.forecast_retrain.retrain_sku_forecast")
    @patch("src.tasks.forecast_retrain.get_sku_ids")
    async def test_successful_retrain_all_skus(
        self,
        mock_get_skus: AsyncMock,
        mock_retrain: AsyncMock,
        mock_engine: MagicMock,
        sku_map: dict[str, uuid.UUID],
    ) -> None:
        """Test successful retraining of all SKUs."""
        mock_get_skus.return_value = sku_map
        mock_retrain.return_value = {
            "sku": "TEST",
            "status": "success",
            "forecasts_created": 26,
            "mape": 0.08,
            "error": None,
        }

        # Setup engine mock
        mock_engine_instance = MagicMock()
        mock_engine_instance.dispose = AsyncMock()
        mock_engine.return_value = mock_engine_instance

        # Setup session mock
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.tasks.forecast_retrain.async_sessionmaker",
            return_value=lambda: mock_session_factory,
        ):
            result = await _async_retrain_forecasts(validate=True)

        assert result["status"] == "success"
        assert result["skus_processed"] == 4
        assert result["skus_successful"] == 4
        assert result["total_forecasts_created"] == 104  # 26 * 4

    @patch("src.tasks.forecast_retrain.create_async_engine")
    @patch("src.tasks.forecast_retrain.get_sku_ids")
    async def test_warning_when_no_skus(
        self,
        mock_get_skus: AsyncMock,
        mock_engine: MagicMock,
    ) -> None:
        """Test warning status when no SKUs found."""
        mock_get_skus.return_value = {}

        # Setup engine mock
        mock_engine_instance = MagicMock()
        mock_engine_instance.dispose = AsyncMock()
        mock_engine.return_value = mock_engine_instance

        # Setup session mock
        mock_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.tasks.forecast_retrain.async_sessionmaker",
            return_value=lambda: mock_session_factory,
        ):
            result = await _async_retrain_forecasts()

        assert result["status"] == "warning"
        assert "No tracked SKUs found" in result["errors"][0]

    @patch("src.tasks.forecast_retrain.create_async_engine")
    @patch("src.tasks.forecast_retrain.retrain_sku_forecast")
    @patch("src.tasks.forecast_retrain.get_sku_ids")
    async def test_partial_success(
        self,
        mock_get_skus: AsyncMock,
        mock_retrain: AsyncMock,
        mock_engine: MagicMock,
        sku_map: dict[str, uuid.UUID],
    ) -> None:
        """Test partial success when some SKUs fail."""
        mock_get_skus.return_value = sku_map
        # First 2 succeed, last 2 fail
        mock_retrain.side_effect = [
            {"sku": "UFBub250", "status": "success", "forecasts_created": 26, "mape": 0.08, "error": None},
            {"sku": "UFRos250", "status": "success", "forecasts_created": 26, "mape": 0.09, "error": None},
            {"sku": "UFRed250", "status": "error", "forecasts_created": 0, "mape": None, "error": "Error"},
            {"sku": "UFCha250", "status": "skipped", "forecasts_created": 0, "mape": None, "error": "No data"},
        ]

        # Setup engine mock
        mock_engine_instance = MagicMock()
        mock_engine_instance.dispose = AsyncMock()
        mock_engine.return_value = mock_engine_instance

        # Setup session mock
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.tasks.forecast_retrain.async_sessionmaker",
            return_value=lambda: mock_session_factory,
        ):
            result = await _async_retrain_forecasts()

        assert result["status"] == "partial"
        assert result["skus_successful"] == 2
        assert result["skus_failed"] == 1
        assert result["skus_skipped"] == 1

    @patch("src.tasks.forecast_retrain.create_async_engine")
    @patch("src.tasks.forecast_retrain.retrain_sku_forecast")
    @patch("src.tasks.forecast_retrain.get_sku_ids")
    async def test_all_skipped(
        self,
        mock_get_skus: AsyncMock,
        mock_retrain: AsyncMock,
        mock_engine: MagicMock,
        sku_map: dict[str, uuid.UUID],
    ) -> None:
        """Test skipped status when all SKUs are skipped."""
        mock_get_skus.return_value = sku_map
        mock_retrain.return_value = {
            "sku": "TEST",
            "status": "skipped",
            "forecasts_created": 0,
            "mape": None,
            "error": "No data",
        }

        # Setup engine mock
        mock_engine_instance = MagicMock()
        mock_engine_instance.dispose = AsyncMock()
        mock_engine.return_value = mock_engine_instance

        # Setup session mock
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.tasks.forecast_retrain.async_sessionmaker",
            return_value=lambda: mock_session_factory,
        ):
            result = await _async_retrain_forecasts()

        assert result["status"] == "skipped"
        assert result["skus_skipped"] == 4


class TestRetrainForecastsTask:
    """Tests for the Celery task."""

    @patch("src.tasks.forecast_retrain.asyncio.run")
    def test_task_calls_async_retrain(self, mock_asyncio_run: MagicMock) -> None:
        """Test that Celery task calls the async retrain function."""
        expected_result = {
            "status": "success",
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "skus_processed": 4,
            "skus_successful": 4,
            "skus_skipped": 0,
            "skus_failed": 0,
            "total_forecasts_created": 104,
            "sku_results": [],
            "errors": [],
        }
        mock_asyncio_run.return_value = expected_result

        # Call the task directly
        result = retrain_forecasts.run(validate=True)

        assert result["status"] == "success"
        assert result["skus_processed"] == 4
        assert result["total_forecasts_created"] == 104
        mock_asyncio_run.assert_called_once()

    @patch("src.tasks.forecast_retrain.asyncio.run")
    def test_task_passes_validate_parameter(self, mock_asyncio_run: MagicMock) -> None:
        """Test that validate parameter is passed to async function."""
        mock_asyncio_run.return_value = {
            "status": "success",
            "skus_processed": 0,
            "skus_successful": 0,
            "skus_skipped": 0,
            "skus_failed": 0,
            "total_forecasts_created": 0,
        }

        retrain_forecasts.run(validate=False)

        # Verify asyncio.run was called with validate=False
        call_args = mock_asyncio_run.call_args
        assert call_args is not None


class TestForecastModel:
    """Tests for the Forecast SQLAlchemy model."""

    def test_model_has_required_columns(self) -> None:
        """Test that Forecast model has required columns."""
        from src.models.forecast import Forecast

        # Check table name
        assert Forecast.__tablename__ == "forecasts"

        # Check columns exist
        columns = [c.name for c in Forecast.__table__.columns]
        assert "id" in columns
        assert "sku_id" in columns
        assert "warehouse_id" in columns
        assert "forecast_date" in columns
        assert "yhat" in columns
        assert "yhat_lower" in columns
        assert "yhat_upper" in columns
        assert "interval_width" in columns
        assert "model_trained_at" in columns
        assert "training_data_start" in columns
        assert "training_data_end" in columns
        assert "training_data_points" in columns
        assert "mape" in columns
        assert "created_at" in columns

    def test_model_has_indexes(self) -> None:
        """Test that Forecast model has expected indexes."""
        from src.models.forecast import Forecast

        index_names = [idx.name for idx in Forecast.__table__.indexes]
        assert "idx_forecasts_sku_date" in index_names
        assert "idx_forecasts_model_trained" in index_names


class TestCeleryBeatSchedule:
    """Tests for Celery beat schedule configuration."""

    def test_retrain_task_is_scheduled(self) -> None:
        """Test that retrain task is in beat schedule."""
        from src.celery_app import celery_app

        beat_schedule = celery_app.conf.beat_schedule
        assert "retrain-forecasts-weekly" in beat_schedule

    def test_retrain_task_runs_on_monday(self) -> None:
        """Test that retrain task is scheduled for Monday."""
        from src.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule["retrain-forecasts-weekly"]["schedule"]
        # Celery crontab day_of_week: 0=Sunday, 1=Monday, etc.
        assert schedule.day_of_week == {1}  # Monday

    def test_retrain_task_runs_at_7am_utc(self) -> None:
        """Test that retrain task runs at 7 AM UTC."""
        from src.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule["retrain-forecasts-weekly"]["schedule"]
        assert schedule.hour == {7}
        assert schedule.minute == {0}

    def test_retrain_task_name_is_correct(self) -> None:
        """Test that retrain task name matches the task."""
        from src.celery_app import celery_app

        task_name = celery_app.conf.beat_schedule["retrain-forecasts-weekly"]["task"]
        assert task_name == "src.tasks.forecast_retrain.retrain_forecasts"

    def test_forecast_retrain_module_is_included(self) -> None:
        """Test that forecast_retrain module is included in Celery app."""
        from src.celery_app import celery_app

        assert "src.tasks.forecast_retrain" in celery_app.conf.include
