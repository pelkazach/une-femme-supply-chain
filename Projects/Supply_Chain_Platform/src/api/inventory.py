"""FastAPI routes for inventory management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import Product
from src.services.winedirect import (
    WineDirectAPIError,
    WineDirectAuthError,
    WineDirectClient,
)

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
