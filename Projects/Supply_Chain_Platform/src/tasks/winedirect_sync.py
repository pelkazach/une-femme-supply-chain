"""Celery tasks for syncing WineDirect data to inventory_events."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.celery_app import celery_app
from src.config import settings
from src.database import get_async_database_url
from src.models.inventory_event import InventoryEvent
from src.models.product import Product
from src.models.warehouse import Warehouse
from src.services.winedirect import (
    WineDirectAPIError,
    WineDirectAuthError,
    WineDirectClient,
)

logger = logging.getLogger(__name__)

# Tracked SKUs (the 4 Une Femme products)
TRACKED_SKUS = {"UFBub250", "UFRos250", "UFRed250", "UFCha250"}

# Default warehouse code for WineDirect inventory
DEFAULT_WAREHOUSE_CODE = "WINEDIRECT"


async def get_or_create_warehouse(
    session: AsyncSession, code: str, name: str
) -> uuid.UUID:
    """Get or create a warehouse by code.

    Args:
        session: Database session
        code: Warehouse code
        name: Warehouse name (used if creating)

    Returns:
        The warehouse UUID
    """
    result = await session.execute(select(Warehouse).where(Warehouse.code == code))
    warehouse = result.scalar_one_or_none()

    if warehouse:
        return warehouse.id

    # Create new warehouse
    new_warehouse = Warehouse(code=code, name=name)
    session.add(new_warehouse)
    await session.flush()
    return new_warehouse.id


async def get_sku_id_map(session: AsyncSession) -> dict[str, uuid.UUID]:
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


async def sync_inventory_positions(
    session: AsyncSession,
    client: WineDirectClient,
    sku_map: dict[str, uuid.UUID],
    warehouse_id: uuid.UUID,
    sync_time: datetime,
) -> int:
    """Sync current inventory positions from WineDirect.

    Creates inventory adjustment events to reflect current sellable inventory.

    Args:
        session: Database session
        client: WineDirect API client
        sku_map: SKU to product UUID mapping
        warehouse_id: Default warehouse UUID
        sync_time: Timestamp for the sync events

    Returns:
        Number of events created
    """
    inventory_data = await client.get_sellable_inventory()
    events_created = 0

    for item in inventory_data:
        # Extract SKU from various possible field names
        sku = item.get("sku") or item.get("item_code") or item.get("product_code")
        if not sku or sku not in sku_map:
            continue

        # Extract quantity
        quantity = item.get("quantity") or item.get("qty") or item.get("available", 0)
        if not isinstance(quantity, int | float):
            continue

        # Create inventory snapshot event
        event = InventoryEvent(
            time=sync_time,
            sku_id=sku_map[sku],
            warehouse_id=warehouse_id,
            event_type="snapshot",
            quantity=int(quantity),
        )
        session.add(event)
        events_created += 1

    return events_created


async def sync_depletion_events(
    session: AsyncSession,
    client: WineDirectClient,
    sku_map: dict[str, uuid.UUID],
    warehouse_id: uuid.UUID,
    since: datetime,
) -> int:
    """Sync depletion events from WineDirect.

    Args:
        session: Database session
        client: WineDirect API client
        sku_map: SKU to product UUID mapping
        warehouse_id: Default warehouse UUID
        since: Start time for fetching events

    Returns:
        Number of events created
    """
    depletion_data = await client.get_inventory_out(since=since)
    events_created = 0

    for item in depletion_data:
        # Extract SKU
        sku = item.get("sku") or item.get("item_code") or item.get("product_code")
        if not sku or sku not in sku_map:
            continue

        # Extract quantity (depletions are negative or absolute values)
        quantity = item.get("quantity") or item.get("qty") or 0
        if not isinstance(quantity, int | float):
            continue
        # Ensure quantity is positive for depletion event type
        quantity = abs(int(quantity))

        # Extract timestamp
        timestamp_str = (
            item.get("timestamp")
            or item.get("date")
            or item.get("event_date")
            or item.get("transaction_date")
        )
        if timestamp_str:
            if isinstance(timestamp_str, datetime):
                event_time = timestamp_str
            else:
                # Parse ISO format timestamp
                timestamp_str = timestamp_str.replace("Z", "+00:00")
                event_time = datetime.fromisoformat(timestamp_str)
        else:
            event_time = datetime.now(UTC)

        # Create depletion event
        event = InventoryEvent(
            time=event_time,
            sku_id=sku_map[sku],
            warehouse_id=warehouse_id,
            event_type="depletion",
            quantity=quantity,
        )
        session.add(event)
        events_created += 1

    return events_created


async def _async_sync_winedirect() -> dict[str, Any]:
    """Async implementation of WineDirect sync.

    Returns:
        Dictionary with sync results
    """
    sync_time = datetime.now(UTC)
    since = sync_time - timedelta(hours=24)

    # Create database connection
    engine = create_async_engine(
        get_async_database_url(settings.database_url),
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    results: dict[str, Any] = {
        "status": "success",
        "sync_time": sync_time.isoformat(),
        "inventory_events": 0,
        "depletion_events": 0,
        "errors": [],
    }

    try:
        async with async_session() as session:
            # Get or create default warehouse
            warehouse_id = await get_or_create_warehouse(
                session, DEFAULT_WAREHOUSE_CODE, "WineDirect Warehouse"
            )

            # Get SKU mapping
            sku_map = await get_sku_id_map(session)
            if not sku_map:
                results["status"] = "warning"
                results["errors"].append("No tracked SKUs found in database")
                logger.warning("No tracked SKUs found in database")
                await session.commit()
                return results

            # Sync with WineDirect API
            async with WineDirectClient() as client:
                # Sync inventory positions
                try:
                    inventory_count = await sync_inventory_positions(
                        session, client, sku_map, warehouse_id, sync_time
                    )
                    results["inventory_events"] = inventory_count
                    logger.info("Created %d inventory snapshot events", inventory_count)
                except WineDirectAPIError as e:
                    results["errors"].append(f"Inventory sync failed: {e}")
                    logger.error("Inventory sync failed: %s", e)

                # Sync depletion events
                try:
                    depletion_count = await sync_depletion_events(
                        session, client, sku_map, warehouse_id, since
                    )
                    results["depletion_events"] = depletion_count
                    logger.info("Created %d depletion events", depletion_count)
                except WineDirectAPIError as e:
                    results["errors"].append(f"Depletion sync failed: {e}")
                    logger.error("Depletion sync failed: %s", e)

            await session.commit()

    except WineDirectAuthError as e:
        results["status"] = "error"
        results["errors"].append(f"Authentication failed: {e}")
        logger.error("WineDirect authentication failed: %s", e)
    except Exception as e:
        results["status"] = "error"
        results["errors"].append(f"Unexpected error: {e}")
        logger.exception("Unexpected error during WineDirect sync")
    finally:
        await engine.dispose()

    if results["errors"] and results["status"] == "success":
        results["status"] = "partial"

    return results


@celery_app.task(
    bind=True,
    name="src.tasks.winedirect_sync.sync_winedirect_inventory",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    autoretry_for=(WineDirectAPIError,),
)
def sync_winedirect_inventory(self: Any) -> dict[str, Any]:
    """Celery task to sync WineDirect inventory data.

    This task runs daily and:
    1. Fetches current sellable inventory positions
    2. Fetches depletion events from the last 24 hours
    3. Inserts the data into inventory_events table

    Returns:
        Dictionary with sync results including counts and any errors
    """
    logger.info("Starting WineDirect inventory sync")
    try:
        result = asyncio.run(_async_sync_winedirect())
        logger.info(
            "WineDirect sync completed: %d inventory events, %d depletion events",
            result["inventory_events"],
            result["depletion_events"],
        )
        return result
    except Exception as e:
        logger.exception("WineDirect sync task failed")
        raise self.retry(exc=e) from e
