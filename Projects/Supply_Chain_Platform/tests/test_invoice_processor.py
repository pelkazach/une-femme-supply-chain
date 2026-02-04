"""Tests for Invoice extraction processor with validation.

These tests verify:
- SKU normalization and validation
- Invoice field validation (invoice_number, vendor, dates, amounts)
- Line item validation with cross-checks
- Accuracy calculation (>93% requirement)
- Integration with Azure Document Intelligence
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from src.services.invoice_processor import (
    KNOWN_VENDORS,
    SKU_ALIASES,
    VALID_SKUS,
    FieldAccuracy,
    InvoiceProcessingResult,
    InvoiceProcessor,
    ValidationIssue,
    ValidationSeverity,
    calculate_field_accuracy,
    calculate_overall_accuracy,
    normalize_line_item_skus,
    normalize_sku,
    validate_amount,
    validate_due_date,
    validate_invoice_date,
    validate_invoice_number,
    validate_invoice_totals,
    validate_line_item,
    validate_quantity,
    validate_vendor_name,
)
from src.services.document_ocr import (
    AzureDocumentIntelligenceClient,
    DocumentType,
    ExtractionResult,
    InvoiceExtraction,
    LineItem,
)


# ============================================================================
# SKU Normalization Tests
# ============================================================================


class TestNormalizeSku:
    """Tests for SKU normalization function."""

    def test_valid_sku_unchanged(self) -> None:
        """Test that valid SKUs are returned properly cased."""
        assert normalize_sku("UFBub250") == "UFBub250"
        assert normalize_sku("UFRos250") == "UFRos250"
        assert normalize_sku("UFRed250") == "UFRed250"
        assert normalize_sku("UFCha250") == "UFCha250"

    def test_valid_sku_case_insensitive(self) -> None:
        """Test that SKU matching is case-insensitive."""
        assert normalize_sku("UFBUB250") == "UFBub250"
        assert normalize_sku("ufbub250") == "UFBub250"
        assert normalize_sku("UFRoS250") == "UFRos250"

    def test_sku_alias_bubbles(self) -> None:
        """Test Bubbles SKU aliases."""
        assert normalize_sku("UF-BUB-250") == "UFBub250"
        assert normalize_sku("UFBUB250") == "UFBub250"
        assert normalize_sku("UF BUBBLES 250") == "UFBub250"
        assert normalize_sku("BUBBLES 250ML") == "UFBub250"
        assert normalize_sku("UNE FEMME BUBBLES") == "UFBub250"

    def test_sku_alias_rose(self) -> None:
        """Test Rose SKU aliases."""
        assert normalize_sku("UF-ROS-250") == "UFRos250"
        assert normalize_sku("UF ROSE 250") == "UFRos250"
        assert normalize_sku("ROSE 250ML") == "UFRos250"
        assert normalize_sku("UNE FEMME ROSE") == "UFRos250"

    def test_sku_alias_red(self) -> None:
        """Test Red SKU aliases."""
        assert normalize_sku("UF-RED-250") == "UFRed250"
        assert normalize_sku("RED 250ML") == "UFRed250"
        assert normalize_sku("UNE FEMME RED") == "UFRed250"

    def test_sku_alias_chardonnay(self) -> None:
        """Test Chardonnay SKU aliases."""
        assert normalize_sku("UF-CHA-250") == "UFCha250"
        assert normalize_sku("UF CHARDONNAY 250") == "UFCha250"
        assert normalize_sku("CHARDONNAY 250ML") == "UFCha250"
        assert normalize_sku("UNE FEMME CHARDONNAY") == "UFCha250"

    def test_unknown_sku_returns_none(self) -> None:
        """Test that unknown SKUs return None."""
        assert normalize_sku("UNKNOWN-SKU") is None
        assert normalize_sku("ABC123") is None
        assert normalize_sku("OTHER WINE") is None

    def test_empty_sku_returns_none(self) -> None:
        """Test that empty SKU returns None."""
        assert normalize_sku("") is None
        assert normalize_sku("   ") is None

    def test_whitespace_stripped(self) -> None:
        """Test that whitespace is stripped from SKUs."""
        assert normalize_sku("  UFBub250  ") == "UFBub250"
        assert normalize_sku("\tUFRos250\n") == "UFRos250"


# ============================================================================
# Validation Function Tests
# ============================================================================


class TestValidateInvoiceNumber:
    """Tests for invoice number validation."""

    def test_valid_invoice_number(self) -> None:
        """Test that valid invoice numbers pass."""
        assert validate_invoice_number("INV-2024-001") is None
        assert validate_invoice_number("12345678") is None
        assert validate_invoice_number("ABC123") is None

    def test_missing_invoice_number_error(self) -> None:
        """Test that missing invoice number is an error."""
        issue = validate_invoice_number("")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "missing" in issue.message.lower()

    def test_short_invoice_number_warning(self) -> None:
        """Test that short invoice numbers generate warning."""
        issue = validate_invoice_number("AB")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "too short" in issue.message.lower()


class TestValidateVendorName:
    """Tests for vendor name validation."""

    def test_valid_vendor_name(self) -> None:
        """Test that valid vendor names pass."""
        assert validate_vendor_name("Une Femme Wines") is None
        assert validate_vendor_name("ABC Winery LLC") is None

    def test_missing_vendor_error(self) -> None:
        """Test that missing vendor is an error."""
        issue = validate_vendor_name("")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "missing" in issue.message.lower()

    def test_short_vendor_warning(self) -> None:
        """Test that short vendor names generate warning."""
        issue = validate_vendor_name("A")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING


class TestValidateInvoiceDate:
    """Tests for invoice date validation."""

    def test_valid_invoice_date(self) -> None:
        """Test that valid dates pass."""
        yesterday = date.today() - timedelta(days=1)
        assert validate_invoice_date(yesterday) is None

    def test_today_invoice_date_valid(self) -> None:
        """Test that today's date is valid."""
        assert validate_invoice_date(date.today()) is None

    def test_missing_invoice_date_error(self) -> None:
        """Test that missing date is an error."""
        issue = validate_invoice_date(None)
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "missing" in issue.message.lower()

    def test_future_date_warning(self) -> None:
        """Test that future dates generate warning."""
        future = date.today() + timedelta(days=5)
        issue = validate_invoice_date(future)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "future" in issue.message.lower()

    def test_old_date_warning(self) -> None:
        """Test that very old dates generate warning."""
        old_date = date.today() - timedelta(days=800)
        issue = validate_invoice_date(old_date)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "2 years" in issue.message.lower()

    def test_invoice_after_due_date_warning(self) -> None:
        """Test that invoice date after due date generates warning."""
        invoice_date = date.today()
        due_date = date.today() - timedelta(days=5)
        issue = validate_invoice_date(invoice_date, due_date)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "after due date" in issue.message.lower()


class TestValidateDueDate:
    """Tests for due date validation."""

    def test_valid_due_date(self) -> None:
        """Test that valid due dates pass."""
        future = date.today() + timedelta(days=30)
        assert validate_due_date(future) is None

    def test_none_due_date_valid(self) -> None:
        """Test that None due date is valid (optional field)."""
        assert validate_due_date(None) is None

    def test_old_due_date_warning(self) -> None:
        """Test that very old due dates generate warning."""
        old_date = date.today() - timedelta(days=400)
        issue = validate_due_date(old_date)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "1 year" in issue.message.lower()

    def test_due_date_before_invoice_warning(self) -> None:
        """Test that due date before invoice date generates warning."""
        invoice_date = date.today()
        due_date = date.today() - timedelta(days=5)
        issue = validate_due_date(due_date, invoice_date)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "before invoice date" in issue.message.lower()


class TestValidateAmount:
    """Tests for amount validation."""

    def test_valid_amount(self) -> None:
        """Test that valid amounts pass."""
        assert validate_amount(100.00, "subtotal") is None
        assert validate_amount(5000.50, "total") is None
        assert validate_amount(0.00, "tax") is None

    def test_negative_amount_error(self) -> None:
        """Test that negative amounts are errors."""
        issue = validate_amount(-100.00, "total")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "negative" in issue.message.lower()

    def test_high_amount_warning(self) -> None:
        """Test that unusually high amounts generate warning."""
        issue = validate_amount(2_000_000.00, "total")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "unusually high" in issue.message.lower()


class TestValidateQuantity:
    """Tests for quantity validation."""

    def test_valid_quantity(self) -> None:
        """Test that valid quantities pass."""
        assert validate_quantity(10, "UFBub250") is None
        assert validate_quantity(1000, "UFRos250") is None

    def test_zero_quantity_error(self) -> None:
        """Test that zero quantity is an error."""
        issue = validate_quantity(0, "UFBub250")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "invalid" in issue.message.lower()

    def test_negative_quantity_error(self) -> None:
        """Test that negative quantity is an error."""
        issue = validate_quantity(-5, "UFBub250")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR

    def test_high_quantity_warning(self) -> None:
        """Test that unusually high quantities generate warning."""
        issue = validate_quantity(15000, "UFBub250")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "unusually high" in issue.message.lower()


class TestValidateLineItem:
    """Tests for line item validation."""

    def test_valid_line_item(self) -> None:
        """Test that valid line items pass."""
        item = LineItem(
            sku="UFBub250",
            description="Une Femme Bubbles 250ml",
            quantity=24,
            unit_price=5.00,
            total=120.00,
            confidence=0.95,
        )
        issues = validate_line_item(item)
        assert len(issues) == 0

    def test_unknown_sku_error(self) -> None:
        """Test that unknown SKUs generate error."""
        item = LineItem(
            sku="UNKNOWN-SKU",
            description="Unknown Wine",
            quantity=10,
            unit_price=10.00,
            total=100.00,
        )
        issues = validate_line_item(item)
        assert any(i.severity == ValidationSeverity.ERROR for i in issues)
        assert any("Unknown SKU" in i.message for i in issues)

    def test_sku_alias_info(self) -> None:
        """Test that SKU aliases generate info message."""
        item = LineItem(
            sku="UF-BUB-250",  # Alias
            description="Une Femme Bubbles",
            quantity=10,
            unit_price=5.00,
            total=50.00,
        )
        issues = validate_line_item(item)
        # Should have info about normalization
        assert any(i.severity == ValidationSeverity.INFO for i in issues)
        assert any("normalized" in i.message.lower() for i in issues)

    def test_negative_unit_price_error(self) -> None:
        """Test that negative unit price generates error."""
        item = LineItem(
            sku="UFBub250",
            description="Wine",
            quantity=10,
            unit_price=-5.00,
            total=50.00,
        )
        issues = validate_line_item(item)
        assert any(
            i.severity == ValidationSeverity.ERROR and "unit_price" in i.field
            for i in issues
        )

    def test_negative_total_error(self) -> None:
        """Test that negative total generates error."""
        item = LineItem(
            sku="UFBub250",
            description="Wine",
            quantity=10,
            unit_price=5.00,
            total=-50.00,
        )
        issues = validate_line_item(item)
        assert any(
            i.severity == ValidationSeverity.ERROR and "total" in i.field
            for i in issues
        )

    def test_total_mismatch_warning(self) -> None:
        """Test that total not matching unit_price * quantity generates warning."""
        item = LineItem(
            sku="UFBub250",
            description="Wine",
            quantity=10,
            unit_price=5.00,
            total=100.00,  # Should be 50.00
        )
        issues = validate_line_item(item)
        assert any(
            i.severity == ValidationSeverity.WARNING and "doesn't match" in i.message
            for i in issues
        )


class TestValidateInvoiceTotals:
    """Tests for invoice totals validation."""

    def test_valid_totals(self) -> None:
        """Test that valid totals pass."""
        extraction = InvoiceExtraction(
            invoice_number="INV-001",
            vendor_name="Vendor",
            invoice_date=date.today(),
            line_items=[
                LineItem(sku="UFBub250", description="Wine", quantity=10, total=100.00)
            ],
            subtotal=100.00,
            tax=8.00,
            total=108.00,
            confidence=0.95,
        )
        issues = validate_invoice_totals(extraction)
        assert len(issues) == 0

    def test_negative_subtotal_error(self) -> None:
        """Test that negative subtotal generates error."""
        extraction = InvoiceExtraction(
            invoice_number="INV-001",
            vendor_name="Vendor",
            invoice_date=date.today(),
            subtotal=-100.00,
            total=0.00,
        )
        issues = validate_invoice_totals(extraction)
        assert any(i.severity == ValidationSeverity.ERROR for i in issues)

    def test_subtotal_mismatch_warning(self) -> None:
        """Test that subtotal not matching line items generates warning."""
        extraction = InvoiceExtraction(
            invoice_number="INV-001",
            vendor_name="Vendor",
            invoice_date=date.today(),
            line_items=[
                LineItem(sku="UFBub250", description="Wine", quantity=10, total=100.00)
            ],
            subtotal=150.00,  # Should be 100.00
            total=158.00,
        )
        issues = validate_invoice_totals(extraction)
        assert any(
            i.severity == ValidationSeverity.WARNING
            and "doesn't match line items" in i.message
            for i in issues
        )

    def test_total_mismatch_warning(self) -> None:
        """Test that total not matching subtotal + tax generates warning."""
        extraction = InvoiceExtraction(
            invoice_number="INV-001",
            vendor_name="Vendor",
            invoice_date=date.today(),
            subtotal=100.00,
            tax=8.00,
            total=200.00,  # Should be 108.00
        )
        issues = validate_invoice_totals(extraction)
        assert any(
            i.severity == ValidationSeverity.WARNING
            and "doesn't match subtotal + tax" in i.message
            for i in issues
        )


# ============================================================================
# Accuracy Calculation Tests
# ============================================================================


class TestFieldAccuracy:
    """Tests for field accuracy calculation."""

    def test_calculate_field_accuracy_complete(self) -> None:
        """Test accuracy calculation for complete extraction."""
        extraction = InvoiceExtraction(
            invoice_number="INV-2024-001",
            vendor_name="Une Femme Wines",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[
                LineItem(
                    sku="UFBub250",
                    description="Bubbles",
                    quantity=24,
                    unit_price=5.00,
                    total=120.00,
                    confidence=0.95,
                )
            ],
            subtotal=120.00,
            tax=9.60,
            total=129.60,
            confidence=0.95,
        )
        accuracies = calculate_field_accuracy(extraction)

        # Should have base fields + line item fields
        assert len(accuracies) >= 7  # invoice_number, vendor, dates, subtotal, tax, total

        # All fields should be extracted
        base_fields = [
            a for a in accuracies
            if not a.field_name.startswith("line_item_")
        ]
        assert all(acc.extracted for acc in base_fields)

    def test_calculate_field_accuracy_missing_optional(self) -> None:
        """Test accuracy calculation with missing optional fields."""
        extraction = InvoiceExtraction(
            invoice_number="INV-2024-001",
            vendor_name="Une Femme Wines",
            invoice_date=date.today(),
            due_date=None,  # Optional
            subtotal=100.00,
            tax=None,  # Optional
            total=100.00,
            confidence=0.90,
        )
        accuracies = calculate_field_accuracy(extraction)

        # due_date not extracted
        due_date_acc = next(a for a in accuracies if a.field_name == "due_date")
        assert due_date_acc.extracted is False
        assert due_date_acc.validated is True  # Optional field

        # tax not extracted
        tax_acc = next(a for a in accuracies if a.field_name == "tax")
        assert tax_acc.extracted is False
        assert tax_acc.validated is True  # Optional field

    def test_calculate_field_accuracy_missing_required(self) -> None:
        """Test accuracy calculation with missing required fields."""
        extraction = InvoiceExtraction(
            invoice_number="",  # Missing
            vendor_name="Une Femme Wines",
            invoice_date=None,  # Missing
            subtotal=0.0,
            total=0.0,
            confidence=0.80,
        )
        accuracies = calculate_field_accuracy(extraction)

        # invoice_number not extracted
        invoice_acc = next(a for a in accuracies if a.field_name == "invoice_number")
        assert invoice_acc.extracted is False

        # invoice_date not extracted
        date_acc = next(a for a in accuracies if a.field_name == "invoice_date")
        assert date_acc.extracted is False


class TestOverallAccuracy:
    """Tests for overall accuracy calculation."""

    def test_high_accuracy_extraction(self) -> None:
        """Test that complete extraction yields high accuracy."""
        extraction = InvoiceExtraction(
            invoice_number="INV-2024-001",
            vendor_name="Une Femme Wines LLC",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[
                LineItem(
                    sku="UFBub250",
                    description="Bubbles 250ml",
                    quantity=24,
                    unit_price=5.00,
                    total=120.00,
                    confidence=0.96,
                )
            ],
            subtotal=120.00,
            tax=9.60,
            total=129.60,
            confidence=0.96,
        )
        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        # Should be high accuracy
        assert accuracy > 0.90

    def test_low_accuracy_missing_fields(self) -> None:
        """Test that missing fields yield lower accuracy."""
        extraction = InvoiceExtraction(
            invoice_number="",
            vendor_name="",
            invoice_date=None,
            subtotal=0.0,
            total=0.0,
            confidence=0.5,
        )
        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        # Should be low accuracy
        assert accuracy < 0.30

    def test_empty_accuracies_returns_zero(self) -> None:
        """Test that empty accuracies list returns 0."""
        extraction = InvoiceExtraction(
            invoice_number="INV-001",
            vendor_name="Vendor",
            invoice_date=date.today(),
            subtotal=100.0,
            total=100.0,
        )
        accuracy = calculate_overall_accuracy(extraction, [])
        assert accuracy == 0.0

    def test_accuracy_above_93_threshold(self) -> None:
        """Test meeting the >93% accuracy requirement."""
        extraction = InvoiceExtraction(
            invoice_number="INV-2024-00123",
            vendor_name="Une Femme Wines LLC",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[
                LineItem(
                    sku="UFBub250",
                    description="Une Femme Bubbles 250ml - 24 pack",
                    quantity=24,
                    unit_price=5.00,
                    total=120.00,
                    confidence=0.96,
                ),
                LineItem(
                    sku="UFRos250",
                    description="Une Femme Rose 250ml - 24 pack",
                    quantity=24,
                    unit_price=5.50,
                    total=132.00,
                    confidence=0.96,
                ),
            ],
            subtotal=252.00,
            tax=20.16,
            total=272.16,
            confidence=0.96,
        )
        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        # Should meet the >93% requirement
        assert accuracy > 0.93


# ============================================================================
# SKU Normalization in Extraction Tests
# ============================================================================


class TestNormalizeLineItemSkus:
    """Tests for SKU normalization in invoice extraction."""

    def test_normalize_alias_sku(self) -> None:
        """Test that alias SKUs are normalized."""
        extraction = InvoiceExtraction(
            invoice_number="INV-001",
            vendor_name="Vendor",
            invoice_date=date.today(),
            line_items=[
                LineItem(
                    sku="UF-BUB-250",  # Alias
                    description="Bubbles",
                    quantity=10,
                    confidence=0.95,
                )
            ],
            subtotal=50.0,
            total=50.0,
        )
        corrected, issues = normalize_line_item_skus(extraction)

        assert corrected.line_items[0].sku == "UFBub250"
        assert len(issues) == 1
        assert issues[0].severity == ValidationSeverity.INFO

    def test_normalize_preserves_valid_sku(self) -> None:
        """Test that valid SKUs are not changed."""
        extraction = InvoiceExtraction(
            invoice_number="INV-001",
            vendor_name="Vendor",
            invoice_date=date.today(),
            line_items=[
                LineItem(
                    sku="UFBub250",  # Already valid
                    description="Bubbles",
                    quantity=10,
                    confidence=0.95,
                )
            ],
            subtotal=50.0,
            total=50.0,
        )
        corrected, issues = normalize_line_item_skus(extraction)

        assert corrected.line_items[0].sku == "UFBub250"
        assert len(issues) == 0

    def test_normalize_preserves_other_fields(self) -> None:
        """Test that normalization preserves other fields."""
        extraction = InvoiceExtraction(
            invoice_number="INV-2024-001",
            vendor_name="Une Femme Wines",
            invoice_date=date(2024, 1, 15),
            due_date=date(2024, 2, 15),
            line_items=[
                LineItem(
                    sku="UF-ROS-250",
                    description="Rose Wine",
                    quantity=24,
                    unit_price=5.00,
                    total=120.00,
                    confidence=0.92,
                )
            ],
            subtotal=120.00,
            tax=9.60,
            total=129.60,
            confidence=0.92,
        )
        corrected, _ = normalize_line_item_skus(extraction)

        assert corrected.invoice_number == "INV-2024-001"
        assert corrected.vendor_name == "Une Femme Wines"
        assert corrected.invoice_date == date(2024, 1, 15)
        assert corrected.due_date == date(2024, 2, 15)
        assert corrected.line_items[0].sku == "UFRos250"
        assert corrected.line_items[0].quantity == 24
        assert corrected.subtotal == 120.00
        assert corrected.total == 129.60


# ============================================================================
# InvoiceProcessor Integration Tests
# ============================================================================


class TestInvoiceProcessor:
    """Tests for the InvoiceProcessor class."""

    @pytest.fixture
    def mock_ocr_client(self) -> MagicMock:
        """Create a mock OCR client."""
        client = MagicMock(spec=AzureDocumentIntelligenceClient)
        return client

    @pytest.fixture
    def processor(self, mock_ocr_client: MagicMock) -> InvoiceProcessor:
        """Create a processor with mock OCR client."""
        return InvoiceProcessor(ocr_client=mock_ocr_client)

    def test_process_invoice_success(
        self, processor: InvoiceProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test successful invoice processing."""
        extraction = InvoiceExtraction(
            invoice_number="INV-2024-001",
            vendor_name="Une Femme Wines",
            invoice_date=date(2024, 1, 15),
            due_date=date(2024, 2, 15),
            line_items=[
                LineItem(
                    sku="UFBub250",
                    description="Bubbles",
                    quantity=24,
                    unit_price=5.00,
                    total=120.00,
                    confidence=0.95,
                )
            ],
            subtotal=120.00,
            tax=9.60,
            total=129.60,
            confidence=0.95,
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.INVOICE,
            extraction=extraction,
            success=True,
            processing_time_ms=150.0,
        )

        result = processor.process_invoice(b"test pdf content")

        assert result.success is True
        assert result.extraction.invoice_number == "INV-2024-001"
        assert result.extraction.total == 129.60
        assert len(result.field_accuracies) > 0
        assert result.overall_accuracy > 0

    def test_process_invoice_ocr_failure(
        self, processor: InvoiceProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test handling of OCR failure."""
        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.INVOICE,
            extraction=InvoiceExtraction(
                invoice_number="",
                vendor_name="",
                invoice_date=None,
                needs_review=True,
            ),
            success=False,
            error_message="OCR service unavailable",
        )

        result = processor.process_invoice(b"test")

        assert result.success is False
        assert result.error_message == "OCR service unavailable"

    def test_process_invoice_validation_issues(
        self, processor: InvoiceProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test that validation issues are captured."""
        extraction = InvoiceExtraction(
            invoice_number="",  # Missing - should be error
            vendor_name="Une Femme Wines",
            invoice_date=date.today(),
            line_items=[
                LineItem(
                    sku="UNKNOWN-SKU",  # Unknown - should be error
                    description="Wine",
                    quantity=10,
                    total=100.00,
                )
            ],
            subtotal=100.00,
            total=100.00,
            confidence=0.90,
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.INVOICE,
            extraction=extraction,
            success=True,
        )

        result = processor.process_invoice(b"test")

        assert result.success is True
        assert result.has_errors is True
        assert len(result.validation_issues) >= 2

    def test_process_invoice_auto_normalize_sku(
        self, processor: InvoiceProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test automatic SKU normalization."""
        extraction = InvoiceExtraction(
            invoice_number="INV-001",
            vendor_name="Vendor",
            invoice_date=date.today(),
            line_items=[
                LineItem(
                    sku="UF-BUB-250",  # Alias
                    description="Bubbles",
                    quantity=10,
                    total=50.00,
                    confidence=0.95,
                )
            ],
            subtotal=50.00,
            total=50.00,
            confidence=0.95,
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.INVOICE,
            extraction=extraction,
            success=True,
        )

        result = processor.process_invoice(b"test")

        # SKU should be normalized
        assert result.extraction.line_items[0].sku == "UFBub250"

    def test_process_invoice_disable_auto_normalize(
        self, mock_ocr_client: MagicMock
    ) -> None:
        """Test disabling automatic SKU normalization."""
        processor = InvoiceProcessor(
            ocr_client=mock_ocr_client,
            auto_normalize_skus=False,
        )

        extraction = InvoiceExtraction(
            invoice_number="INV-001",
            vendor_name="Vendor",
            invoice_date=date.today(),
            line_items=[
                LineItem(
                    sku="UF-BUB-250",  # Won't be normalized
                    description="Bubbles",
                    quantity=10,
                    total=50.00,
                    confidence=0.95,
                )
            ],
            subtotal=50.00,
            total=50.00,
            confidence=0.95,
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.INVOICE,
            extraction=extraction,
            success=True,
        )

        result = processor.process_invoice(b"test")

        # SKU should NOT be normalized
        assert result.extraction.line_items[0].sku == "UF-BUB-250"

    def test_process_invoice_needs_review_low_accuracy(
        self, processor: InvoiceProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test that low accuracy triggers review flag."""
        extraction = InvoiceExtraction(
            invoice_number="I",  # Short
            vendor_name="V",  # Short
            invoice_date=date.today(),
            subtotal=0.0,
            total=0.0,
            confidence=0.50,  # Low confidence
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.INVOICE,
            extraction=extraction,
            success=True,
        )

        result = processor.process_invoice(b"test")

        assert result.needs_review is True

    def test_process_invoice_exception_handling(
        self, processor: InvoiceProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test exception handling during processing."""
        mock_ocr_client.analyze_document.side_effect = Exception("Unexpected error")

        result = processor.process_invoice(b"test")

        assert result.success is False
        assert "Unexpected error" in str(result.error_message)

    def test_get_valid_skus(self, processor: InvoiceProcessor) -> None:
        """Test getting valid SKUs."""
        skus = processor.get_valid_skus()
        assert skus == VALID_SKUS
        assert "UFBub250" in skus
        assert "UFRos250" in skus

    def test_get_sku_aliases(self, processor: InvoiceProcessor) -> None:
        """Test getting SKU aliases."""
        aliases = processor.get_sku_aliases()
        assert aliases == SKU_ALIASES
        assert "UF-BUB-250" in aliases

    def test_get_known_vendors(self, processor: InvoiceProcessor) -> None:
        """Test getting known vendors."""
        vendors = processor.get_known_vendors()
        assert vendors == KNOWN_VENDORS
        assert "UNE FEMME WINES" in vendors


# ============================================================================
# InvoiceProcessingResult Tests
# ============================================================================


class TestInvoiceProcessingResult:
    """Tests for InvoiceProcessingResult data class."""

    def test_has_errors_true(self) -> None:
        """Test has_errors returns True when errors exist."""
        result = InvoiceProcessingResult(
            extraction=InvoiceExtraction(
                invoice_number="",
                vendor_name="",
                invoice_date=None,
            ),
            validation_issues=[
                ValidationIssue(
                    field="invoice_number",
                    message="Missing",
                    severity=ValidationSeverity.ERROR,
                )
            ],
        )
        assert result.has_errors is True

    def test_has_errors_false(self) -> None:
        """Test has_errors returns False when no errors."""
        result = InvoiceProcessingResult(
            extraction=InvoiceExtraction(
                invoice_number="INV-001",
                vendor_name="Vendor",
                invoice_date=date.today(),
                subtotal=100.0,
                total=100.0,
            ),
            validation_issues=[
                ValidationIssue(
                    field="due_date",
                    message="Missing",
                    severity=ValidationSeverity.WARNING,
                )
            ],
        )
        assert result.has_errors is False

    def test_has_warnings_true(self) -> None:
        """Test has_warnings returns True when warnings exist."""
        result = InvoiceProcessingResult(
            extraction=InvoiceExtraction(
                invoice_number="IN",
                vendor_name="V",
                invoice_date=date.today(),
                subtotal=100.0,
                total=100.0,
            ),
            validation_issues=[
                ValidationIssue(
                    field="invoice_number",
                    message="Too short",
                    severity=ValidationSeverity.WARNING,
                )
            ],
        )
        assert result.has_warnings is True

    def test_valid_line_items(self) -> None:
        """Test valid_line_items property filters correctly."""
        result = InvoiceProcessingResult(
            extraction=InvoiceExtraction(
                invoice_number="INV-001",
                vendor_name="Vendor",
                invoice_date=date.today(),
                line_items=[
                    LineItem(sku="UFBub250", description="Wine", quantity=10),
                    LineItem(sku="UNKNOWN", description="Other", quantity=5),
                    LineItem(sku="UFRos250", description="Wine", quantity=10),
                ],
                subtotal=250.0,
                total=250.0,
            ),
        )
        valid = result.valid_line_items
        assert len(valid) == 2
        assert all(item.sku in VALID_SKUS for item in valid)


# ============================================================================
# Integration Tests with Real Patterns
# ============================================================================


class TestRealWorldPatterns:
    """Tests with real-world invoice patterns."""

    def test_wine_shipment_invoice(self) -> None:
        """Test processing typical wine shipment invoice."""
        extraction = InvoiceExtraction(
            invoice_number="INV-UF-2024-00789",
            vendor_name="Une Femme Wines LLC",
            invoice_date=date.today() - timedelta(days=5),
            due_date=date.today() + timedelta(days=25),
            line_items=[
                LineItem(
                    sku="UFBub250",
                    description="Une Femme Bubbles 250ml - Case of 24",
                    quantity=48,
                    unit_price=5.00,
                    total=240.00,
                    confidence=0.96,
                ),
                LineItem(
                    sku="UFRos250",
                    description="Une Femme Rose 250ml - Case of 24",
                    quantity=24,
                    unit_price=5.50,
                    total=132.00,
                    confidence=0.96,
                ),
            ],
            subtotal=372.00,
            tax=29.76,
            total=401.76,
            confidence=0.96,
        )

        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        assert accuracy > 0.93

    def test_distributor_invoice(self) -> None:
        """Test processing distributor-style invoice."""
        extraction = InvoiceExtraction(
            invoice_number="RNDC-2024-01234",
            vendor_name="Republic National Distributing Company",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=[
                LineItem(
                    sku="UFCha250",
                    description="Une Femme Chardonnay",
                    quantity=96,
                    unit_price=4.75,
                    total=456.00,
                    confidence=0.94,
                )
            ],
            subtotal=456.00,
            tax=36.48,
            total=492.48,
            confidence=0.94,
        )

        issues: list[ValidationIssue] = []
        invoice_issue = validate_invoice_number(extraction.invoice_number)
        if invoice_issue:
            issues.append(invoice_issue)

        vendor_issue = validate_vendor_name(extraction.vendor_name)
        if vendor_issue:
            issues.append(vendor_issue)

        # No errors expected
        assert not any(i.severity == ValidationSeverity.ERROR for i in issues)

    def test_scan_quality_invoice_low_confidence(self) -> None:
        """Test invoice with potential OCR issues (poor scan quality)."""
        extraction = InvoiceExtraction(
            invoice_number="INV-001",  # Short due to OCR issues
            vendor_name="Une Femme",
            invoice_date=date.today(),
            line_items=[
                LineItem(
                    sku="UF",  # Incomplete due to OCR
                    description="Wine",
                    quantity=10,
                    total=50.00,
                    confidence=0.65,
                )
            ],
            subtotal=50.00,
            total=50.00,
            confidence=0.70,
        )

        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        # Should be below threshold due to low confidence
        assert accuracy < 0.93

    def test_multi_page_invoice(self) -> None:
        """Test invoice with multiple line items (multi-page scenario)."""
        line_items = [
            LineItem(
                sku="UFBub250",
                description=f"Bubbles - Order Line {i}",
                quantity=24,
                unit_price=5.00,
                total=120.00,
                confidence=0.95,
            )
            for i in range(5)
        ]

        extraction = InvoiceExtraction(
            invoice_number="INV-MULTI-2024-001",
            vendor_name="Une Femme Wines",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            line_items=line_items,
            subtotal=600.00,
            tax=48.00,
            total=648.00,
            confidence=0.95,
        )

        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        # Should still meet accuracy threshold
        assert accuracy > 0.93


# ============================================================================
# Constants Tests
# ============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_valid_skus_contains_all_products(self) -> None:
        """Test VALID_SKUS contains all Une Femme products."""
        assert "UFBub250" in VALID_SKUS
        assert "UFRos250" in VALID_SKUS
        assert "UFRed250" in VALID_SKUS
        assert "UFCha250" in VALID_SKUS
        assert len(VALID_SKUS) == 4

    def test_valid_skus_is_frozenset(self) -> None:
        """Test VALID_SKUS is immutable."""
        assert isinstance(VALID_SKUS, frozenset)

    def test_sku_aliases_maps_to_valid_skus(self) -> None:
        """Test all alias values are valid SKUs."""
        for alias, normalized in SKU_ALIASES.items():
            assert (
                normalized in VALID_SKUS
            ), f"Alias '{alias}' maps to invalid SKU '{normalized}'"

    def test_sku_aliases_keys_uppercase(self) -> None:
        """Test all alias keys are uppercase."""
        for alias in SKU_ALIASES:
            assert alias == alias.upper(), f"Alias '{alias}' is not uppercase"

    def test_known_vendors_contains_major_vendors(self) -> None:
        """Test KNOWN_VENDORS contains major wine vendors."""
        assert "UNE FEMME WINES" in KNOWN_VENDORS
        assert "RNDC" in KNOWN_VENDORS
        assert "SOUTHERN GLAZERS" in KNOWN_VENDORS
        assert "WINEBOW" in KNOWN_VENDORS

    def test_known_vendors_is_frozenset(self) -> None:
        """Test KNOWN_VENDORS is immutable."""
        assert isinstance(KNOWN_VENDORS, frozenset)
