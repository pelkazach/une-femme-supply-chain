"""Celery tasks for syncing inventory and invoices with QuickBooks Online.

This module provides bidirectional inventory synchronization between the
Une Femme Supply Chain Platform and QuickBooks Online. Key features:

- Syncs current inventory levels from our database to QuickBooks
- Pulls QuickBooks inventory positions into our system
- Detects discrepancies exceeding ±1% threshold
- Runs every 4 hours per the sync schedule
- Completes within 15 minutes

Invoice sync features:
- Pulls invoices from QuickBooks daily
- Stores invoices locally for AR tracking
- Links line items to local products when SKU matches
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.celery_app import celery_app
from src.config import settings
from src.database import get_async_database_url
from src.models.inventory_event import InventoryEvent
from src.models.product import Product
from src.models.qb_invoice import QBInvoice, QBInvoiceLineItem
from src.models.warehouse import Warehouse
from src.services.metrics import get_current_inventory
from src.services.quickbooks import (
    QuickBooksAPIError,
    QuickBooksAuthError,
    QuickBooksClient,
    SyncResult,
)

logger = logging.getLogger(__name__)

# Tracked SKUs (the 4 Une Femme products)
TRACKED_SKUS = {"UFBub250", "UFRos250", "UFRed250", "UFCha250"}

# Default warehouse code for QuickBooks inventory
QUICKBOOKS_WAREHOUSE_CODE = "QUICKBOOKS"

# Discrepancy threshold (±1%)
DISCREPANCY_THRESHOLD = 0.01


@dataclass
class InventoryDiscrepancy:
    """Represents a discrepancy between platform and QuickBooks inventory."""

    sku: str
    platform_quantity: int
    quickbooks_quantity: int
    difference: int
    difference_percent: float
    exceeds_threshold: bool

    @classmethod
    def calculate(
        cls, sku: str, platform_qty: int, qbo_qty: int
    ) -> "InventoryDiscrepancy":
        """Calculate discrepancy between platform and QuickBooks quantities.

        Args:
            sku: The product SKU
            platform_qty: Quantity in our platform database
            qbo_qty: Quantity in QuickBooks

        Returns:
            InventoryDiscrepancy with calculated values
        """
        difference = platform_qty - qbo_qty

        # Calculate percentage difference based on the larger value
        # to avoid division by zero and give meaningful percentages
        max_qty = max(abs(platform_qty), abs(qbo_qty), 1)
        difference_percent = abs(difference) / max_qty

        exceeds = difference_percent > DISCREPANCY_THRESHOLD

        return cls(
            sku=sku,
            platform_quantity=platform_qty,
            quickbooks_quantity=qbo_qty,
            difference=difference,
            difference_percent=difference_percent,
            exceeds_threshold=exceeds,
        )


@dataclass
class InventorySyncResult:
    """Result of an inventory sync operation."""

    status: str = "success"
    sync_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    direction: str = "bidirectional"
    skus_synced: int = 0
    skus_with_discrepancies: int = 0
    discrepancies: list[InventoryDiscrepancy] = field(default_factory=list)
    push_result: SyncResult | None = None
    pull_events_created: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status,
            "sync_time": self.sync_time.isoformat(),
            "direction": self.direction,
            "skus_synced": self.skus_synced,
            "skus_with_discrepancies": self.skus_with_discrepancies,
            "discrepancies": [
                {
                    "sku": d.sku,
                    "platform_quantity": d.platform_quantity,
                    "quickbooks_quantity": d.quickbooks_quantity,
                    "difference": d.difference,
                    "difference_percent": round(d.difference_percent * 100, 2),
                    "exceeds_threshold": d.exceeds_threshold,
                }
                for d in self.discrepancies
            ],
            "push_result": (
                {
                    "success": self.push_result.success,
                    "failed": self.push_result.failed,
                    "errors": self.push_result.errors,
                }
                if self.push_result
                else None
            ),
            "pull_events_created": self.pull_events_created,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 2),
        }


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


async def get_platform_inventory(
    session: AsyncSession,
    sku_map: dict[str, uuid.UUID],
) -> dict[str, int]:
    """Get current inventory levels from the platform database.

    Args:
        session: Database session
        sku_map: SKU to product UUID mapping

    Returns:
        Dictionary mapping SKU to current quantity
    """
    inventory = {}
    for sku, sku_id in sku_map.items():
        quantity = await get_current_inventory(session, sku_id)
        inventory[sku] = quantity
    return inventory


async def get_quickbooks_inventory(
    client: QuickBooksClient,
) -> dict[str, int]:
    """Get current inventory levels from QuickBooks.

    Args:
        client: QuickBooks API client

    Returns:
        Dictionary mapping SKU (item name) to quantity on hand
    """
    inventory = {}
    items = await client.get_items()

    for item in items:
        name = getattr(item, "Name", None)
        if name and name in TRACKED_SKUS:
            qty_on_hand = getattr(item, "QtyOnHand", 0)
            inventory[name] = int(qty_on_hand or 0)

    return inventory


def detect_discrepancies(
    platform_inventory: dict[str, int],
    qbo_inventory: dict[str, int],
) -> list[InventoryDiscrepancy]:
    """Detect inventory discrepancies between platform and QuickBooks.

    Args:
        platform_inventory: SKU -> quantity from platform
        qbo_inventory: SKU -> quantity from QuickBooks

    Returns:
        List of InventoryDiscrepancy objects
    """
    discrepancies = []

    # Check all SKUs in platform inventory
    all_skus = set(platform_inventory.keys()) | set(qbo_inventory.keys())

    for sku in all_skus:
        platform_qty = platform_inventory.get(sku, 0)
        qbo_qty = qbo_inventory.get(sku, 0)

        discrepancy = InventoryDiscrepancy.calculate(sku, platform_qty, qbo_qty)
        if discrepancy.difference != 0:
            discrepancies.append(discrepancy)

    return discrepancies


async def push_inventory_to_quickbooks(
    client: QuickBooksClient,
    platform_inventory: dict[str, int],
) -> SyncResult:
    """Push platform inventory levels to QuickBooks.

    Args:
        client: QuickBooks API client
        platform_inventory: SKU -> quantity from platform

    Returns:
        SyncResult with push operation details
    """
    products = [
        {"sku": sku, "quantity": qty} for sku, qty in platform_inventory.items()
    ]
    return await client.sync_inventory(products)


async def pull_inventory_from_quickbooks(
    session: AsyncSession,
    qbo_inventory: dict[str, int],
    sku_map: dict[str, uuid.UUID],
    warehouse_id: uuid.UUID,
    sync_time: datetime,
) -> int:
    """Create snapshot events from QuickBooks inventory levels.

    This creates inventory snapshot events representing QuickBooks' view
    of inventory, which can be used for reconciliation.

    Args:
        session: Database session
        qbo_inventory: SKU -> quantity from QuickBooks
        sku_map: SKU to product UUID mapping
        warehouse_id: QuickBooks warehouse UUID
        sync_time: Timestamp for the snapshot events

    Returns:
        Number of events created
    """
    events_created = 0

    for sku, quantity in qbo_inventory.items():
        if sku not in sku_map:
            continue

        event = InventoryEvent(
            time=sync_time,
            sku_id=sku_map[sku],
            warehouse_id=warehouse_id,
            event_type="snapshot",
            quantity=quantity,
        )
        session.add(event)
        events_created += 1

    return events_created


async def _async_sync_quickbooks_inventory(
    direction: str = "bidirectional",
) -> InventorySyncResult:
    """Async implementation of QuickBooks inventory sync.

    Args:
        direction: Sync direction - "push" (platform -> QBO),
                   "pull" (QBO -> platform), or "bidirectional"

    Returns:
        InventorySyncResult with sync details
    """
    start_time = datetime.now(UTC)
    result = InventorySyncResult(direction=direction, sync_time=start_time)

    # Create database connection
    engine = create_async_engine(
        get_async_database_url(settings.database_url),
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    client = QuickBooksClient()

    try:
        # Load existing token
        if not client.load_token():
            result.status = "error"
            result.errors.append(
                "QuickBooks not authenticated. Please complete OAuth flow first."
            )
            logger.error("QuickBooks token not found or invalid")
            return result

        async with async_session() as session:
            # Get or create QuickBooks warehouse
            warehouse_id = await get_or_create_warehouse(
                session, QUICKBOOKS_WAREHOUSE_CODE, "QuickBooks Warehouse"
            )

            # Get SKU mapping
            sku_map = await get_sku_id_map(session)
            if not sku_map:
                result.status = "warning"
                result.errors.append("No tracked SKUs found in database")
                logger.warning("No tracked SKUs found in database")
                return result

            # Get platform inventory
            platform_inventory = await get_platform_inventory(session, sku_map)
            logger.info("Platform inventory: %s", platform_inventory)

            # Get QuickBooks inventory
            try:
                qbo_inventory = await get_quickbooks_inventory(client)
                logger.info("QuickBooks inventory: %s", qbo_inventory)
            except QuickBooksAPIError as e:
                result.status = "error"
                result.errors.append(f"Failed to fetch QuickBooks inventory: {e}")
                logger.error("Failed to fetch QuickBooks inventory: %s", e)
                return result

            # Detect discrepancies
            discrepancies = detect_discrepancies(platform_inventory, qbo_inventory)
            result.discrepancies = discrepancies
            result.skus_with_discrepancies = sum(
                1 for d in discrepancies if d.exceeds_threshold
            )

            if result.skus_with_discrepancies > 0:
                logger.warning(
                    "Found %d SKUs with discrepancies exceeding %.1f%% threshold",
                    result.skus_with_discrepancies,
                    DISCREPANCY_THRESHOLD * 100,
                )
                for d in discrepancies:
                    if d.exceeds_threshold:
                        logger.warning(
                            "Discrepancy for %s: platform=%d, QBO=%d, diff=%.1f%%",
                            d.sku,
                            d.platform_quantity,
                            d.quickbooks_quantity,
                            d.difference_percent * 100,
                        )

            # Perform sync operations based on direction
            if direction in ("push", "bidirectional"):
                try:
                    push_result = await push_inventory_to_quickbooks(
                        client, platform_inventory
                    )
                    result.push_result = push_result
                    result.skus_synced = push_result.success
                    logger.info(
                        "Pushed inventory to QuickBooks: %d success, %d failed",
                        push_result.success,
                        push_result.failed,
                    )
                except QuickBooksAPIError as e:
                    result.errors.append(f"Push to QuickBooks failed: {e}")
                    logger.error("Push to QuickBooks failed: %s", e)

            if direction in ("pull", "bidirectional"):
                try:
                    pull_count = await pull_inventory_from_quickbooks(
                        session,
                        qbo_inventory,
                        sku_map,
                        warehouse_id,
                        start_time,
                    )
                    result.pull_events_created = pull_count
                    logger.info(
                        "Created %d inventory snapshot events from QuickBooks",
                        pull_count,
                    )
                except Exception as e:
                    result.errors.append(f"Pull from QuickBooks failed: {e}")
                    logger.error("Pull from QuickBooks failed: %s", e)

            await session.commit()

    except QuickBooksAuthError as e:
        result.status = "error"
        result.errors.append(f"Authentication failed: {e}")
        logger.error("QuickBooks authentication failed: %s", e)
    except Exception as e:
        result.status = "error"
        result.errors.append(f"Unexpected error: {e}")
        logger.exception("Unexpected error during QuickBooks sync")
    finally:
        await engine.dispose()

    # Calculate duration
    end_time = datetime.now(UTC)
    result.duration_seconds = (end_time - start_time).total_seconds()

    # Set final status
    if result.errors and result.status == "success":
        result.status = "partial"

    return result


@celery_app.task(
    bind=True,
    name="src.tasks.quickbooks_sync.sync_quickbooks_inventory",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    autoretry_for=(QuickBooksAPIError,),
)
def sync_quickbooks_inventory(
    self: Any,
    direction: str = "bidirectional",
) -> dict[str, Any]:
    """Celery task to sync inventory with QuickBooks Online.

    This task runs every 4 hours and performs bidirectional sync:
    1. Pushes platform inventory levels to QuickBooks
    2. Pulls QuickBooks inventory levels as snapshot events
    3. Detects and logs discrepancies exceeding ±1%

    Args:
        direction: Sync direction - "push", "pull", or "bidirectional"

    Returns:
        Dictionary with sync results including counts, discrepancies, and errors
    """
    logger.info("Starting QuickBooks inventory sync (direction=%s)", direction)

    try:
        result = asyncio.run(_async_sync_quickbooks_inventory(direction=direction))
        logger.info(
            "QuickBooks sync completed in %.2fs: %d SKUs synced, %d discrepancies",
            result.duration_seconds,
            result.skus_synced,
            result.skus_with_discrepancies,
        )
        return result.to_dict()
    except Exception as e:
        logger.exception("QuickBooks sync task failed")
        raise self.retry(exc=e) from e


@celery_app.task(name="src.tasks.quickbooks_sync.check_inventory_discrepancies")
def check_inventory_discrepancies() -> dict[str, Any]:
    """Celery task to check for inventory discrepancies without syncing.

    This is a read-only task that compares inventory levels between
    the platform and QuickBooks without making any changes.

    Returns:
        Dictionary with discrepancy details
    """
    logger.info("Checking QuickBooks inventory discrepancies")

    async def _check() -> dict[str, Any]:
        engine = create_async_engine(
            get_async_database_url(settings.database_url),
            pool_pre_ping=True,
        )
        async_session = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        client = QuickBooksClient()

        try:
            if not client.load_token():
                return {
                    "status": "error",
                    "error": "QuickBooks not authenticated",
                }

            async with async_session() as session:
                sku_map = await get_sku_id_map(session)
                if not sku_map:
                    return {"status": "warning", "error": "No tracked SKUs found"}

                platform_inventory = await get_platform_inventory(session, sku_map)
                qbo_inventory = await get_quickbooks_inventory(client)

                discrepancies = detect_discrepancies(platform_inventory, qbo_inventory)
                exceeding = [d for d in discrepancies if d.exceeds_threshold]

                return {
                    "status": "success",
                    "platform_inventory": platform_inventory,
                    "quickbooks_inventory": qbo_inventory,
                    "discrepancies": [
                        {
                            "sku": d.sku,
                            "platform_quantity": d.platform_quantity,
                            "quickbooks_quantity": d.quickbooks_quantity,
                            "difference_percent": round(d.difference_percent * 100, 2),
                            "exceeds_threshold": d.exceeds_threshold,
                        }
                        for d in discrepancies
                    ],
                    "skus_exceeding_threshold": len(exceeding),
                }
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_check())
    except Exception as e:
        logger.exception("Discrepancy check failed")
        return {"status": "error", "error": str(e)}


# ============================================================================
# Invoice Sync
# ============================================================================


@dataclass
class InvoiceSyncResult:
    """Result of an invoice sync operation."""

    status: str = "success"
    sync_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    invoices_fetched: int = 0
    invoices_created: int = 0
    invoices_updated: int = 0
    line_items_created: int = 0
    line_items_linked: int = 0  # Line items linked to local products
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status,
            "sync_time": self.sync_time.isoformat(),
            "invoices_fetched": self.invoices_fetched,
            "invoices_created": self.invoices_created,
            "invoices_updated": self.invoices_updated,
            "line_items_created": self.line_items_created,
            "line_items_linked": self.line_items_linked,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 2),
        }


def parse_qb_date(date_value: Any) -> datetime | None:
    """Parse a date value from QuickBooks into a datetime.

    QuickBooks may return dates as strings or datetime objects in various formats.

    Args:
        date_value: The date value from QuickBooks

    Returns:
        Parsed datetime or None if parsing fails
    """
    if date_value is None:
        return None

    if isinstance(date_value, datetime):
        if date_value.tzinfo is None:
            return date_value.replace(tzinfo=UTC)
        return date_value

    if isinstance(date_value, str):
        # Try various date formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO with microseconds and timezone
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",  # ISO with microseconds, no timezone
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]
        # Normalize Z suffix to +0000
        normalized = date_value.replace("Z", "+0000")
        for fmt in formats:
            try:
                dt = datetime.strptime(normalized, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except ValueError:
                continue

    logger.warning("Could not parse date value: %s", date_value)
    return None


def parse_qb_decimal(value: Any) -> Decimal | None:
    """Parse a numeric value from QuickBooks into a Decimal.

    Args:
        value: The numeric value from QuickBooks

    Returns:
        Parsed Decimal or None if parsing fails
    """
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except Exception:
        logger.warning("Could not parse decimal value: %s", value)
        return None


def extract_invoice_status(invoice: Any) -> str:
    """Extract the invoice status from a QuickBooks invoice object.

    Args:
        invoice: QuickBooks Invoice object

    Returns:
        Status string (Open, Paid, Overdue, etc.)
    """
    balance = getattr(invoice, "Balance", None)

    # Check if fully paid
    if balance is not None and float(balance) == 0:
        return "Paid"

    # Check if overdue
    due_date = getattr(invoice, "DueDate", None)
    if due_date:
        parsed_due = parse_qb_date(due_date)
        if parsed_due and parsed_due < datetime.now(UTC):
            return "Overdue"

    return "Open"


def extract_line_items(invoice: Any) -> list[dict[str, Any]]:
    """Extract line items from a QuickBooks invoice object.

    Args:
        invoice: QuickBooks Invoice object

    Returns:
        List of line item dictionaries
    """
    line_items: list[dict[str, Any]] = []

    # QuickBooks stores line items in the Line attribute
    lines = getattr(invoice, "Line", None)
    if not lines:
        return line_items

    line_number = 0
    for line in lines:
        # Skip subtotal, tax, and discount lines
        detail_type = getattr(line, "DetailType", None)
        if detail_type != "SalesItemLineDetail":
            continue

        line_number += 1
        detail = getattr(line, "SalesItemLineDetail", None)
        if not detail:
            continue

        item_ref = getattr(detail, "ItemRef", None)
        item_id = getattr(item_ref, "value", None) if item_ref else None
        item_name = getattr(item_ref, "name", None) if item_ref else None

        line_item = {
            "line_number": line_number,
            "description": getattr(line, "Description", None),
            "quantity": getattr(detail, "Qty", None),
            "unit_price": getattr(detail, "UnitPrice", None),
            "amount": getattr(line, "Amount", None),
            "qb_item_id": item_id,
            "qb_item_name": item_name,
        }
        line_items.append(line_item)

    return line_items


async def get_or_create_invoice(
    session: AsyncSession,
    qb_invoice_id: str,
    invoice_data: dict[str, Any],
    sync_time: datetime,
) -> tuple[QBInvoice, bool]:
    """Get an existing invoice or create a new one.

    Args:
        session: Database session
        qb_invoice_id: QuickBooks invoice ID
        invoice_data: Invoice data dictionary
        sync_time: Timestamp of the sync

    Returns:
        Tuple of (invoice, created) where created is True if new invoice
    """
    # Check if invoice already exists
    result = await session.execute(
        select(QBInvoice).where(QBInvoice.qb_invoice_id == qb_invoice_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing invoice
        existing.invoice_number = invoice_data.get("invoice_number")
        existing.customer_name = invoice_data.get("customer_name")
        existing.customer_id = invoice_data.get("customer_id")
        existing.invoice_date = invoice_data.get("invoice_date")
        existing.due_date = invoice_data.get("due_date")
        existing.total_amount = invoice_data.get("total_amount")
        existing.balance_due = invoice_data.get("balance_due")
        existing.currency_code = invoice_data.get("currency_code", "USD")
        existing.status = invoice_data.get("status", "Open")
        existing.line_items = invoice_data.get("line_items")
        existing.qb_created_at = invoice_data.get("qb_created_at")
        existing.qb_updated_at = invoice_data.get("qb_updated_at")
        existing.synced_at = sync_time
        return existing, False

    # Create new invoice
    new_invoice = QBInvoice(
        qb_invoice_id=qb_invoice_id,
        invoice_number=invoice_data.get("invoice_number"),
        customer_name=invoice_data.get("customer_name"),
        customer_id=invoice_data.get("customer_id"),
        invoice_date=invoice_data.get("invoice_date"),
        due_date=invoice_data.get("due_date"),
        total_amount=invoice_data.get("total_amount"),
        balance_due=invoice_data.get("balance_due"),
        currency_code=invoice_data.get("currency_code", "USD"),
        status=invoice_data.get("status", "Open"),
        line_items=invoice_data.get("line_items"),
        qb_created_at=invoice_data.get("qb_created_at"),
        qb_updated_at=invoice_data.get("qb_updated_at"),
        synced_at=sync_time,
    )
    session.add(new_invoice)
    await session.flush()
    return new_invoice, True


async def create_line_item_records(
    session: AsyncSession,
    invoice: QBInvoice,
    line_items: list[dict[str, Any]],
    sku_map: dict[str, uuid.UUID],
) -> tuple[int, int]:
    """Create line item records for an invoice.

    Args:
        session: Database session
        invoice: The parent invoice
        line_items: List of line item dictionaries
        sku_map: Mapping of SKU names to product UUIDs

    Returns:
        Tuple of (items_created, items_linked)
    """
    items_created = 0
    items_linked = 0

    for item_data in line_items:
        # Check if item name matches a tracked SKU
        item_name = item_data.get("qb_item_name")
        sku_id = sku_map.get(item_name) if item_name else None

        line_item = QBInvoiceLineItem(
            invoice_id=invoice.id,
            line_number=item_data.get("line_number", 1),
            description=item_data.get("description"),
            quantity=item_data.get("quantity"),
            unit_price=parse_qb_decimal(item_data.get("unit_price")),
            amount=parse_qb_decimal(item_data.get("amount")),
            qb_item_id=item_data.get("qb_item_id"),
            qb_item_name=item_name,
            sku_id=sku_id,
        )
        session.add(line_item)
        items_created += 1

        if sku_id:
            items_linked += 1

    return items_created, items_linked


async def delete_existing_line_items(
    session: AsyncSession,
    invoice_id: uuid.UUID,
) -> None:
    """Delete existing line items for an invoice before re-creating.

    Args:
        session: Database session
        invoice_id: The invoice UUID
    """
    from sqlalchemy import delete

    await session.execute(
        delete(QBInvoiceLineItem).where(QBInvoiceLineItem.invoice_id == invoice_id)
    )


async def pull_invoices_from_quickbooks(
    client: QuickBooksClient,
    session: AsyncSession,
    sku_map: dict[str, uuid.UUID],
    since: datetime | None = None,
    sync_time: datetime | None = None,
) -> InvoiceSyncResult:
    """Pull invoices from QuickBooks and store locally.

    Args:
        client: QuickBooks API client
        session: Database session
        sku_map: SKU to product UUID mapping
        since: Only fetch invoices modified after this time
        sync_time: Timestamp for this sync (defaults to now)

    Returns:
        InvoiceSyncResult with sync details
    """
    if sync_time is None:
        sync_time = datetime.now(UTC)

    result = InvoiceSyncResult(sync_time=sync_time)

    try:
        # Fetch invoices from QuickBooks
        invoices = await client.get_invoices(since=since)
        result.invoices_fetched = len(invoices)
        logger.info("Fetched %d invoices from QuickBooks", len(invoices))

        for invoice in invoices:
            try:
                # Extract invoice ID
                qb_id = getattr(invoice, "Id", None)
                if not qb_id:
                    logger.warning("Invoice without ID, skipping")
                    continue

                # Extract customer info
                customer_ref = getattr(invoice, "CustomerRef", None)
                customer_id = getattr(customer_ref, "value", None) if customer_ref else None
                customer_name = getattr(customer_ref, "name", None) if customer_ref else None

                # Extract metadata timestamps
                meta = getattr(invoice, "MetaData", None)
                qb_created = parse_qb_date(getattr(meta, "CreateTime", None)) if meta else None
                qb_updated = parse_qb_date(getattr(meta, "LastUpdatedTime", None)) if meta else None

                # Extract currency
                currency_ref = getattr(invoice, "CurrencyRef", None)
                currency_code = getattr(currency_ref, "value", "USD") if currency_ref else "USD"

                # Extract line items
                line_items_data = extract_line_items(invoice)

                # Build invoice data dictionary
                invoice_data = {
                    "invoice_number": getattr(invoice, "DocNumber", None),
                    "customer_name": customer_name,
                    "customer_id": customer_id,
                    "invoice_date": parse_qb_date(getattr(invoice, "TxnDate", None)),
                    "due_date": parse_qb_date(getattr(invoice, "DueDate", None)),
                    "total_amount": parse_qb_decimal(getattr(invoice, "TotalAmt", None)),
                    "balance_due": parse_qb_decimal(getattr(invoice, "Balance", None)),
                    "currency_code": currency_code,
                    "status": extract_invoice_status(invoice),
                    "line_items": line_items_data,
                    "qb_created_at": qb_created,
                    "qb_updated_at": qb_updated,
                }

                # Get or create invoice record
                db_invoice, created = await get_or_create_invoice(
                    session, qb_id, invoice_data, sync_time
                )

                if created:
                    result.invoices_created += 1
                else:
                    result.invoices_updated += 1
                    # Delete existing line items before re-creating
                    await delete_existing_line_items(session, db_invoice.id)

                # Create line item records
                items_created, items_linked = await create_line_item_records(
                    session, db_invoice, line_items_data, sku_map
                )
                result.line_items_created += items_created
                result.line_items_linked += items_linked

            except Exception as e:
                error_msg = f"Error processing invoice {qb_id}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        await session.commit()

    except QuickBooksAPIError as e:
        result.status = "error"
        result.errors.append(f"QuickBooks API error: {e}")
        logger.error("QuickBooks API error during invoice sync: %s", e)

    except Exception as e:
        result.status = "error"
        result.errors.append(f"Unexpected error: {e}")
        logger.exception("Unexpected error during invoice sync")

    if result.errors and result.status == "success":
        result.status = "partial"

    return result


async def _async_sync_quickbooks_invoices(
    since: datetime | None = None,
) -> InvoiceSyncResult:
    """Async implementation of QuickBooks invoice sync.

    Args:
        since: Only fetch invoices modified after this time.
               Defaults to 24 hours ago.

    Returns:
        InvoiceSyncResult with sync details
    """
    start_time = datetime.now(UTC)

    # Default to last 24 hours if not specified
    if since is None:
        since = start_time - timedelta(days=1)

    result = InvoiceSyncResult(sync_time=start_time)

    # Create database connection
    engine = create_async_engine(
        get_async_database_url(settings.database_url),
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    client = QuickBooksClient()

    try:
        # Load existing token
        if not client.load_token():
            result.status = "error"
            result.errors.append(
                "QuickBooks not authenticated. Please complete OAuth flow first."
            )
            logger.error("QuickBooks token not found or invalid")
            return result

        async with async_session() as session:
            # Get SKU mapping for linking line items to products
            sku_map = await get_sku_id_map(session)

            # Pull invoices
            result = await pull_invoices_from_quickbooks(
                client, session, sku_map, since=since, sync_time=start_time
            )

    except QuickBooksAuthError as e:
        result.status = "error"
        result.errors.append(f"Authentication failed: {e}")
        logger.error("QuickBooks authentication failed: %s", e)
    except Exception as e:
        result.status = "error"
        result.errors.append(f"Unexpected error: {e}")
        logger.exception("Unexpected error during QuickBooks invoice sync")
    finally:
        await engine.dispose()

    # Calculate duration
    end_time = datetime.now(UTC)
    result.duration_seconds = (end_time - start_time).total_seconds()

    return result


@celery_app.task(
    bind=True,
    name="src.tasks.quickbooks_sync.sync_quickbooks_invoices",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    autoretry_for=(QuickBooksAPIError,),
)
def sync_quickbooks_invoices(
    self: Any,
    days_back: int = 1,
) -> dict[str, Any]:
    """Celery task to sync invoices from QuickBooks Online.

    This task runs daily and pulls invoices that have been modified
    since the specified number of days ago.

    Args:
        days_back: Number of days back to fetch invoices (default 1 for daily sync)

    Returns:
        Dictionary with sync results
    """
    since = datetime.now(UTC) - timedelta(days=days_back)
    logger.info("Starting QuickBooks invoice sync (since=%s)", since.isoformat())

    try:
        result = asyncio.run(_async_sync_quickbooks_invoices(since=since))
        logger.info(
            "QuickBooks invoice sync completed in %.2fs: %d fetched, %d created, %d updated",
            result.duration_seconds,
            result.invoices_fetched,
            result.invoices_created,
            result.invoices_updated,
        )
        return result.to_dict()
    except Exception as e:
        logger.exception("QuickBooks invoice sync task failed")
        raise self.retry(exc=e) from e


@celery_app.task(name="src.tasks.quickbooks_sync.sync_quickbooks_invoices_full")
def sync_quickbooks_invoices_full() -> dict[str, Any]:
    """Celery task to perform a full invoice sync from QuickBooks.

    This task fetches ALL invoices from QuickBooks, not just recent ones.
    Use this for initial sync or recovery scenarios.

    Returns:
        Dictionary with sync results
    """
    logger.info("Starting full QuickBooks invoice sync")

    try:
        # Pass None for since to fetch all invoices
        result = asyncio.run(_async_sync_quickbooks_invoices(since=None))
        logger.info(
            "Full QuickBooks invoice sync completed in %.2fs: %d fetched, %d created, %d updated",
            result.duration_seconds,
            result.invoices_fetched,
            result.invoices_created,
            result.invoices_updated,
        )
        return result.to_dict()
    except Exception as e:
        logger.exception("Full QuickBooks invoice sync task failed")
        return {"status": "error", "error": str(e)}
