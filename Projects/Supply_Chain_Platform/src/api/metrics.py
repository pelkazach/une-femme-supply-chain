"""FastAPI routes for inventory metrics."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import Distributor, Product, Warehouse
from src.services.metrics import (
    calculate_doh_t30_all_skus,
    calculate_doh_t30_for_sku,
    calculate_ship_dep_ratio_all_skus,
    calculate_ship_dep_ratio_for_sku,
    calculate_velocity_trend_all_skus,
    calculate_velocity_trend_for_sku,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])


# --- Pydantic Schemas ---


class DOHMetricsResponse(BaseModel):
    """Days on Hand metrics for a SKU."""

    sku: str = Field(description="SKU code")
    sku_id: UUID = Field(description="SKU UUID")
    current_inventory: int = Field(description="Current inventory level")
    doh_t30: float | None = Field(
        description="Days on hand based on 30-day depletion rate (None if no sales)"
    )
    depletion_30d: int = Field(description="Total depletions in last 30 days")
    daily_rate_30d: float | None = Field(
        description="Daily depletion rate (30-day)"
    )
    doh_t90: float | None = Field(
        description="Days on hand based on 90-day depletion rate (None if no sales)"
    )
    depletion_90d: int = Field(description="Total depletions in last 90 days")
    daily_rate_90d: float | None = Field(
        description="Daily depletion rate (90-day)"
    )
    calculated_at: datetime = Field(description="Timestamp when metrics were calculated")

    model_config = {"from_attributes": True}


class ShipDepRatioResponse(BaseModel):
    """Shipment to Depletion ratio metrics for a SKU."""

    sku: str = Field(description="SKU code")
    sku_id: UUID = Field(description="SKU UUID")
    shipment_30d: int = Field(description="Total shipments in last 30 days")
    depletion_30d: int = Field(description="Total depletions in last 30 days")
    ratio_30d: float | None = Field(
        description="A30_Ship:A30_Dep ratio (None if no depletions)"
    )
    shipment_90d: int = Field(description="Total shipments in last 90 days")
    depletion_90d: int = Field(description="Total depletions in last 90 days")
    ratio_90d: float | None = Field(
        description="A90_Ship:A90_Dep ratio (None if no depletions)"
    )
    calculated_at: datetime = Field(description="Timestamp when metrics were calculated")

    model_config = {"from_attributes": True}


class VelocityTrendResponse(BaseModel):
    """Velocity trend metrics for a SKU."""

    sku: str = Field(description="SKU code")
    sku_id: UUID = Field(description="SKU UUID")
    depletion_30d: int = Field(description="Total depletions in last 30 days")
    depletion_90d: int = Field(description="Total depletions in last 90 days")
    daily_rate_30d_dep: float | None = Field(
        description="Daily depletion rate (30-day)"
    )
    daily_rate_90d_dep: float | None = Field(
        description="Daily depletion rate (90-day)"
    )
    velocity_trend_dep: float | None = Field(
        description="A30:A90_Dep ratio (>1 accelerating, <1 decelerating)"
    )
    shipment_30d: int = Field(description="Total shipments in last 30 days")
    shipment_90d: int = Field(description="Total shipments in last 90 days")
    daily_rate_30d_ship: float | None = Field(
        description="Daily shipment rate (30-day)"
    )
    daily_rate_90d_ship: float | None = Field(
        description="Daily shipment rate (90-day)"
    )
    velocity_trend_ship: float | None = Field(
        description="A30:A90_Ship ratio (>1 accelerating, <1 decelerating)"
    )
    calculated_at: datetime = Field(description="Timestamp when metrics were calculated")

    model_config = {"from_attributes": True}


class SKUMetrics(BaseModel):
    """Combined metrics for a single SKU."""

    sku: str = Field(description="SKU code")
    sku_id: UUID = Field(description="SKU UUID")
    doh: DOHMetricsResponse = Field(description="Days on Hand metrics")
    ship_dep_ratio: ShipDepRatioResponse = Field(
        description="Shipment to Depletion ratio metrics"
    )
    velocity_trend: VelocityTrendResponse = Field(
        description="Velocity trend metrics"
    )
    calculated_at: datetime = Field(description="Timestamp when metrics were calculated")


class MetricsResponse(BaseModel):
    """Response schema for all metrics endpoint."""

    skus: list[SKUMetrics] = Field(description="Metrics for each SKU")
    total_skus: int = Field(description="Number of SKUs")
    warehouse_id: UUID | None = Field(
        default=None, description="Warehouse filter applied"
    )
    distributor_id: UUID | None = Field(
        default=None, description="Distributor filter applied"
    )
    calculated_at: datetime = Field(description="Timestamp when metrics were calculated")


# --- Helper Functions ---


async def _resolve_warehouse_id(
    db: AsyncSession,
    warehouse_id: UUID | None,
    warehouse_code: str | None,
) -> UUID | None:
    """Resolve warehouse_id from either ID or code."""
    if warehouse_id:
        return warehouse_id
    if warehouse_code:
        result = await db.execute(
            select(Warehouse).where(Warehouse.code == warehouse_code)
        )
        warehouse = result.scalar_one_or_none()
        if warehouse:
            return warehouse.id
        raise HTTPException(
            status_code=404,
            detail=f"Warehouse with code '{warehouse_code}' not found",
        )
    return None


async def _resolve_distributor_id(
    db: AsyncSession,
    distributor_id: UUID | None,
    distributor_name: str | None,
) -> UUID | None:
    """Resolve distributor_id from either ID or name."""
    if distributor_id:
        return distributor_id
    if distributor_name:
        result = await db.execute(
            select(Distributor).where(Distributor.name == distributor_name)
        )
        distributor = result.scalar_one_or_none()
        if distributor:
            return distributor.id
        raise HTTPException(
            status_code=404,
            detail=f"Distributor with name '{distributor_name}' not found",
        )
    return None


# --- API Endpoints ---


@router.get("", response_model=MetricsResponse)
async def get_metrics(
    db: Annotated[AsyncSession, Depends(get_db)],
    warehouse_id: Annotated[
        UUID | None,
        Query(description="Filter by warehouse UUID"),
    ] = None,
    warehouse_code: Annotated[
        str | None,
        Query(description="Filter by warehouse code (alternative to warehouse_id)"),
    ] = None,
    distributor_id: Annotated[
        UUID | None,
        Query(description="Filter by distributor UUID"),
    ] = None,
    distributor_name: Annotated[
        str | None,
        Query(description="Filter by distributor name (alternative to distributor_id)"),
    ] = None,
) -> MetricsResponse:
    """Get all inventory metrics for all tracked SKUs.

    Returns DOH_T30, DOH_T90, shipment:depletion ratios, and velocity trends
    for all 4 tracked SKUs (UFBub250, UFRos250, UFRed250, UFCha250).

    Supports filtering by warehouse and/or distributor.

    Returns:
        MetricsResponse: All metrics for all SKUs.
    """
    # Resolve warehouse and distributor IDs
    resolved_warehouse_id = await _resolve_warehouse_id(
        db, warehouse_id, warehouse_code
    )
    resolved_distributor_id = await _resolve_distributor_id(
        db, distributor_id, distributor_name
    )

    # Calculate all metrics for all SKUs
    doh_metrics = await calculate_doh_t30_all_skus(
        db, warehouse_id=resolved_warehouse_id
    )
    ship_dep_metrics = await calculate_ship_dep_ratio_all_skus(
        db, warehouse_id=resolved_warehouse_id, distributor_id=resolved_distributor_id
    )
    velocity_metrics = await calculate_velocity_trend_all_skus(
        db, warehouse_id=resolved_warehouse_id, distributor_id=resolved_distributor_id
    )

    # Combine metrics by SKU
    skus: list[SKUMetrics] = []
    for doh, ship_dep, velocity in zip(
        doh_metrics, ship_dep_metrics, velocity_metrics, strict=True
    ):
        skus.append(
            SKUMetrics(
                sku=doh.sku,
                sku_id=doh.sku_id,
                doh=DOHMetricsResponse(
                    sku=doh.sku,
                    sku_id=doh.sku_id,
                    current_inventory=doh.current_inventory,
                    doh_t30=doh.doh_t30,
                    depletion_30d=doh.depletion_30d,
                    daily_rate_30d=doh.daily_rate_30d,
                    doh_t90=doh.doh_t90,
                    depletion_90d=doh.depletion_90d,
                    daily_rate_90d=doh.daily_rate_90d,
                    calculated_at=doh.calculated_at,
                ),
                ship_dep_ratio=ShipDepRatioResponse(
                    sku=ship_dep.sku,
                    sku_id=ship_dep.sku_id,
                    shipment_30d=ship_dep.shipment_30d,
                    depletion_30d=ship_dep.depletion_30d,
                    ratio_30d=ship_dep.ratio_30d,
                    shipment_90d=ship_dep.shipment_90d,
                    depletion_90d=ship_dep.depletion_90d,
                    ratio_90d=ship_dep.ratio_90d,
                    calculated_at=ship_dep.calculated_at,
                ),
                velocity_trend=VelocityTrendResponse(
                    sku=velocity.sku,
                    sku_id=velocity.sku_id,
                    depletion_30d=velocity.depletion_30d,
                    depletion_90d=velocity.depletion_90d,
                    daily_rate_30d_dep=velocity.daily_rate_30d_dep,
                    daily_rate_90d_dep=velocity.daily_rate_90d_dep,
                    velocity_trend_dep=velocity.velocity_trend_dep,
                    shipment_30d=velocity.shipment_30d,
                    shipment_90d=velocity.shipment_90d,
                    daily_rate_30d_ship=velocity.daily_rate_30d_ship,
                    daily_rate_90d_ship=velocity.daily_rate_90d_ship,
                    velocity_trend_ship=velocity.velocity_trend_ship,
                    calculated_at=velocity.calculated_at,
                ),
                calculated_at=doh.calculated_at,
            )
        )

    # Use the first SKU's calculated_at for the response timestamp
    calculated_at = skus[0].calculated_at if skus else datetime.now()

    return MetricsResponse(
        skus=skus,
        total_skus=len(skus),
        warehouse_id=resolved_warehouse_id,
        distributor_id=resolved_distributor_id,
        calculated_at=calculated_at,
    )


@router.get("/{sku}", response_model=SKUMetrics)
async def get_metrics_by_sku(
    sku: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    warehouse_id: Annotated[
        UUID | None,
        Query(description="Filter by warehouse UUID"),
    ] = None,
    warehouse_code: Annotated[
        str | None,
        Query(description="Filter by warehouse code (alternative to warehouse_id)"),
    ] = None,
    distributor_id: Annotated[
        UUID | None,
        Query(description="Filter by distributor UUID"),
    ] = None,
    distributor_name: Annotated[
        str | None,
        Query(description="Filter by distributor name (alternative to distributor_id)"),
    ] = None,
) -> SKUMetrics:
    """Get all inventory metrics for a specific SKU.

    Returns DOH_T30, DOH_T90, shipment:depletion ratios, and velocity trends
    for the specified SKU.

    Supports filtering by warehouse and/or distributor.

    Args:
        sku: The SKU code to get metrics for.

    Returns:
        SKUMetrics: All metrics for the specified SKU.

    Raises:
        HTTPException: 404 if SKU is not tracked in the system.
    """
    # Verify the SKU exists in our system
    result = await db.execute(select(Product).where(Product.sku == sku))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"SKU '{sku}' is not tracked in the system",
        )

    # Resolve warehouse and distributor IDs
    resolved_warehouse_id = await _resolve_warehouse_id(
        db, warehouse_id, warehouse_code
    )
    resolved_distributor_id = await _resolve_distributor_id(
        db, distributor_id, distributor_name
    )

    # Calculate all metrics for the SKU
    doh = await calculate_doh_t30_for_sku(
        db, product.id, warehouse_id=resolved_warehouse_id
    )
    ship_dep = await calculate_ship_dep_ratio_for_sku(
        db, product.id,
        warehouse_id=resolved_warehouse_id,
        distributor_id=resolved_distributor_id,
    )
    velocity = await calculate_velocity_trend_for_sku(
        db, product.id,
        warehouse_id=resolved_warehouse_id,
        distributor_id=resolved_distributor_id,
    )

    return SKUMetrics(
        sku=doh.sku,
        sku_id=doh.sku_id,
        doh=DOHMetricsResponse(
            sku=doh.sku,
            sku_id=doh.sku_id,
            current_inventory=doh.current_inventory,
            doh_t30=doh.doh_t30,
            depletion_30d=doh.depletion_30d,
            daily_rate_30d=doh.daily_rate_30d,
            doh_t90=doh.doh_t90,
            depletion_90d=doh.depletion_90d,
            daily_rate_90d=doh.daily_rate_90d,
            calculated_at=doh.calculated_at,
        ),
        ship_dep_ratio=ShipDepRatioResponse(
            sku=ship_dep.sku,
            sku_id=ship_dep.sku_id,
            shipment_30d=ship_dep.shipment_30d,
            depletion_30d=ship_dep.depletion_30d,
            ratio_30d=ship_dep.ratio_30d,
            shipment_90d=ship_dep.shipment_90d,
            depletion_90d=ship_dep.depletion_90d,
            ratio_90d=ship_dep.ratio_90d,
            calculated_at=ship_dep.calculated_at,
        ),
        velocity_trend=VelocityTrendResponse(
            sku=velocity.sku,
            sku_id=velocity.sku_id,
            depletion_30d=velocity.depletion_30d,
            depletion_90d=velocity.depletion_90d,
            daily_rate_30d_dep=velocity.daily_rate_30d_dep,
            daily_rate_90d_dep=velocity.daily_rate_90d_dep,
            velocity_trend_dep=velocity.velocity_trend_dep,
            shipment_30d=velocity.shipment_30d,
            shipment_90d=velocity.shipment_90d,
            daily_rate_30d_ship=velocity.daily_rate_30d_ship,
            daily_rate_90d_ship=velocity.daily_rate_90d_ship,
            velocity_trend_ship=velocity.velocity_trend_ship,
            calculated_at=velocity.calculated_at,
        ),
        calculated_at=doh.calculated_at,
    )
