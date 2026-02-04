"""Celery tasks for retraining Prophet forecast models.

This module provides tasks for:
- Weekly retraining of Prophet models for all SKUs
- Storing forecast results in the database
- Cross-validation and model performance tracking
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.celery_app import celery_app
from src.config import settings
from src.database import get_async_database_url
from src.models.forecast import Forecast
from src.models.product import Product
from src.services.forecast import (
    ForecastResult,
    ModelPerformance,
    train_forecast_model_for_sku,
)

logger = logging.getLogger(__name__)

# Tracked SKUs (the 4 Une Femme products)
TRACKED_SKUS = {"UFBub250", "UFRos250", "UFRed250", "UFCha250"}


async def get_sku_ids(session: AsyncSession) -> dict[str, UUID]:
    """Get mapping of SKU codes to product UUIDs.

    Args:
        session: Database session

    Returns:
        Dictionary mapping SKU code to product UUID
    """
    result = await session.execute(
        select(Product.sku, Product.id).where(Product.sku.in_(TRACKED_SKUS))
    )
    return {row.sku: row.id for row in result}


async def store_forecast(
    session: AsyncSession,
    forecast_result: ForecastResult,
    performance: ModelPerformance | None,
    warehouse_id: UUID | None = None,
) -> int:
    """Store forecast results in the database.

    Deletes existing forecasts for this SKU/warehouse and inserts new ones.

    Args:
        session: Database session
        forecast_result: The forecast result from Prophet
        performance: Model performance metrics (optional)
        warehouse_id: Optional warehouse filter

    Returns:
        Number of forecast records created
    """
    # Delete existing forecasts for this SKU and warehouse
    delete_stmt = delete(Forecast).where(Forecast.sku_id == forecast_result.sku_id)
    if warehouse_id:
        delete_stmt = delete_stmt.where(Forecast.warehouse_id == warehouse_id)
    else:
        delete_stmt = delete_stmt.where(Forecast.warehouse_id.is_(None))

    await session.execute(delete_stmt)

    # Get MAPE from performance if available
    mape = performance.mape if performance else None

    # Convert training data dates to datetime
    training_start = datetime.combine(
        forecast_result.training_data_start, datetime.min.time()
    ).replace(tzinfo=UTC)
    training_end = datetime.combine(
        forecast_result.training_data_end, datetime.min.time()
    ).replace(tzinfo=UTC)

    # Insert new forecast records
    records_created = 0
    for forecast_point in forecast_result.forecasts:
        forecast = Forecast(
            sku_id=forecast_result.sku_id,
            warehouse_id=warehouse_id,
            forecast_date=forecast_point.ds.replace(tzinfo=UTC)
            if forecast_point.ds.tzinfo is None
            else forecast_point.ds,
            yhat=forecast_point.yhat,
            yhat_lower=forecast_point.yhat_lower,
            yhat_upper=forecast_point.yhat_upper,
            interval_width=0.80,  # Default interval width
            model_trained_at=forecast_result.model_trained_at.replace(tzinfo=UTC)
            if forecast_result.model_trained_at.tzinfo is None
            else forecast_result.model_trained_at,
            training_data_start=training_start,
            training_data_end=training_end,
            training_data_points=forecast_result.training_data_points,
            mape=mape,
        )
        session.add(forecast)
        records_created += 1

    return records_created


async def retrain_sku_forecast(
    session: AsyncSession,
    sku: str,
    sku_id: UUID,
    validate: bool = True,
) -> dict[str, Any]:
    """Retrain forecast model for a single SKU.

    Args:
        session: Database session
        sku: SKU code
        sku_id: SKU UUID
        validate: Whether to run cross-validation

    Returns:
        Dictionary with training results
    """
    result: dict[str, Any] = {
        "sku": sku,
        "status": "success",
        "forecasts_created": 0,
        "mape": None,
        "error": None,
    }

    try:
        # Train model and generate forecast
        model, forecast_result, performance = await train_forecast_model_for_sku(
            session, sku_id, warehouse_id=None, validate=validate
        )

        # Store forecasts in database
        records_created = await store_forecast(session, forecast_result, performance)
        result["forecasts_created"] = records_created

        if performance:
            result["mape"] = performance.mape
            if performance.mape > 0.12:
                logger.warning(
                    "SKU %s has MAPE %.2f%% (above 12%% target)",
                    sku,
                    performance.mape * 100,
                )

        logger.info(
            "Trained forecast for %s: %d forecasts, MAPE=%.2f%%",
            sku,
            records_created,
            (performance.mape * 100) if performance else 0,
        )

    except ValueError as e:
        # Insufficient training data or other validation errors
        result["status"] = "skipped"
        result["error"] = str(e)
        logger.warning("Skipped forecast for %s: %s", sku, e)

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.exception("Error training forecast for %s", sku)

    return result


async def _async_retrain_forecasts(
    validate: bool = True,
) -> dict[str, Any]:
    """Async implementation of forecast retraining for all SKUs.

    Args:
        validate: Whether to run cross-validation

    Returns:
        Dictionary with overall results
    """
    start_time = datetime.now(UTC)

    # Create database connection
    engine = create_async_engine(
        get_async_database_url(settings.database_url),
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    results: dict[str, Any] = {
        "status": "success",
        "started_at": start_time.isoformat(),
        "completed_at": None,
        "skus_processed": 0,
        "skus_successful": 0,
        "skus_skipped": 0,
        "skus_failed": 0,
        "total_forecasts_created": 0,
        "sku_results": [],
        "errors": [],
    }

    try:
        async with async_session() as session:
            # Get all tracked SKUs
            sku_map = await get_sku_ids(session)
            if not sku_map:
                results["status"] = "warning"
                results["errors"].append("No tracked SKUs found in database")
                logger.warning("No tracked SKUs found in database")
                return results

            # Retrain model for each SKU
            for sku, sku_id in sku_map.items():
                sku_result = await retrain_sku_forecast(
                    session, sku, sku_id, validate=validate
                )
                results["sku_results"].append(sku_result)
                results["skus_processed"] += 1

                if sku_result["status"] == "success":
                    results["skus_successful"] += 1
                    results["total_forecasts_created"] += sku_result["forecasts_created"]
                elif sku_result["status"] == "skipped":
                    results["skus_skipped"] += 1
                else:
                    results["skus_failed"] += 1
                    if sku_result["error"]:
                        results["errors"].append(
                            f"{sku}: {sku_result['error']}"
                        )

            await session.commit()

    except Exception as e:
        results["status"] = "error"
        results["errors"].append(f"Unexpected error: {e}")
        logger.exception("Unexpected error during forecast retraining")
    finally:
        await engine.dispose()

    results["completed_at"] = datetime.now(UTC).isoformat()

    # Update overall status based on results
    if results["skus_failed"] > 0 and results["skus_successful"] > 0:
        results["status"] = "partial"
    elif results["skus_failed"] > 0 and results["skus_successful"] == 0:
        results["status"] = "error"
    elif results["skus_skipped"] == results["skus_processed"]:
        results["status"] = "skipped"

    return results


@celery_app.task(
    bind=True,
    name="src.tasks.forecast_retrain.retrain_forecasts",
    max_retries=2,
    default_retry_delay=600,  # 10 minutes
)
def retrain_forecasts(
    self: Any,
    validate: bool = True,
) -> dict[str, Any]:
    """Celery task to retrain Prophet forecast models for all SKUs.

    This task runs weekly (every Monday) and:
    1. Fetches historical depletion data for each SKU
    2. Trains a Prophet model with wine industry seasonality
    3. Generates 26-week forecasts with 80% confidence intervals
    4. Stores the forecasts in the database
    5. Optionally runs cross-validation to assess model quality

    Args:
        validate: Whether to run cross-validation (default: True)

    Returns:
        Dictionary with retraining results including counts and any errors
    """
    logger.info("Starting weekly forecast retraining")
    try:
        result = asyncio.run(_async_retrain_forecasts(validate=validate))
        logger.info(
            "Forecast retraining completed: %d SKUs processed, "
            "%d successful, %d skipped, %d failed, %d total forecasts",
            result["skus_processed"],
            result["skus_successful"],
            result["skus_skipped"],
            result["skus_failed"],
            result["total_forecasts_created"],
        )
        return result
    except Exception as e:
        logger.exception("Forecast retraining task failed")
        raise self.retry(exc=e) from e
