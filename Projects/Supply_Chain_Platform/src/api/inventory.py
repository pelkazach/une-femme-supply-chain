"""FastAPI routes for inventory management."""

from datetime import UTC, datetime, timedelta
from enum import IntEnum
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import Product
from src.services.winedirect import (
    WineDirectAPIError,
    WineDirectAuthError,
    WineDirectClient,
)


class VelocityPeriod(IntEnum):
    """Valid lookback periods for velocity reports."""

    DAYS_30 = 30
    DAYS_60 = 60
    DAYS_90 = 90

router = APIRouter(prefix="/inventory", tags=["inventory"])


class InventoryItem(BaseModel):
    """Schema for an inventory position."""

    sku: str
    quantity: int
    pool: str | None = None
    warehouse: str | None = None

    model_config = {"from_attributes": True}


class InventoryResponse(BaseModel):
    """Response schema for sellable inventory endpoint."""

    items: list[InventoryItem]
    total_items: int


@router.get("/sellable", response_model=InventoryResponse)
async def get_sellable_inventory(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InventoryResponse:
    """Fetch current sellable inventory positions from WineDirect.

    Returns inventory positions for all 4 SKUs tracked in the system.
    Data is fetched live from the WineDirect API.

    Returns:
        InventoryResponse: List of inventory items with quantities and locations.

    Raises:
        HTTPException: 401 if WineDirect authentication fails.
        HTTPException: 502 if WineDirect API call fails.
        HTTPException: 503 if WineDirect service is unavailable.
    """
    # Get the list of tracked SKUs from the database
    result = await db.execute(select(Product.sku))
    tracked_skus = {row[0] for row in result.fetchall()}

    try:
        async with WineDirectClient() as client:
            raw_inventory = await client.get_sellable_inventory()
    except WineDirectAuthError as e:
        raise HTTPException(
            status_code=401,
            detail=f"WineDirect authentication failed: {e}",
        ) from e
    except WineDirectAPIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"WineDirect API error: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"WineDirect service unavailable: {e}",
        ) from e

    # Filter inventory to only include tracked SKUs
    items: list[InventoryItem] = []
    for item in raw_inventory:
        sku = item.get("sku") or item.get("item_code") or item.get("product_code")
        if sku and sku in tracked_skus:
            items.append(
                InventoryItem(
                    sku=sku,
                    quantity=item.get("quantity", 0),
                    pool=item.get("pool"),
                    warehouse=item.get("warehouse") or item.get("location"),
                )
            )

    return InventoryResponse(items=items, total_items=len(items))


@router.get("/sellable/{sku}", response_model=InventoryItem)
async def get_sellable_inventory_by_sku(
    sku: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InventoryItem:
    """Fetch sellable inventory position for a specific SKU.

    Args:
        sku: The product SKU to fetch inventory for.

    Returns:
        InventoryItem: Inventory position for the specified SKU.

    Raises:
        HTTPException: 404 if SKU is not tracked in the system.
        HTTPException: 404 if SKU not found in WineDirect inventory.
        HTTPException: 401 if WineDirect authentication fails.
        HTTPException: 502 if WineDirect API call fails.
    """
    # Verify the SKU exists in our system
    result = await db.execute(select(Product).where(Product.sku == sku))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"SKU '{sku}' is not tracked in the system",
        )

    try:
        async with WineDirectClient() as client:
            raw_inventory = await client.get_sellable_inventory()
    except WineDirectAuthError as e:
        raise HTTPException(
            status_code=401,
            detail=f"WineDirect authentication failed: {e}",
        ) from e
    except WineDirectAPIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"WineDirect API error: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"WineDirect service unavailable: {e}",
        ) from e

    # Find the specific SKU in the inventory
    for item in raw_inventory:
        item_sku = item.get("sku") or item.get("item_code") or item.get("product_code")
        if item_sku == sku:
            return InventoryItem(
                sku=sku,
                quantity=item.get("quantity", 0),
                pool=item.get("pool"),
                warehouse=item.get("warehouse") or item.get("location"),
            )

    raise HTTPException(
        status_code=404,
        detail=f"SKU '{sku}' not found in WineDirect inventory",
    )


class DepletionEvent(BaseModel):
    """Schema for a depletion (inventory out) event."""

    sku: str
    quantity: int
    timestamp: datetime
    order_id: str | None = None
    customer: str | None = None
    warehouse: str | None = None

    model_config = {"from_attributes": True}


class DepletionResponse(BaseModel):
    """Response schema for inventory-out endpoint."""

    events: list[DepletionEvent]
    total_events: int
    start_date: datetime
    end_date: datetime


@router.get("/out", response_model=DepletionResponse)
async def get_inventory_out(
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: Annotated[
        datetime | None,
        Query(description="Start date for depletion events (ISO 8601 format)"),
    ] = None,
    end_date: Annotated[
        datetime | None,
        Query(description="End date for depletion events (ISO 8601 format)"),
    ] = None,
) -> DepletionResponse:
    """Fetch depletion events (inventory out) from WineDirect.

    Returns depletion events with timestamps, filtered to tracked SKUs.
    Data is fetched live from the WineDirect API.

    Args:
        start_date: Start of date range. Defaults to 24 hours ago.
        end_date: End of date range. Defaults to now.

    Returns:
        DepletionResponse: List of depletion events with timestamps.

    Raises:
        HTTPException: 401 if WineDirect authentication fails.
        HTTPException: 502 if WineDirect API call fails.
        HTTPException: 503 if WineDirect service is unavailable.
    """
    # Default to last 24 hours if no dates provided
    if end_date is None:
        end_date = datetime.now(UTC)
    if start_date is None:
        start_date = end_date - timedelta(hours=24)

    # Ensure dates are timezone-aware
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=UTC)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=UTC)

    # Get the list of tracked SKUs from the database
    result = await db.execute(select(Product.sku))
    tracked_skus = {row[0] for row in result.fetchall()}

    try:
        async with WineDirectClient() as client:
            raw_events = await client.get_inventory_out(since=start_date, until=end_date)
    except WineDirectAuthError as e:
        raise HTTPException(
            status_code=401,
            detail=f"WineDirect authentication failed: {e}",
        ) from e
    except WineDirectAPIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"WineDirect API error: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"WineDirect service unavailable: {e}",
        ) from e

    # Filter events to only include tracked SKUs and parse timestamps
    events: list[DepletionEvent] = []
    for event in raw_events:
        sku = event.get("sku") or event.get("item_code") or event.get("product_code")
        if sku and sku in tracked_skus:
            # Parse timestamp from various possible field names
            timestamp_str = (
                event.get("timestamp")
                or event.get("date")
                or event.get("event_date")
                or event.get("transaction_date")
            )
            if timestamp_str:
                if isinstance(timestamp_str, datetime):
                    timestamp = timestamp_str
                else:
                    # Parse ISO format string
                    timestamp = datetime.fromisoformat(
                        timestamp_str.replace("Z", "+00:00")
                    )
            else:
                # Use current time if no timestamp provided
                timestamp = datetime.now(UTC)

            events.append(
                DepletionEvent(
                    sku=sku,
                    quantity=event.get("quantity", 0),
                    timestamp=timestamp,
                    order_id=event.get("order_id") or event.get("order_number"),
                    customer=event.get("customer") or event.get("customer_name"),
                    warehouse=event.get("warehouse") or event.get("location"),
                )
            )

    return DepletionResponse(
        events=events,
        total_events=len(events),
        start_date=start_date,
        end_date=end_date,
    )


class SkuVelocity(BaseModel):
    """Schema for a single SKU's velocity metrics."""

    sku: str
    units_per_day: float = Field(description="Average depletion rate in units per day")
    total_units: int = Field(description="Total units depleted in the period")
    period_days: int = Field(description="Lookback period in days")

    model_config = {"from_attributes": True}


class VelocityResponse(BaseModel):
    """Response schema for velocity endpoint."""

    period_days: int = Field(description="Lookback period (30, 60, or 90 days)")
    velocities: list[SkuVelocity] = Field(description="Velocity metrics by SKU")
    total_skus: int = Field(description="Number of SKUs with velocity data")


def parse_velocity_report(
    raw_report: dict[str, Any],
    tracked_skus: set[str],
    period_days: int,
) -> list[SkuVelocity]:
    """Parse velocity report data from WineDirect API response.

    Extracts depletion rates per SKU from the raw API response, handling
    various possible field names and response structures.

    Args:
        raw_report: Raw velocity report from WineDirect API.
        tracked_skus: Set of SKUs tracked in our system.
        period_days: The lookback period (30, 60, or 90 days).

    Returns:
        List of SkuVelocity objects for tracked SKUs.
    """
    velocities: list[SkuVelocity] = []

    # Handle various response structures
    # Could be: {"skus": [...]}, {"data": [...]}, {"items": [...]}, or direct list
    sku_data: list[dict[str, Any]] = []
    if isinstance(raw_report, list):
        sku_data = raw_report
    elif "skus" in raw_report:
        sku_data = raw_report["skus"]
    elif "data" in raw_report:
        sku_data = raw_report["data"]
    elif "items" in raw_report:
        sku_data = raw_report["items"]
    elif "velocities" in raw_report:
        sku_data = raw_report["velocities"]

    for item in sku_data:
        # Extract SKU from various possible field names
        sku = (
            item.get("sku")
            or item.get("item_code")
            or item.get("product_code")
            or item.get("sku_code")
        )
        if not sku or sku not in tracked_skus:
            continue

        # Extract units per day from various possible field names
        units_per_day: float | None = None
        for field in [
            "units_per_day",
            "velocity",
            "rate",
            "depletion_rate",
            "avg_daily_units",
            "daily_rate",
        ]:
            if field in item and item[field] is not None:
                units_per_day = float(item[field])
                break

        # Extract total units from various possible field names
        total_units: int = 0
        for field in [
            "total_units",
            "total_quantity",
            "quantity",
            "units",
            "total_depleted",
        ]:
            if field in item and item[field] is not None:
                total_units = int(item[field])
                break

        # If we have total_units but not units_per_day, calculate it
        if units_per_day is None and total_units > 0:
            units_per_day = total_units / period_days
        # If we have units_per_day but not total_units, calculate it
        elif units_per_day is not None and total_units == 0:
            total_units = int(units_per_day * period_days)
        # If neither is available, skip this SKU
        elif units_per_day is None:
            continue

        velocities.append(
            SkuVelocity(
                sku=sku,
                units_per_day=round(units_per_day, 2),
                total_units=total_units,
                period_days=period_days,
            )
        )

    return velocities


@router.get("/velocity", response_model=VelocityResponse)
async def get_velocity_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    period: Annotated[
        VelocityPeriod,
        Query(description="Lookback period in days (30, 60, or 90)"),
    ] = VelocityPeriod.DAYS_30,
) -> VelocityResponse:
    """Fetch velocity (depletion rate) report from WineDirect.

    Returns daily depletion rates for all tracked SKUs based on the
    specified lookback period (30, 60, or 90 days).

    Args:
        period: Lookback period in days. Must be 30, 60, or 90.

    Returns:
        VelocityResponse: Velocity metrics for tracked SKUs.

    Raises:
        HTTPException: 401 if WineDirect authentication fails.
        HTTPException: 502 if WineDirect API call fails.
        HTTPException: 503 if WineDirect service is unavailable.
    """
    # Get the list of tracked SKUs from the database
    result = await db.execute(select(Product.sku))
    tracked_skus = {row[0] for row in result.fetchall()}

    try:
        async with WineDirectClient() as client:
            raw_report = await client.get_velocity_report(days=period)
    except WineDirectAuthError as e:
        raise HTTPException(
            status_code=401,
            detail=f"WineDirect authentication failed: {e}",
        ) from e
    except WineDirectAPIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"WineDirect API error: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"WineDirect service unavailable: {e}",
        ) from e

    # Parse the velocity report, filtering to tracked SKUs
    velocities = parse_velocity_report(raw_report, tracked_skus, period)

    return VelocityResponse(
        period_days=period,
        velocities=velocities,
        total_skus=len(velocities),
    )


@router.get("/velocity/{sku}", response_model=SkuVelocity)
async def get_velocity_by_sku(
    sku: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    period: Annotated[
        VelocityPeriod,
        Query(description="Lookback period in days (30, 60, or 90)"),
    ] = VelocityPeriod.DAYS_30,
) -> SkuVelocity:
    """Fetch velocity (depletion rate) for a specific SKU.

    Args:
        sku: The product SKU to fetch velocity for.
        period: Lookback period in days. Must be 30, 60, or 90.

    Returns:
        SkuVelocity: Velocity metrics for the specified SKU.

    Raises:
        HTTPException: 404 if SKU is not tracked in the system.
        HTTPException: 404 if SKU not found in velocity report.
        HTTPException: 401 if WineDirect authentication fails.
        HTTPException: 502 if WineDirect API call fails.
    """
    # Verify the SKU exists in our system
    result = await db.execute(select(Product).where(Product.sku == sku))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"SKU '{sku}' is not tracked in the system",
        )

    try:
        async with WineDirectClient() as client:
            raw_report = await client.get_velocity_report(days=period)
    except WineDirectAuthError as e:
        raise HTTPException(
            status_code=401,
            detail=f"WineDirect authentication failed: {e}",
        ) from e
    except WineDirectAPIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"WineDirect API error: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"WineDirect service unavailable: {e}",
        ) from e

    # Parse the velocity report for the specific SKU
    velocities = parse_velocity_report(raw_report, {sku}, period)

    if not velocities:
        raise HTTPException(
            status_code=404,
            detail=f"SKU '{sku}' not found in WineDirect velocity report",
        )

    return velocities[0]
