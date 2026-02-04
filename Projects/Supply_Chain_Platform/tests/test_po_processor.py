"""Tests for PO extraction processor with validation.

These tests verify:
- SKU normalization and validation
- PO field validation (po_number, vendor, dates, totals)
- Line item validation
- Accuracy calculation (>93% requirement)
- Integration with Azure Document Intelligence
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.services.document_ocr import (
    AzureDocumentIntelligenceClient,
    DocumentType,
    ExtractionResult,
    LineItem,
    PurchaseOrderExtraction,
)
from src.services.po_processor import (
    VALID_SKUS,
    SKU_ALIASES,
    FieldAccuracy,
    POProcessingResult,
    POProcessor,
    ValidationIssue,
    ValidationSeverity,
    calculate_field_accuracy,
    calculate_overall_accuracy,
    normalize_line_item_skus,
    normalize_sku,
    validate_line_item,
    validate_order_date,
    validate_po_number,
    validate_po_totals,
    validate_quantity,
    validate_vendor_name,
)


# ============================================================================
# SKU Normalization Tests
# ============================================================================


class TestNormalizeSku:
    """Tests for SKU normalization function."""

    def test_valid_sku_unchanged(self) -> None:
        """Test that valid SKUs are returned unchanged."""
        assert normalize_sku("UFBub250") == "UFBub250"
        assert normalize_sku("UFRos250") == "UFRos250"
        assert normalize_sku("UFRed250") == "UFRed250"
        assert normalize_sku("UFCha250") == "UFCha250"

    def test_valid_sku_case_insensitive(self) -> None:
        """Test that SKU matching is case-insensitive."""
        assert normalize_sku("ufbub250") == "UFBub250"
        assert normalize_sku("UFBUB250") == "UFBub250"
        assert normalize_sku("UfBuB250") == "UFBub250"

    def test_sku_alias_bubble(self) -> None:
        """Test bubble SKU aliases."""
        assert normalize_sku("UF-BUB-250") == "UFBub250"
        assert normalize_sku("UF BUB 250") == "UFBub250"
        assert normalize_sku("BUBBLES 250ML") == "UFBub250"
        assert normalize_sku("UNE FEMME BUBBLES") == "UFBub250"

    def test_sku_alias_rose(self) -> None:
        """Test rose SKU aliases."""
        assert normalize_sku("UF-ROS-250") == "UFRos250"
        assert normalize_sku("UF ROSE 250") == "UFRos250"
        assert normalize_sku("ROSE 250ML") == "UFRos250"

    def test_sku_alias_red(self) -> None:
        """Test red SKU aliases."""
        assert normalize_sku("UF-RED-250") == "UFRed250"
        assert normalize_sku("RED 250ML") == "UFRed250"

    def test_sku_alias_chardonnay(self) -> None:
        """Test chardonnay SKU aliases."""
        assert normalize_sku("UF-CHA-250") == "UFCha250"
        assert normalize_sku("CHARDONNAY 250ML") == "UFCha250"

    def test_invalid_sku_returns_none(self) -> None:
        """Test that invalid SKUs return None."""
        assert normalize_sku("INVALID") is None
        assert normalize_sku("UF-XXX-250") is None
        assert normalize_sku("") is None

    def test_empty_sku_returns_none(self) -> None:
        """Test that empty/None SKUs return None."""
        assert normalize_sku("") is None
        assert normalize_sku("   ") is None

    def test_whitespace_stripped(self) -> None:
        """Test that whitespace is stripped from SKUs."""
        assert normalize_sku("  UFBub250  ") == "UFBub250"
        assert normalize_sku("\tUFRos250\n") == "UFRos250"


# ============================================================================
# Validation Function Tests
# ============================================================================


class TestValidatePONumber:
    """Tests for PO number validation."""

    def test_valid_po_number(self) -> None:
        """Test that valid PO numbers pass."""
        assert validate_po_number("PO-2024-001") is None
        assert validate_po_number("12345") is None
        assert validate_po_number("ABC") is None

    def test_missing_po_number_error(self) -> None:
        """Test that missing PO number is an error."""
        issue = validate_po_number("")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "missing" in issue.message.lower()

    def test_short_po_number_warning(self) -> None:
        """Test that short PO numbers generate warning."""
        issue = validate_po_number("AB")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "too short" in issue.message.lower()


class TestValidateVendorName:
    """Tests for vendor name validation."""

    def test_valid_vendor_name(self) -> None:
        """Test that valid vendor names pass."""
        assert validate_vendor_name("RNDC Distribution") is None
        assert validate_vendor_name("Wine Supplier Co") is None

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


class TestValidateOrderDate:
    """Tests for order date validation."""

    def test_valid_order_date(self) -> None:
        """Test that valid dates pass."""
        yesterday = date.today() - timedelta(days=1)
        assert validate_order_date(yesterday) is None

    def test_missing_order_date_warning(self) -> None:
        """Test that missing date is a warning."""
        issue = validate_order_date(None)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "missing" in issue.message.lower()

    def test_future_date_warning(self) -> None:
        """Test that future dates generate warning."""
        future = date.today() + timedelta(days=7)
        issue = validate_order_date(future)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "future" in issue.message.lower()

    def test_old_date_warning(self) -> None:
        """Test that very old dates generate warning."""
        old_date = date.today() - timedelta(days=800)
        issue = validate_order_date(old_date)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "2 years" in issue.message.lower()

    def test_order_after_delivery_warning(self) -> None:
        """Test that order date after delivery generates warning."""
        order = date(2024, 2, 15)
        delivery = date(2024, 2, 10)
        issue = validate_order_date(order, delivery)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "after delivery" in issue.message.lower()

    def test_order_before_delivery_valid(self) -> None:
        """Test that order before delivery is valid."""
        # Use recent dates to avoid "too old" warning
        order = date.today() - timedelta(days=7)
        delivery = date.today() + timedelta(days=7)
        assert validate_order_date(order, delivery) is None


class TestValidateQuantity:
    """Tests for quantity validation."""

    def test_valid_quantity(self) -> None:
        """Test that valid quantities pass."""
        assert validate_quantity(100, "UFBub250") is None
        assert validate_quantity(1, "UFRos250") is None
        assert validate_quantity(10000, "UFRed250") is None

    def test_zero_quantity_error(self) -> None:
        """Test that zero quantity is an error."""
        issue = validate_quantity(0, "UFBub250")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR

    def test_negative_quantity_error(self) -> None:
        """Test that negative quantity is an error."""
        issue = validate_quantity(-10, "UFBub250")
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
            description="Bubbles",
            quantity=100,
            unit_price=10.0,
            total=1000.0,
            confidence=0.95,
        )
        issues = validate_line_item(item)
        assert len(issues) == 0

    def test_invalid_sku_error(self) -> None:
        """Test that invalid SKU generates error."""
        item = LineItem(sku="INVALID", description="Test", quantity=10)
        issues = validate_line_item(item)
        assert len(issues) >= 1
        assert any(i.severity == ValidationSeverity.ERROR for i in issues)

    def test_sku_normalized_info(self) -> None:
        """Test that normalized SKU generates info."""
        item = LineItem(sku="UF-BUB-250", description="Test", quantity=10)
        issues = validate_line_item(item)
        assert any(i.severity == ValidationSeverity.INFO for i in issues)

    def test_negative_unit_price_error(self) -> None:
        """Test that negative unit price is error."""
        item = LineItem(
            sku="UFBub250",
            description="Test",
            quantity=10,
            unit_price=-5.0,
        )
        issues = validate_line_item(item)
        assert any(
            i.severity == ValidationSeverity.ERROR and "unit_price" in i.field
            for i in issues
        )

    def test_negative_total_error(self) -> None:
        """Test that negative total is error."""
        item = LineItem(
            sku="UFBub250",
            description="Test",
            quantity=10,
            total=-100.0,
        )
        issues = validate_line_item(item)
        assert any(
            i.severity == ValidationSeverity.ERROR and "total" in i.field
            for i in issues
        )

    def test_total_mismatch_warning(self) -> None:
        """Test that total mismatch generates warning."""
        item = LineItem(
            sku="UFBub250",
            description="Test",
            quantity=10,
            unit_price=10.0,
            total=150.0,  # Should be 100
        )
        issues = validate_line_item(item)
        assert any(
            i.severity == ValidationSeverity.WARNING and "doesn't match" in i.message
            for i in issues
        )


class TestValidatePOTotals:
    """Tests for PO total validation."""

    def test_valid_totals(self) -> None:
        """Test that valid totals pass."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-001",
            vendor_name="Vendor",
            order_date=date.today(),
            line_items=[
                LineItem(sku="UFBub250", description="Test", quantity=10, total=100.0)
            ],
            subtotal=100.0,
            tax=8.5,
            total=108.5,
        )
        issues = validate_po_totals(extraction)
        assert len(issues) == 0

    def test_negative_subtotal_error(self) -> None:
        """Test that negative subtotal is error."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-001",
            vendor_name="Vendor",
            order_date=date.today(),
            subtotal=-100.0,
            total=100.0,
        )
        issues = validate_po_totals(extraction)
        assert any(i.severity == ValidationSeverity.ERROR for i in issues)

    def test_negative_total_error(self) -> None:
        """Test that negative total is error."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-001",
            vendor_name="Vendor",
            order_date=date.today(),
            total=-100.0,
        )
        issues = validate_po_totals(extraction)
        assert any(i.severity == ValidationSeverity.ERROR for i in issues)


# ============================================================================
# Accuracy Calculation Tests
# ============================================================================


class TestFieldAccuracy:
    """Tests for field accuracy calculation."""

    def test_calculate_field_accuracy_complete(self) -> None:
        """Test accuracy calculation for complete extraction."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-001",
            vendor_name="Vendor",
            order_date=date.today(),
            delivery_date=date.today() + timedelta(days=7),
            line_items=[
                LineItem(
                    sku="UFBub250",
                    description="Test",
                    quantity=100,
                    confidence=0.95,
                )
            ],
            total=1000.0,
            confidence=0.95,
        )
        accuracies = calculate_field_accuracy(extraction)

        # Should have: po_number, vendor_name, order_date, delivery_date,
        # line_item_0_sku, line_item_0_quantity, total
        assert len(accuracies) == 7

        # All fields should be extracted
        assert all(acc.extracted for acc in accuracies)

    def test_calculate_field_accuracy_missing_fields(self) -> None:
        """Test accuracy calculation with missing fields."""
        extraction = PurchaseOrderExtraction(
            po_number="",  # Missing
            vendor_name="Vendor",
            order_date=None,  # Missing
            total=0.0,  # Missing
            confidence=0.80,
        )
        accuracies = calculate_field_accuracy(extraction)

        # po_number not extracted
        po_acc = next(a for a in accuracies if a.field_name == "po_number")
        assert po_acc.extracted is False

        # order_date not extracted
        date_acc = next(a for a in accuracies if a.field_name == "order_date")
        assert date_acc.extracted is False


class TestOverallAccuracy:
    """Tests for overall accuracy calculation."""

    def test_high_accuracy_extraction(self) -> None:
        """Test that complete extraction yields high accuracy."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-001",
            vendor_name="Vendor",
            order_date=date.today(),
            line_items=[
                LineItem(
                    sku="UFBub250",
                    description="Test",
                    quantity=100,
                    confidence=0.95,
                )
            ],
            total=1000.0,
            confidence=0.95,
        )
        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        # Should be reasonably high accuracy (above 80%)
        # Note: delivery_date is optional but not extracted, which lowers score
        assert accuracy > 0.80

    def test_low_accuracy_missing_fields(self) -> None:
        """Test that missing fields yield lower accuracy."""
        extraction = PurchaseOrderExtraction(
            po_number="",
            vendor_name="",
            order_date=None,
            total=0.0,
            confidence=0.5,
        )
        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        # Should be low accuracy
        assert accuracy < 0.50

    def test_empty_accuracies_returns_zero(self) -> None:
        """Test that empty accuracies list returns 0."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-001",
            vendor_name="Vendor",
            order_date=None,
        )
        accuracy = calculate_overall_accuracy(extraction, [])
        assert accuracy == 0.0

    def test_accuracy_above_93_threshold(self) -> None:
        """Test meeting the >93% accuracy requirement."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-2024-001",
            vendor_name="RNDC Distribution",
            order_date=date.today(),
            delivery_date=date.today() + timedelta(days=10),
            line_items=[
                LineItem(
                    sku="UFBub250",
                    description="Bubbles 250ml",
                    quantity=100,
                    unit_price=10.0,
                    total=1000.0,
                    confidence=0.96,
                ),
                LineItem(
                    sku="UFRos250",
                    description="Rose 250ml",
                    quantity=50,
                    unit_price=10.0,
                    total=500.0,
                    confidence=0.94,
                ),
            ],
            subtotal=1500.0,
            total=1500.0,
            confidence=0.95,
        )
        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        # Should meet the >93% requirement
        assert accuracy > 0.93


# ============================================================================
# SKU Normalization Tests
# ============================================================================


class TestNormalizeLineItemSkus:
    """Tests for line item SKU normalization."""

    def test_normalize_valid_skus_unchanged(self) -> None:
        """Test that valid SKUs are not changed."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-001",
            vendor_name="Vendor",
            order_date=date.today(),
            line_items=[
                LineItem(sku="UFBub250", description="Test", quantity=10)
            ],
        )
        corrected, issues = normalize_line_item_skus(extraction)

        assert corrected.line_items[0].sku == "UFBub250"
        assert len(issues) == 0

    def test_normalize_alias_skus(self) -> None:
        """Test that alias SKUs are normalized."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-001",
            vendor_name="Vendor",
            order_date=date.today(),
            line_items=[
                LineItem(sku="UF-BUB-250", description="Test", quantity=10)
            ],
        )
        corrected, issues = normalize_line_item_skus(extraction)

        assert corrected.line_items[0].sku == "UFBub250"
        assert len(issues) == 1
        assert issues[0].severity == ValidationSeverity.INFO

    def test_normalize_preserves_other_fields(self) -> None:
        """Test that normalization preserves other line item fields."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-001",
            vendor_name="Vendor",
            order_date=date.today(),
            line_items=[
                LineItem(
                    sku="UF-ROS-250",
                    description="Rose Wine",
                    quantity=50,
                    unit_price=12.0,
                    total=600.0,
                    confidence=0.92,
                )
            ],
        )
        corrected, _ = normalize_line_item_skus(extraction)

        item = corrected.line_items[0]
        assert item.sku == "UFRos250"
        assert item.description == "Rose Wine"
        assert item.quantity == 50
        assert item.unit_price == 12.0
        assert item.total == 600.0
        assert item.confidence == 0.92


# ============================================================================
# POProcessor Integration Tests
# ============================================================================


class TestPOProcessor:
    """Tests for the POProcessor class."""

    @pytest.fixture
    def mock_ocr_client(self) -> MagicMock:
        """Create a mock OCR client."""
        client = MagicMock(spec=AzureDocumentIntelligenceClient)
        return client

    @pytest.fixture
    def processor(self, mock_ocr_client: MagicMock) -> POProcessor:
        """Create a processor with mock OCR client."""
        return POProcessor(ocr_client=mock_ocr_client)

    def test_process_po_success(
        self, processor: POProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test successful PO processing."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-2024-001",
            vendor_name="RNDC Distribution",
            order_date=date(2024, 1, 15),
            line_items=[
                LineItem(
                    sku="UFBub250",
                    description="Bubbles",
                    quantity=100,
                    total=1000.0,
                    confidence=0.95,
                )
            ],
            total=1000.0,
            confidence=0.95,
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.PURCHASE_ORDER,
            extraction=extraction,
            success=True,
            processing_time_ms=150.0,
        )

        result = processor.process_po(b"test pdf content")

        assert result.success is True
        assert result.extraction.po_number == "PO-2024-001"
        assert len(result.field_accuracies) > 0
        assert result.overall_accuracy > 0

    def test_process_po_ocr_failure(
        self, processor: POProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test handling of OCR failure."""
        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.PURCHASE_ORDER,
            extraction=PurchaseOrderExtraction(
                po_number="",
                vendor_name="",
                order_date=None,
                needs_review=True,
            ),
            success=False,
            error_message="OCR service unavailable",
        )

        result = processor.process_po(b"test")

        assert result.success is False
        assert result.error_message == "OCR service unavailable"

    def test_process_po_validation_issues(
        self, processor: POProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test that validation issues are captured."""
        extraction = PurchaseOrderExtraction(
            po_number="",  # Missing - should be error
            vendor_name="Vendor",
            order_date=date.today(),
            line_items=[
                LineItem(
                    sku="INVALID-SKU",  # Invalid - should be error
                    description="Test",
                    quantity=10,
                    confidence=0.90,
                )
            ],
            total=100.0,
            confidence=0.90,
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.PURCHASE_ORDER,
            extraction=extraction,
            success=True,
        )

        result = processor.process_po(b"test")

        assert result.success is True
        assert result.has_errors is True
        assert len(result.validation_issues) >= 2

    def test_process_po_auto_normalize_skus(
        self, processor: POProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test automatic SKU normalization."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-001",
            vendor_name="Vendor",
            order_date=date.today(),
            line_items=[
                LineItem(
                    sku="UF-BUB-250",  # Alias
                    description="Bubbles",
                    quantity=100,
                    confidence=0.95,
                )
            ],
            total=1000.0,
            confidence=0.95,
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.PURCHASE_ORDER,
            extraction=extraction,
            success=True,
        )

        result = processor.process_po(b"test")

        # SKU should be normalized
        assert result.extraction.line_items[0].sku == "UFBub250"

    def test_process_po_disable_auto_normalize(
        self, mock_ocr_client: MagicMock
    ) -> None:
        """Test disabling automatic SKU normalization."""
        processor = POProcessor(
            ocr_client=mock_ocr_client,
            auto_normalize_skus=False,
        )

        extraction = PurchaseOrderExtraction(
            po_number="PO-001",
            vendor_name="Vendor",
            order_date=date.today(),
            line_items=[
                LineItem(
                    sku="UF-BUB-250",  # Alias - won't be normalized
                    description="Bubbles",
                    quantity=100,
                    confidence=0.95,
                )
            ],
            total=1000.0,
            confidence=0.95,
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.PURCHASE_ORDER,
            extraction=extraction,
            success=True,
        )

        result = processor.process_po(b"test")

        # SKU should NOT be normalized
        assert result.extraction.line_items[0].sku == "UF-BUB-250"

    def test_process_po_needs_review_low_accuracy(
        self, processor: POProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test that low accuracy triggers review flag."""
        extraction = PurchaseOrderExtraction(
            po_number="PO",  # Short
            vendor_name="V",  # Short
            order_date=None,
            line_items=[],  # No items
            total=0.0,
            confidence=0.50,  # Low confidence
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.PURCHASE_ORDER,
            extraction=extraction,
            success=True,
        )

        result = processor.process_po(b"test")

        assert result.needs_review is True

    def test_process_po_exception_handling(
        self, processor: POProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test exception handling during processing."""
        mock_ocr_client.analyze_document.side_effect = Exception("Unexpected error")

        result = processor.process_po(b"test")

        assert result.success is False
        assert "Unexpected error" in result.error_message

    def test_get_valid_skus(self, processor: POProcessor) -> None:
        """Test getting valid SKUs."""
        skus = processor.get_valid_skus()
        assert skus == VALID_SKUS
        assert "UFBub250" in skus

    def test_get_sku_aliases(self, processor: POProcessor) -> None:
        """Test getting SKU aliases."""
        aliases = processor.get_sku_aliases()
        assert aliases == SKU_ALIASES
        assert "UF-BUB-250" in aliases


# ============================================================================
# POProcessingResult Tests
# ============================================================================


class TestPOProcessingResult:
    """Tests for POProcessingResult data class."""

    def test_has_errors_true(self) -> None:
        """Test has_errors returns True when errors exist."""
        result = POProcessingResult(
            extraction=PurchaseOrderExtraction(
                po_number="", vendor_name="", order_date=None
            ),
            validation_issues=[
                ValidationIssue(
                    field="po_number",
                    message="Missing",
                    severity=ValidationSeverity.ERROR,
                )
            ],
        )
        assert result.has_errors is True

    def test_has_errors_false(self) -> None:
        """Test has_errors returns False when no errors."""
        result = POProcessingResult(
            extraction=PurchaseOrderExtraction(
                po_number="PO-001", vendor_name="Vendor", order_date=None
            ),
            validation_issues=[
                ValidationIssue(
                    field="date",
                    message="Missing",
                    severity=ValidationSeverity.WARNING,
                )
            ],
        )
        assert result.has_errors is False

    def test_has_warnings_true(self) -> None:
        """Test has_warnings returns True when warnings exist."""
        result = POProcessingResult(
            extraction=PurchaseOrderExtraction(
                po_number="PO", vendor_name="V", order_date=None
            ),
            validation_issues=[
                ValidationIssue(
                    field="po_number",
                    message="Too short",
                    severity=ValidationSeverity.WARNING,
                )
            ],
        )
        assert result.has_warnings is True

    def test_valid_line_items_filters_correctly(self) -> None:
        """Test valid_line_items returns only valid SKUs."""
        result = POProcessingResult(
            extraction=PurchaseOrderExtraction(
                po_number="PO-001",
                vendor_name="Vendor",
                order_date=None,
                line_items=[
                    LineItem(sku="UFBub250", description="Valid", quantity=10),
                    LineItem(sku="INVALID", description="Invalid", quantity=5),
                    LineItem(sku="UFRos250", description="Valid", quantity=20),
                ],
            ),
        )

        valid = result.valid_line_items
        assert len(valid) == 2
        assert all(item.sku in VALID_SKUS for item in valid)


# ============================================================================
# Integration Tests with Real Patterns
# ============================================================================


class TestRealWorldPatterns:
    """Tests with real-world PO patterns."""

    def test_rndc_style_po(self) -> None:
        """Test processing RNDC-style PO."""
        extraction = PurchaseOrderExtraction(
            po_number="RNDC-2024-00123",
            vendor_name="Republic National Distributing Company",
            order_date=date(2024, 1, 15),
            delivery_date=date(2024, 1, 22),
            line_items=[
                LineItem(
                    sku="UFBub250",
                    description="Une Femme Bubbles 250ml - Case of 24",
                    quantity=50,
                    unit_price=72.00,
                    total=3600.00,
                    confidence=0.96,
                ),
                LineItem(
                    sku="UFRos250",
                    description="Une Femme Rose 250ml - Case of 24",
                    quantity=25,
                    unit_price=72.00,
                    total=1800.00,
                    confidence=0.94,
                ),
            ],
            subtotal=5400.00,
            tax=0.0,
            total=5400.00,
            confidence=0.95,
        )

        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        assert accuracy > 0.93

    def test_southern_glazers_style_po(self) -> None:
        """Test processing Southern Glazers-style PO."""
        extraction = PurchaseOrderExtraction(
            po_number="SG-TX-2024-0456",
            vendor_name="Southern Glazer's Wine & Spirits",
            order_date=date(2024, 1, 20),
            line_items=[
                LineItem(
                    sku="UFCha250",
                    description="UNE FEMME CHARDONNAY 250ML",
                    quantity=100,
                    unit_price=3.00,
                    total=300.00,
                    confidence=0.93,
                )
            ],
            total=300.00,
            confidence=0.94,
        )

        issues = []
        po_issue = validate_po_number(extraction.po_number)
        if po_issue:
            issues.append(po_issue)

        vendor_issue = validate_vendor_name(extraction.vendor_name)
        if vendor_issue:
            issues.append(vendor_issue)

        # No errors expected
        assert not any(i.severity == ValidationSeverity.ERROR for i in issues)

    def test_multiple_sku_variants_in_one_po(self) -> None:
        """Test PO with multiple variations of same product."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-2024-789",
            vendor_name="Winebow Inc",
            order_date=date(2024, 2, 1),
            line_items=[
                LineItem(sku="UF-BUB-250", description="Bubbles", quantity=100),
                LineItem(sku="UF BUB 250", description="Bubbles", quantity=50),
                LineItem(sku="UFBUB250", description="Bubbles", quantity=25),
            ],
            total=1750.00,
            confidence=0.90,
        )

        corrected, corrections = normalize_line_item_skus(extraction)

        # All should normalize to same SKU
        for item in corrected.line_items:
            assert item.sku == "UFBub250"

        # Should have 2 corrections (first one was already an alias)
        assert len(corrections) == 3


# ============================================================================
# Constants Tests
# ============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_valid_skus_contains_all_products(self) -> None:
        """Test VALID_SKUS contains all 4 products."""
        assert len(VALID_SKUS) == 4
        assert "UFBub250" in VALID_SKUS
        assert "UFRos250" in VALID_SKUS
        assert "UFRed250" in VALID_SKUS
        assert "UFCha250" in VALID_SKUS

    def test_valid_skus_is_frozenset(self) -> None:
        """Test VALID_SKUS is immutable."""
        assert isinstance(VALID_SKUS, frozenset)

    def test_sku_aliases_maps_to_valid_skus(self) -> None:
        """Test all alias values are valid SKUs."""
        for alias, normalized in SKU_ALIASES.items():
            assert normalized in VALID_SKUS, f"Alias '{alias}' maps to invalid SKU '{normalized}'"

    def test_sku_aliases_keys_uppercase(self) -> None:
        """Test all alias keys are uppercase."""
        for alias in SKU_ALIASES:
            assert alias == alias.upper(), f"Alias '{alias}' is not uppercase"
