"""Demand forecasting service using Prophet.

This module provides functions for training Prophet forecasting models
and generating demand forecasts for inventory planning.

Key features:
- Prophet model training with multiplicative seasonality (critical for champagne)
- Holiday effects for wine industry (NYE, Valentine's, Mother's Day, Thanksgiving)
- 26-week rolling forecasts with confidence intervals
- Cross-validation for model performance assessment
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import TypeAlias
from uuid import UUID

import pandas as pd
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import InventoryEvent, Product

# Type alias for forecast values that may be None
ForecastValue: TypeAlias = float | None

# Minimum training data requirements (from spec)
MIN_TRAINING_WEEKS = 104  # 2 years
MIN_TRAINING_DAYS = MIN_TRAINING_WEEKS * 7

# Default forecast horizon
DEFAULT_FORECAST_WEEKS = 26

# Target MAPE threshold (from spec)
TARGET_MAPE = 0.12  # 12%


@dataclass(frozen=True)
class ForecastPoint:
    """A single forecast point with confidence intervals.

    Attributes:
        ds: The forecast date
        yhat: Point forecast (predicted value)
        yhat_lower: Lower bound of prediction interval
        yhat_upper: Upper bound of prediction interval
    """
    ds: datetime
    yhat: float
    yhat_lower: float
    yhat_upper: float


@dataclass(frozen=True)
class ForecastResult:
    """Complete forecast result for a SKU.

    Attributes:
        sku: The SKU code
        sku_id: The SKU UUID
        forecasts: List of forecast points (weekly)
        model_trained_at: When the model was trained
        training_data_start: Start date of training data
        training_data_end: End date of training data
        training_data_points: Number of data points used for training
    """
    sku: str
    sku_id: UUID
    forecasts: list[ForecastPoint]
    model_trained_at: datetime
    training_data_start: date
    training_data_end: date
    training_data_points: int


@dataclass(frozen=True)
class ModelPerformance:
    """Model performance metrics from cross-validation.

    Attributes:
        sku: The SKU code
        mape: Mean Absolute Percentage Error
        rmse: Root Mean Square Error
        mae: Mean Absolute Error
        coverage: Prediction interval coverage
        horizon_days: Forecast horizon used for validation
    """
    sku: str
    mape: float
    rmse: float
    mae: float
    coverage: float
    horizon_days: int


def create_wine_holidays() -> pd.DataFrame:
    """Create a holiday calendar for the wine industry.

    This includes holidays that significantly affect wine/champagne sales:
    - New Year's Eve (NYE): 7.5x spike for champagne
    - Valentine's Day: 2-3x spike
    - Mother's Day: Moderate spike
    - Thanksgiving: Pre-holiday purchases

    Returns:
        DataFrame with columns: holiday, ds, lower_window, upper_window
    """
    holidays_list = []

    # Generate holidays for years 2020-2030 to cover training and forecast periods
    for year in range(2020, 2031):
        # New Year's Eve - biggest impact for champagne (7-day lead-up)
        holidays_list.append({
            "holiday": "NYE",
            "ds": pd.Timestamp(year=year, month=12, day=31),
            "lower_window": -7,
            "upper_window": 1,
        })

        # Valentine's Day - 2-3x spike (7-day lead-up)
        holidays_list.append({
            "holiday": "Valentines",
            "ds": pd.Timestamp(year=year, month=2, day=14),
            "lower_window": -7,
            "upper_window": 0,
        })

        # Mother's Day - Second Sunday of May
        may_first = pd.Timestamp(year=year, month=5, day=1)
        # Find the first Sunday
        days_until_sunday = (6 - may_first.weekday()) % 7
        first_sunday = may_first + pd.Timedelta(days=days_until_sunday)
        # Second Sunday
        mothers_day = first_sunday + pd.Timedelta(weeks=1)
        holidays_list.append({
            "holiday": "MothersDay",
            "ds": mothers_day,
            "lower_window": -7,
            "upper_window": 0,
        })

        # Thanksgiving - Fourth Thursday of November
        nov_first = pd.Timestamp(year=year, month=11, day=1)
        # Find the first Thursday
        days_until_thursday = (3 - nov_first.weekday()) % 7
        first_thursday = nov_first + pd.Timedelta(days=days_until_thursday)
        # Fourth Thursday
        thanksgiving = first_thursday + pd.Timedelta(weeks=3)
        holidays_list.append({
            "holiday": "Thanksgiving",
            "ds": thanksgiving,
            "lower_window": -3,
            "upper_window": 0,
        })

    return pd.DataFrame(holidays_list)


def train_forecast_model(
    df: pd.DataFrame,
    holidays: pd.DataFrame | None = None,
) -> Prophet:
    """Train a Prophet model for demand forecasting.

    This function creates and trains a Prophet model configured for
    wine/champagne demand patterns with multiplicative seasonality.

    Args:
        df: Training data with columns 'ds' (date) and 'y' (quantity).
            Must contain at least 2 years (104 weeks) of data.
        holidays: Optional holiday calendar. If not provided, wine industry
            holidays will be used.

    Returns:
        Trained Prophet model ready for forecasting.

    Raises:
        ValueError: If training data has fewer than MIN_TRAINING_DAYS points
            or is missing required columns.

    Example:
        >>> df = pd.DataFrame({
        ...     'ds': pd.date_range('2022-01-01', periods=730, freq='D'),
        ...     'y': [100 + i % 7 for i in range(730)]
        ... })
        >>> model = train_forecast_model(df)
        >>> future = model.make_future_dataframe(periods=26, freq='W')
        >>> forecast = model.predict(future)
    """
    # Validate input data
    if "ds" not in df.columns or "y" not in df.columns:
        raise ValueError("DataFrame must have 'ds' and 'y' columns")

    if len(df) < MIN_TRAINING_DAYS:
        raise ValueError(
            f"Insufficient training data: {len(df)} days provided, "
            f"minimum {MIN_TRAINING_DAYS} days ({MIN_TRAINING_WEEKS} weeks) required"
        )

    # Use wine industry holidays if not provided
    if holidays is None:
        holidays = create_wine_holidays()

    # Create Prophet model with configuration from spec
    model = Prophet(
        growth="linear",
        seasonality_mode="multiplicative",  # Critical for champagne's 7.5x NYE spikes
        changepoint_prior_scale=0.05,
        yearly_seasonality=True,
        weekly_seasonality=True,
        holidays=holidays,
        interval_width=0.80,  # 80% prediction interval by default
    )

    # Add US country holidays for additional context
    model.add_country_holidays(country_name="US")

    # Fit the model
    model.fit(df)

    return model


def generate_forecast(
    model: Prophet,
    periods: int = DEFAULT_FORECAST_WEEKS,
    interval_width: float = 0.80,
) -> pd.DataFrame:
    """Generate a forecast using a trained Prophet model.

    Args:
        model: Trained Prophet model
        periods: Number of weeks to forecast (default: 26)
        interval_width: Width of prediction interval (0.80 for 80%, 0.95 for 95%)

    Returns:
        DataFrame with columns: ds, yhat, yhat_lower, yhat_upper
    """
    # Update interval width if different from model's default
    if interval_width != model.interval_width:
        model.interval_width = interval_width

    # Create future dataframe for weekly forecasts
    future = model.make_future_dataframe(periods=periods, freq="W")

    # Generate predictions
    forecast = model.predict(future)

    # Return only the forecast columns we need
    return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(periods)


def validate_model(
    model: Prophet,
    df: pd.DataFrame,
    horizon_days: int = 90,
    initial_days: int | None = None,
    period_days: int = 30,
) -> ModelPerformance:
    """Validate model performance using cross-validation.

    Performs time-series cross-validation to assess model accuracy.
    Target MAPE is <12% per spec requirements.

    Args:
        model: Trained Prophet model (will be used for parameters only)
        df: Training data used to fit the model
        horizon_days: Forecast horizon for validation (default: 90 days)
        initial_days: Initial training period. If None, uses 70% of data.
        period_days: Spacing between cutoff dates (default: 30 days)

    Returns:
        ModelPerformance with MAPE, RMSE, MAE, and coverage metrics.
    """
    # Set initial period to 70% of data if not specified
    if initial_days is None:
        initial_days = int(len(df) * 0.7)

    # Perform cross-validation
    # Note: Prophet's cross_validation re-fits the model internally
    df_cv = cross_validation(
        model,
        initial=f"{initial_days} days",
        period=f"{period_days} days",
        horizon=f"{horizon_days} days",
    )

    # Calculate performance metrics
    df_metrics = performance_metrics(df_cv)

    # Get the metrics (use the final row which represents the full horizon)
    final_metrics = df_metrics.iloc[-1]

    return ModelPerformance(
        sku="",  # Will be set by caller
        mape=float(final_metrics["mape"]),
        rmse=float(final_metrics["rmse"]),
        mae=float(final_metrics["mae"]),
        coverage=float(final_metrics.get("coverage", 0.0)),
        horizon_days=horizon_days,
    )


async def get_training_data(
    session: AsyncSession,
    sku_id: UUID,
    warehouse_id: UUID | None = None,
    min_date: datetime | None = None,
) -> pd.DataFrame:
    """Fetch historical depletion data for model training.

    Retrieves daily depletion totals from the inventory_events table
    and formats them for Prophet training.

    Args:
        session: Database session
        sku_id: Product SKU UUID
        warehouse_id: Optional warehouse filter
        min_date: Optional minimum date filter

    Returns:
        DataFrame with 'ds' (date) and 'y' (daily depletion quantity)
    """
    # Build query for daily depletion totals
    query = (
        select(
            func.date(InventoryEvent.time).label("ds"),
            func.sum(InventoryEvent.quantity).label("y"),
        )
        .where(InventoryEvent.sku_id == sku_id)
        .where(InventoryEvent.event_type == "depletion")
        .group_by(func.date(InventoryEvent.time))
        .order_by(func.date(InventoryEvent.time))
    )

    if warehouse_id:
        query = query.where(InventoryEvent.warehouse_id == warehouse_id)

    if min_date:
        query = query.where(InventoryEvent.time >= min_date)

    result = await session.execute(query)
    rows = result.all()

    if not rows:
        return pd.DataFrame(columns=["ds", "y"])

    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=["ds", "y"])

    # Ensure ds is datetime type
    df["ds"] = pd.to_datetime(df["ds"])

    # Fill missing dates with zero (no depletions)
    if len(df) > 0:
        date_range = pd.date_range(start=df["ds"].min(), end=df["ds"].max(), freq="D")
        df = df.set_index("ds").reindex(date_range, fill_value=0).reset_index()
        df.columns = ["ds", "y"]

    return df


async def train_forecast_model_for_sku(
    session: AsyncSession,
    sku_id: UUID,
    warehouse_id: UUID | None = None,
    validate: bool = True,
) -> tuple[Prophet, ForecastResult, ModelPerformance | None]:
    """Train a forecast model for a specific SKU.

    This is the main entry point for training a forecast model. It:
    1. Fetches historical depletion data
    2. Validates data sufficiency
    3. Trains the Prophet model
    4. Optionally validates model performance
    5. Generates the initial forecast

    Args:
        session: Database session
        sku_id: Product SKU UUID
        warehouse_id: Optional warehouse filter
        validate: Whether to run cross-validation (default: True)

    Returns:
        Tuple of (trained model, forecast result, optional performance metrics)

    Raises:
        ValueError: If insufficient training data
    """
    # Get product info
    product_query = select(Product).where(Product.id == sku_id)
    result = await session.execute(product_query)
    product = result.scalar_one()

    # Get training data
    df = await get_training_data(session, sku_id, warehouse_id)

    # Validate data sufficiency
    if len(df) < MIN_TRAINING_DAYS:
        raise ValueError(
            f"Insufficient training data for {product.sku}: "
            f"{len(df)} days provided, minimum {MIN_TRAINING_DAYS} days required"
        )

    # Train the model
    model = train_forecast_model(df)

    # Generate forecast
    forecast_df = generate_forecast(model, periods=DEFAULT_FORECAST_WEEKS)

    # Convert to ForecastPoint objects
    forecasts = [
        ForecastPoint(
            ds=row["ds"].to_pydatetime(),
            yhat=float(row["yhat"]),
            yhat_lower=float(row["yhat_lower"]),
            yhat_upper=float(row["yhat_upper"]),
        )
        for _, row in forecast_df.iterrows()
    ]

    now = datetime.utcnow()
    forecast_result = ForecastResult(
        sku=product.sku,
        sku_id=sku_id,
        forecasts=forecasts,
        model_trained_at=now,
        training_data_start=df["ds"].min().date(),
        training_data_end=df["ds"].max().date(),
        training_data_points=len(df),
    )

    # Optionally validate model performance
    performance = None
    if validate:
        perf = validate_model(model, df)
        performance = ModelPerformance(
            sku=product.sku,
            mape=perf.mape,
            rmse=perf.rmse,
            mae=perf.mae,
            coverage=perf.coverage,
            horizon_days=perf.horizon_days,
        )

    return model, forecast_result, performance


def calculate_safety_stock(
    forecast: pd.DataFrame,
    service_level: float = 0.95,
) -> float:
    """Calculate safety stock from forecast intervals.

    Safety stock is the buffer inventory needed to account for
    demand variability. For a given service level, it's derived
    from the prediction interval.

    Args:
        forecast: DataFrame with yhat and yhat_upper columns
        service_level: Target service level (0.95 for 95%)

    Returns:
        Recommended safety stock quantity

    Note:
        Prophet's default interval is 80%. For 95% service level,
        the forecast should be regenerated with interval_width=0.95.
    """
    # Safety stock is the average difference between upper bound and point forecast
    # This represents the demand variability we need to buffer against
    safety_stock: float = float((forecast["yhat_upper"] - forecast["yhat"]).mean())

    # Scale if service level doesn't match the interval width
    # (This is a rough approximation - proper scaling would use z-scores)
    if service_level != 0.80:
        # Approximate z-score ratio for scaling
        z_80 = 1.28  # Z-score for 80% interval
        z_95 = 1.96  # Z-score for 95% interval
        if service_level == 0.95:
            safety_stock *= z_95 / z_80

    return max(0.0, safety_stock)
