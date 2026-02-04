"""Inventory metrics calculation service.

This module provides functions for calculating key inventory metrics:
- DOH_T30: Days on Hand based on trailing 30-day depletion rate
- DOH_T90: Days on Hand based on trailing 90-day depletion rate
- Shipment:Depletion ratios
- Velocity trend ratios
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TypeAlias
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import InventoryEvent, Product

# Type alias for metric values that may be None (e.g., when division by zero)
MetricValue: TypeAlias = float | None


@dataclass(frozen=True)
class DOHMetrics:
    """Days on Hand metrics for a SKU.

    Attributes:
        sku: The SKU code
        sku_id: The SKU UUID
        current_inventory: Current inventory level
        doh_t30: Days on hand based on 30-day depletion rate
        depletion_30d: Total depletions in last 30 days
        daily_rate_30d: Daily depletion rate (depletions / 30)
        calculated_at: Timestamp when metrics were calculated
    """
    sku: str
    sku_id: UUID
    current_inventory: int
    doh_t30: MetricValue
    depletion_30d: int
    daily_rate_30d: MetricValue
    calculated_at: datetime


def calculate_doh_t30(
    current_inventory: int,
    depletion_30d: int,
) -> MetricValue:
    """Calculate Days on Hand based on trailing 30-day depletion rate.

    Formula: DOH_T30 = current_inventory / (depletion_30d / 30)

    This metric tells you how many days of inventory remain if sales
    continue at the trailing 30-day average rate.

    Args:
        current_inventory: Current inventory quantity (units on hand)
        depletion_30d: Total units depleted in the last 30 days

    Returns:
        Days on hand as a float, or None if depletion rate is zero
        (cannot calculate days on hand with no sales)

    Examples:
        >>> calculate_doh_t30(1000, 100)  # 1000 units, 100 sold in 30d
        300.0  # 1000 / (100/30) = 1000 / 3.33 = 300 days

        >>> calculate_doh_t30(1000, 3000)  # 1000 units, 3000 sold in 30d
        10.0  # 1000 / (3000/30) = 1000 / 100 = 10 days

        >>> calculate_doh_t30(1000, 0)  # No sales
        None  # Cannot calculate - division by zero
    """
    if depletion_30d <= 0:
        # Cannot calculate days on hand with zero or negative depletions
        return None

    # Calculate daily depletion rate
    daily_rate = depletion_30d / 30.0

    # Calculate days on hand
    doh = current_inventory / daily_rate

    return doh


def calculate_daily_depletion_rate(
    total_depletion: int,
    days: int,
) -> MetricValue:
    """Calculate daily depletion rate from total depletions.

    Args:
        total_depletion: Total units depleted in the period
        days: Number of days in the period

    Returns:
        Daily depletion rate, or None if days is zero
    """
    if days <= 0:
        return None
    return total_depletion / days


async def get_current_inventory(
    session: AsyncSession,
    sku_id: UUID,
    warehouse_id: UUID | None = None,
) -> int:
    """Get current inventory level for a SKU.

    Calculates current inventory by summing all inventory events:
    - 'snapshot' events represent absolute inventory counts (use latest)
    - 'shipment' events add to inventory
    - 'depletion' events subtract from inventory
    - 'adjustment' events can add or subtract

    Args:
        session: Database session
        sku_id: Product SKU UUID
        warehouse_id: Optional warehouse filter

    Returns:
        Current inventory quantity
    """
    # First, try to get the most recent snapshot
    snapshot_query = (
        select(InventoryEvent.quantity, InventoryEvent.time)
        .where(InventoryEvent.sku_id == sku_id)
        .where(InventoryEvent.event_type == "snapshot")
    )
    if warehouse_id:
        snapshot_query = snapshot_query.where(
            InventoryEvent.warehouse_id == warehouse_id
        )
    snapshot_query = snapshot_query.order_by(InventoryEvent.time.desc()).limit(1)

    result = await session.execute(snapshot_query)
    snapshot_row = result.first()

    if snapshot_row:
        snapshot_quantity, snapshot_time = snapshot_row

        # Get events after the snapshot
        events_query = (
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (InventoryEvent.event_type == "shipment", InventoryEvent.quantity),
                            (InventoryEvent.event_type == "adjustment", InventoryEvent.quantity),
                            (InventoryEvent.event_type == "depletion", -InventoryEvent.quantity),
                            else_=0,
                        )
                    ),
                    0,
                )
            )
            .where(InventoryEvent.sku_id == sku_id)
            .where(InventoryEvent.time > snapshot_time)
            .where(InventoryEvent.event_type != "snapshot")
        )
        if warehouse_id:
            events_query = events_query.where(
                InventoryEvent.warehouse_id == warehouse_id
            )

        result = await session.execute(events_query)
        delta: int = result.scalar() or 0

        return int(snapshot_quantity) + delta

    # No snapshot - sum all events
    all_events_query = (
        select(
            func.coalesce(
                func.sum(
                    case(
                        (InventoryEvent.event_type == "shipment", InventoryEvent.quantity),
                        (InventoryEvent.event_type == "adjustment", InventoryEvent.quantity),
                        (InventoryEvent.event_type == "depletion", -InventoryEvent.quantity),
                        else_=0,
                    )
                ),
                0,
            )
        )
        .where(InventoryEvent.sku_id == sku_id)
    )
    if warehouse_id:
        all_events_query = all_events_query.where(
            InventoryEvent.warehouse_id == warehouse_id
        )

    result = await session.execute(all_events_query)
    return result.scalar() or 0


async def get_depletion_total(
    session: AsyncSession,
    sku_id: UUID,
    days: int,
    warehouse_id: UUID | None = None,
    distributor_id: UUID | None = None,
    as_of: datetime | None = None,
) -> int:
    """Get total depletions for a SKU over a time period.

    Args:
        session: Database session
        sku_id: Product SKU UUID
        days: Number of days to look back
        warehouse_id: Optional warehouse filter
        distributor_id: Optional distributor filter
        as_of: Calculate as of this time (default: now)

    Returns:
        Total depletion quantity
    """
    if as_of is None:
        as_of = datetime.now(UTC)

    start_time = as_of - timedelta(days=days)

    query = (
        select(func.coalesce(func.sum(InventoryEvent.quantity), 0))
        .where(InventoryEvent.sku_id == sku_id)
        .where(InventoryEvent.event_type == "depletion")
        .where(InventoryEvent.time >= start_time)
        .where(InventoryEvent.time <= as_of)
    )

    if warehouse_id:
        query = query.where(InventoryEvent.warehouse_id == warehouse_id)
    if distributor_id:
        query = query.where(InventoryEvent.distributor_id == distributor_id)

    result = await session.execute(query)
    return result.scalar() or 0


async def calculate_doh_t30_for_sku(
    session: AsyncSession,
    sku_id: UUID,
    warehouse_id: UUID | None = None,
    as_of: datetime | None = None,
) -> DOHMetrics:
    """Calculate DOH_T30 metrics for a specific SKU.

    Args:
        session: Database session
        sku_id: Product SKU UUID
        warehouse_id: Optional warehouse filter
        as_of: Calculate as of this time (default: now)

    Returns:
        DOHMetrics with calculated values
    """
    if as_of is None:
        as_of = datetime.now(UTC)

    # Get product info
    product_query = select(Product).where(Product.id == sku_id)
    result = await session.execute(product_query)
    product = result.scalar_one()

    # Get current inventory
    current_inventory = await get_current_inventory(session, sku_id, warehouse_id)

    # Get 30-day depletions
    depletion_30d = await get_depletion_total(
        session, sku_id, days=30, warehouse_id=warehouse_id, as_of=as_of
    )

    # Calculate DOH
    doh_t30 = calculate_doh_t30(current_inventory, depletion_30d)
    daily_rate = calculate_daily_depletion_rate(depletion_30d, 30)

    return DOHMetrics(
        sku=product.sku,
        sku_id=sku_id,
        current_inventory=current_inventory,
        doh_t30=doh_t30,
        depletion_30d=depletion_30d,
        daily_rate_30d=daily_rate,
        calculated_at=as_of,
    )


async def calculate_doh_t30_all_skus(
    session: AsyncSession,
    warehouse_id: UUID | None = None,
    as_of: datetime | None = None,
) -> list[DOHMetrics]:
    """Calculate DOH_T30 metrics for all tracked SKUs.

    Args:
        session: Database session
        warehouse_id: Optional warehouse filter
        as_of: Calculate as of this time (default: now)

    Returns:
        List of DOHMetrics for each SKU
    """
    if as_of is None:
        as_of = datetime.now(UTC)

    # Get all products
    products_query = select(Product).order_by(Product.sku)
    result = await session.execute(products_query)
    products = result.scalars().all()

    metrics = []
    for product in products:
        sku_metrics = await calculate_doh_t30_for_sku(
            session, product.id, warehouse_id, as_of
        )
        metrics.append(sku_metrics)

    return metrics
