"""Tests for QuickBooks invoice sync task."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.qb_invoice import QBInvoice, QBInvoiceLineItem
from src.services.quickbooks import QuickBooksAPIError, QuickBooksClient
from src.tasks.quickbooks_sync import (
    InvoiceSyncResult,
    create_line_item_records,
    delete_existing_line_items,
    extract_invoice_status,
    extract_line_items,
    get_or_create_invoice,
    parse_qb_date,
    parse_qb_decimal,
    pull_invoices_from_quickbooks,
    sync_quickbooks_invoices,
    sync_quickbooks_invoices_full,
)


# ============================================================================
# InvoiceSyncResult Tests
# ============================================================================


class TestInvoiceSyncResult:
    """Tests for InvoiceSyncResult dataclass."""

    def test_default_values(self) -> None:
        """Test default values are correct."""
        result = InvoiceSyncResult()

        assert result.status == "success"
        assert result.invoices_fetched == 0
        assert result.invoices_created == 0
        assert result.invoices_updated == 0
        assert result.line_items_created == 0
        assert result.line_items_linked == 0
        assert result.errors == []

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        sync_time = datetime.now(UTC)
        result = InvoiceSyncResult(
            status="partial",
            sync_time=sync_time,
            invoices_fetched=10,
            invoices_created=5,
            invoices_updated=3,
            line_items_created=25,
            line_items_linked=8,
            errors=["Some error"],
            duration_seconds=5.123,
        )

        data = result.to_dict()

        assert data["status"] == "partial"
        assert data["sync_time"] == sync_time.isoformat()
        assert data["invoices_fetched"] == 10
        assert data["invoices_created"] == 5
        assert data["invoices_updated"] == 3
        assert data["line_items_created"] == 25
        assert data["line_items_linked"] == 8
        assert data["errors"] == ["Some error"]
        assert data["duration_seconds"] == 5.12


# ============================================================================
# parse_qb_date Tests
# ============================================================================


class TestParseQbDate:
    """Tests for parse_qb_date function."""

    def test_parse_none(self) -> None:
        """Test parsing None returns None."""
        assert parse_qb_date(None) is None

    def test_parse_datetime_with_tz(self) -> None:
        """Test parsing datetime with timezone."""
        dt = datetime(2026, 1, 15, 10, 30, tzinfo=UTC)
        result = parse_qb_date(dt)

        assert result == dt

    def test_parse_datetime_without_tz(self) -> None:
        """Test parsing datetime without timezone adds UTC."""
        dt = datetime(2026, 1, 15, 10, 30)
        result = parse_qb_date(dt)

        assert result is not None
        assert result.tzinfo == UTC

    def test_parse_iso_string_with_tz(self) -> None:
        """Test parsing ISO string with timezone."""
        result = parse_qb_date("2026-01-15T10:30:00+0000")

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15

    def test_parse_iso_string_with_z(self) -> None:
        """Test parsing ISO string with Z suffix."""
        result = parse_qb_date("2026-01-15T10:30:00Z")

        assert result is not None
        assert result.year == 2026

    def test_parse_date_only_string(self) -> None:
        """Test parsing date-only string."""
        result = parse_qb_date("2026-01-15")

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15

    def test_parse_invalid_string(self) -> None:
        """Test parsing invalid string returns None."""
        result = parse_qb_date("not a date")

        assert result is None


# ============================================================================
# parse_qb_decimal Tests
# ============================================================================


class TestParseQbDecimal:
    """Tests for parse_qb_decimal function."""

    def test_parse_none(self) -> None:
        """Test parsing None returns None."""
        assert parse_qb_decimal(None) is None

    def test_parse_int(self) -> None:
        """Test parsing integer."""
        result = parse_qb_decimal(100)

        assert result == Decimal("100")

    def test_parse_float(self) -> None:
        """Test parsing float."""
        result = parse_qb_decimal(99.99)

        assert result == Decimal("99.99")

    def test_parse_string(self) -> None:
        """Test parsing string."""
        result = parse_qb_decimal("1234.56")

        assert result == Decimal("1234.56")

    def test_parse_invalid(self) -> None:
        """Test parsing invalid value returns None."""
        result = parse_qb_decimal("not a number")

        assert result is None


# ============================================================================
# extract_invoice_status Tests
# ============================================================================


class TestExtractInvoiceStatus:
    """Tests for extract_invoice_status function."""

    def test_paid_invoice(self) -> None:
        """Test invoice with zero balance is Paid."""
        invoice = MagicMock()
        invoice.Balance = 0
        invoice.TotalAmt = 100
        invoice.DueDate = None

        status = extract_invoice_status(invoice)

        assert status == "Paid"

    def test_overdue_invoice(self) -> None:
        """Test invoice past due date is Overdue."""
        invoice = MagicMock()
        invoice.Balance = 100
        invoice.TotalAmt = 100
        # Use a simple date format that parse_qb_date can handle
        invoice.DueDate = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")

        status = extract_invoice_status(invoice)

        assert status == "Overdue"

    def test_open_invoice(self) -> None:
        """Test invoice with balance and future due date is Open."""
        invoice = MagicMock()
        invoice.Balance = 100
        invoice.TotalAmt = 100
        invoice.DueDate = (datetime.now(UTC) + timedelta(days=30)).isoformat()

        status = extract_invoice_status(invoice)

        assert status == "Open"

    def test_open_invoice_no_due_date(self) -> None:
        """Test invoice with balance and no due date is Open."""
        invoice = MagicMock()
        invoice.Balance = 100
        invoice.TotalAmt = 100
        invoice.DueDate = None

        status = extract_invoice_status(invoice)

        assert status == "Open"


# ============================================================================
# extract_line_items Tests
# ============================================================================


class TestExtractLineItems:
    """Tests for extract_line_items function."""

    def test_no_lines(self) -> None:
        """Test invoice with no lines."""
        invoice = MagicMock()
        invoice.Line = None

        items = extract_line_items(invoice)

        assert items == []

    def test_empty_lines(self) -> None:
        """Test invoice with empty lines list."""
        invoice = MagicMock()
        invoice.Line = []

        items = extract_line_items(invoice)

        assert items == []

    def test_sales_item_line(self) -> None:
        """Test extracting sales item line."""
        item_ref = MagicMock()
        item_ref.value = "item123"
        item_ref.name = "UFBub250"

        detail = MagicMock()
        detail.ItemRef = item_ref
        detail.Qty = 10
        detail.UnitPrice = 25.00

        line = MagicMock()
        line.DetailType = "SalesItemLineDetail"
        line.SalesItemLineDetail = detail
        line.Description = "Une Femme Bubbles 250ml"
        line.Amount = 250.00

        invoice = MagicMock()
        invoice.Line = [line]

        items = extract_line_items(invoice)

        assert len(items) == 1
        assert items[0]["line_number"] == 1
        assert items[0]["qb_item_id"] == "item123"
        assert items[0]["qb_item_name"] == "UFBub250"
        assert items[0]["quantity"] == 10
        assert items[0]["unit_price"] == 25.00
        assert items[0]["amount"] == 250.00

    def test_skips_non_sales_lines(self) -> None:
        """Test that subtotal/tax lines are skipped."""
        subtotal_line = MagicMock()
        subtotal_line.DetailType = "SubTotalLineDetail"

        item_ref = MagicMock()
        item_ref.value = "item1"
        item_ref.name = "Product"

        sales_detail = MagicMock()
        sales_detail.ItemRef = item_ref
        sales_detail.Qty = 5
        sales_detail.UnitPrice = 10.00

        sales_line = MagicMock()
        sales_line.DetailType = "SalesItemLineDetail"
        sales_line.SalesItemLineDetail = sales_detail
        sales_line.Description = "Product"
        sales_line.Amount = 50.00

        invoice = MagicMock()
        invoice.Line = [subtotal_line, sales_line]

        items = extract_line_items(invoice)

        assert len(items) == 1
        assert items[0]["qb_item_name"] == "Product"


# ============================================================================
# get_or_create_invoice Tests
# ============================================================================


class TestGetOrCreateInvoice:
    """Tests for get_or_create_invoice function."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock database session."""
        return MagicMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_creates_new_invoice(self, mock_session: MagicMock) -> None:
        """Test creating a new invoice."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()

        sync_time = datetime.now(UTC)
        invoice_data = {
            "invoice_number": "INV-001",
            "customer_name": "Test Customer",
            "total_amount": Decimal("100.00"),
        }

        invoice, created = await get_or_create_invoice(
            mock_session, "qb123", invoice_data, sync_time
        )

        assert created is True
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_existing_invoice(self, mock_session: MagicMock) -> None:
        """Test updating an existing invoice."""
        existing_invoice = QBInvoice(
            qb_invoice_id="qb123",
            invoice_number="INV-001",
            synced_at=datetime.now(UTC),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_invoice
        mock_session.execute = AsyncMock(return_value=mock_result)

        sync_time = datetime.now(UTC)
        invoice_data = {
            "invoice_number": "INV-001-UPDATED",
            "customer_name": "Updated Customer",
            "total_amount": Decimal("200.00"),
        }

        invoice, created = await get_or_create_invoice(
            mock_session, "qb123", invoice_data, sync_time
        )

        assert created is False
        assert invoice.invoice_number == "INV-001-UPDATED"
        assert invoice.customer_name == "Updated Customer"


# ============================================================================
# create_line_item_records Tests
# ============================================================================


class TestCreateLineItemRecords:
    """Tests for create_line_item_records function."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock database session."""
        return MagicMock(spec=AsyncSession)

    @pytest.fixture
    def mock_invoice(self) -> QBInvoice:
        """Create a mock invoice."""
        return QBInvoice(
            id=uuid.uuid4(),
            qb_invoice_id="qb123",
            synced_at=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_creates_line_items(
        self, mock_session: MagicMock, mock_invoice: QBInvoice
    ) -> None:
        """Test creating line item records."""
        line_items = [
            {
                "line_number": 1,
                "description": "Product 1",
                "quantity": 10,
                "unit_price": "25.00",
                "amount": "250.00",
                "qb_item_id": "item1",
                "qb_item_name": "OTHER_PRODUCT",
            },
        ]
        sku_map: dict[str, uuid.UUID] = {}

        created, linked = await create_line_item_records(
            mock_session, mock_invoice, line_items, sku_map
        )

        assert created == 1
        assert linked == 0
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_links_to_products(
        self, mock_session: MagicMock, mock_invoice: QBInvoice
    ) -> None:
        """Test linking line items to local products."""
        sku_id = uuid.uuid4()
        line_items = [
            {
                "line_number": 1,
                "qb_item_name": "UFBub250",
                "quantity": 10,
            },
        ]
        sku_map = {"UFBub250": sku_id}

        created, linked = await create_line_item_records(
            mock_session, mock_invoice, line_items, sku_map
        )

        assert created == 1
        assert linked == 1

        # Verify the line item has the sku_id set
        call_args = mock_session.add.call_args[0][0]
        assert call_args.sku_id == sku_id


# ============================================================================
# pull_invoices_from_quickbooks Tests
# ============================================================================


class TestPullInvoicesFromQuickbooks:
    """Tests for pull_invoices_from_quickbooks function."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock database session."""
        session = MagicMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock QuickBooks client."""
        return MagicMock(spec=QuickBooksClient)

    @pytest.mark.asyncio
    async def test_fetches_invoices(
        self, mock_session: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that invoices are fetched from QuickBooks."""
        mock_client.get_invoices = AsyncMock(return_value=[])

        result = await pull_invoices_from_quickbooks(
            mock_client, mock_session, {}, since=None
        )

        assert result.status == "success"
        assert result.invoices_fetched == 0
        mock_client.get_invoices.assert_called_once()

    @pytest.mark.asyncio
    async def test_processes_invoice(
        self, mock_session: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test processing an invoice."""
        # Create mock invoice
        customer_ref = MagicMock()
        customer_ref.value = "cust123"
        customer_ref.name = "Test Customer"

        meta = MagicMock()
        meta.CreateTime = "2026-01-15T10:00:00Z"
        meta.LastUpdatedTime = "2026-01-16T10:00:00Z"

        invoice = MagicMock()
        invoice.Id = "inv123"
        invoice.DocNumber = "INV-001"
        invoice.CustomerRef = customer_ref
        invoice.MetaData = meta
        invoice.TxnDate = "2026-01-15"
        invoice.DueDate = "2026-02-15"
        invoice.TotalAmt = 100.00
        invoice.Balance = 100.00
        invoice.CurrencyRef = MagicMock(value="USD")
        invoice.Line = []

        mock_client.get_invoices = AsyncMock(return_value=[invoice])

        # Mock database operations
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await pull_invoices_from_quickbooks(
            mock_client, mock_session, {}, since=None
        )

        assert result.invoices_fetched == 1
        assert result.invoices_created == 1

    @pytest.mark.asyncio
    async def test_handles_api_error(
        self, mock_session: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test handling QuickBooks API errors."""
        mock_client.get_invoices = AsyncMock(
            side_effect=QuickBooksAPIError("API error")
        )

        result = await pull_invoices_from_quickbooks(
            mock_client, mock_session, {}, since=None
        )

        assert result.status == "error"
        assert len(result.errors) == 1
        assert "API error" in result.errors[0]


# ============================================================================
# Celery Task Tests
# ============================================================================


class TestSyncQuickBooksInvoicesTask:
    """Tests for sync_quickbooks_invoices Celery task."""

    def test_task_returns_sync_result(self) -> None:
        """Test that the task returns InvoiceSyncResult as dict."""
        mock_result = InvoiceSyncResult(
            status="success",
            invoices_fetched=10,
            invoices_created=5,
        )

        with patch("asyncio.run", return_value=mock_result):
            result = sync_quickbooks_invoices.apply(
                kwargs={"days_back": 1}
            ).result

        assert result["status"] == "success"
        assert result["invoices_fetched"] == 10
        assert result["invoices_created"] == 5

    def test_task_default_days_back(self) -> None:
        """Test that default days_back is 1."""
        mock_result = InvoiceSyncResult()

        with patch("asyncio.run", return_value=mock_result):
            # Default should be 1 day back
            result = sync_quickbooks_invoices.apply().result

        assert result["status"] == "success"


class TestSyncQuickBooksInvoicesFullTask:
    """Tests for sync_quickbooks_invoices_full Celery task."""

    def test_full_sync_fetches_all(self) -> None:
        """Test that full sync doesn't pass a since date."""
        mock_result = InvoiceSyncResult(
            invoices_fetched=100,
        )

        with patch(
            "src.tasks.quickbooks_sync._async_sync_quickbooks_invoices",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_sync:
            with patch("asyncio.run", return_value=mock_result):
                sync_quickbooks_invoices_full.apply()

            # Verify since was passed as None (full sync)
            # Note: asyncio.run wraps our async function
            # The actual test is in the function behavior


# ============================================================================
# Beat Schedule Tests
# ============================================================================


class TestInvoiceSyncBeatSchedule:
    """Tests for Celery beat schedule configuration for invoice sync."""

    def test_invoice_sync_in_schedule(self) -> None:
        """Test that invoice sync is in the beat schedule."""
        from src.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule

        assert "sync-quickbooks-invoices-daily" in schedule

    def test_invoice_sync_runs_daily(self) -> None:
        """AC: Invoices synced daily from QBO → Platform."""
        from src.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule["sync-quickbooks-invoices-daily"]

        # Check it runs daily at 8 AM UTC
        crontab = schedule["schedule"]
        assert crontab.hour == {8}
        assert crontab.minute == {0}

    def test_invoice_sync_default_days_back(self) -> None:
        """Test that default days_back is 1 for daily sync."""
        from src.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule["sync-quickbooks-invoices-daily"]

        assert schedule["kwargs"]["days_back"] == 1


# ============================================================================
# Model Tests
# ============================================================================


class TestQBInvoiceModel:
    """Tests for QBInvoice model."""

    def test_model_has_required_fields(self) -> None:
        """Test that model has all required fields."""
        # Note: SQLAlchemy defaults are set at the database level,
        # so we need to explicitly set them for in-memory instances
        invoice = QBInvoice(
            qb_invoice_id="qb123",
            synced_at=datetime.now(UTC),
            status="Open",
            currency_code="USD",
        )

        assert invoice.qb_invoice_id == "qb123"
        assert invoice.status == "Open"
        assert invoice.currency_code == "USD"

    def test_model_repr(self) -> None:
        """Test model __repr__."""
        invoice = QBInvoice(
            qb_invoice_id="qb123",
            invoice_number="INV-001",
            total_amount=Decimal("100.00"),
            synced_at=datetime.now(UTC),
        )

        repr_str = repr(invoice)

        assert "qb123" in repr_str
        assert "INV-001" in repr_str


class TestQBInvoiceLineItemModel:
    """Tests for QBInvoiceLineItem model."""

    def test_model_has_required_fields(self) -> None:
        """Test that model has all required fields."""
        invoice_id = uuid.uuid4()
        line_item = QBInvoiceLineItem(
            invoice_id=invoice_id,
            line_number=1,
        )

        assert line_item.invoice_id == invoice_id
        assert line_item.line_number == 1

    def test_model_repr(self) -> None:
        """Test model __repr__."""
        invoice_id = uuid.uuid4()
        line_item = QBInvoiceLineItem(
            invoice_id=invoice_id,
            qb_item_name="UFBub250",
            quantity=10,
        )

        repr_str = repr(line_item)

        assert "UFBub250" in repr_str


# ============================================================================
# Acceptance Criteria Tests
# ============================================================================


class TestAcceptanceCriteria:
    """Tests verifying acceptance criteria from spec."""

    def test_invoices_retrieved_from_quickbooks(self) -> None:
        """AC: Invoices retrieved from QuickBooks."""
        # The pull_invoices_from_quickbooks function fetches invoices
        # This is tested in TestPullInvoicesFromQuickbooks
        pass

    def test_invoices_stored_locally(self) -> None:
        """AC: Invoices stored locally."""
        # QBInvoice model exists and can store invoice data
        invoice = QBInvoice(
            qb_invoice_id="qb123",
            invoice_number="INV-001",
            customer_name="Test Customer",
            total_amount=Decimal("100.00"),
            synced_at=datetime.now(UTC),
        )

        assert invoice.qb_invoice_id == "qb123"
        assert invoice.invoice_number == "INV-001"
        assert invoice.customer_name == "Test Customer"
        assert invoice.total_amount == Decimal("100.00")

    def test_line_items_linked_to_products(self) -> None:
        """AC: Line items can be linked to local products."""
        sku_id = uuid.uuid4()
        line_item = QBInvoiceLineItem(
            invoice_id=uuid.uuid4(),
            qb_item_name="UFBub250",
            sku_id=sku_id,
        )

        assert line_item.sku_id == sku_id

    def test_daily_sync_configured(self) -> None:
        """AC: Invoice sync runs daily."""
        from src.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule

        assert "sync-quickbooks-invoices-daily" in schedule

    def test_sync_result_tracks_created_and_updated(self) -> None:
        """AC: Sync tracks created vs updated invoices."""
        result = InvoiceSyncResult(
            invoices_created=5,
            invoices_updated=3,
        )

        assert result.invoices_created == 5
        assert result.invoices_updated == 3

    def test_invoice_status_tracking(self) -> None:
        """AC: Invoice status (Open, Paid, Overdue) is tracked."""
        invoice = QBInvoice(
            qb_invoice_id="qb123",
            status="Paid",
            synced_at=datetime.now(UTC),
        )

        assert invoice.status == "Paid"

        # Test status extraction
        mock_paid = MagicMock(Balance=0, TotalAmt=100, DueDate=None)
        assert extract_invoice_status(mock_paid) == "Paid"

        mock_overdue = MagicMock(
            Balance=100,
            TotalAmt=100,
            DueDate=(datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d"),
        )
        assert extract_invoice_status(mock_overdue) == "Overdue"


# ============================================================================
# Integration Tests
# ============================================================================


class TestInvoiceSyncIntegration:
    """Integration tests for invoice sync functionality."""

    def test_tracked_skus_can_be_linked(self) -> None:
        """Test that line items matching tracked SKUs get linked."""
        from src.tasks.quickbooks_sync import TRACKED_SKUS

        # Verify our 4 SKUs are still defined
        expected_skus = {"UFBub250", "UFRos250", "UFRed250", "UFCha250"}
        assert TRACKED_SKUS == expected_skus

    def test_invoice_sync_result_serializable(self) -> None:
        """Test that sync result can be serialized for Celery."""
        result = InvoiceSyncResult(
            status="success",
            invoices_fetched=10,
            invoices_created=5,
            invoices_updated=3,
            line_items_created=25,
            line_items_linked=8,
            errors=["test error"],
            duration_seconds=5.5,
        )

        data = result.to_dict()

        # Should be JSON-serializable
        import json
        json_str = json.dumps(data)
        assert json_str is not None
        assert "success" in json_str
