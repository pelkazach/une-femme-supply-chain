"""Tests for BOL extraction processor with validation.

These tests verify:
- Carrier normalization and validation
- BOL field validation (bol_number, shipper, consignee, carrier, tracking)
- Ship date and cargo validation
- Accuracy calculation (>93% requirement)
- Integration with Azure Document Intelligence
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from src.services.bol_processor import (
    CARRIER_ALIASES,
    KNOWN_CARRIERS,
    BOLProcessingResult,
    BOLProcessor,
    FieldAccuracy,
    ValidationIssue,
    ValidationSeverity,
    calculate_field_accuracy,
    calculate_overall_accuracy,
    normalize_carrier,
    normalize_carrier_in_extraction,
    validate_bol_number,
    validate_cargo_description,
    validate_carrier,
    validate_consignee_address,
    validate_consignee_name,
    validate_ship_date,
    validate_shipper_address,
    validate_shipper_name,
    validate_tracking_number,
    validate_weight,
)
from src.services.document_ocr import (
    AzureDocumentIntelligenceClient,
    BOLExtraction,
    DocumentType,
    ExtractionResult,
)


# ============================================================================
# Carrier Normalization Tests
# ============================================================================


class TestNormalizeCarrier:
    """Tests for carrier normalization function."""

    def test_known_carrier_unchanged(self) -> None:
        """Test that known carriers are returned (uppercase)."""
        assert normalize_carrier("UPS") == "UPS"
        assert normalize_carrier("FEDEX") == "FEDEX"
        assert normalize_carrier("OLD DOMINION") == "OLD DOMINION"

    def test_known_carrier_case_insensitive(self) -> None:
        """Test that carrier matching is case-insensitive."""
        assert normalize_carrier("ups") == "UPS"
        assert normalize_carrier("FedEx") == "FEDEX"
        assert normalize_carrier("dhl") == "DHL"

    def test_carrier_alias_ups(self) -> None:
        """Test UPS aliases."""
        assert normalize_carrier("UNITED PARCEL SERVICE") == "UPS"

    def test_carrier_alias_fedex(self) -> None:
        """Test FedEx aliases."""
        assert normalize_carrier("FEDERAL EXPRESS") == "FEDEX"
        assert normalize_carrier("FED EX") == "FEDEX"

    def test_carrier_alias_old_dominion(self) -> None:
        """Test Old Dominion aliases."""
        assert normalize_carrier("OD") == "OLD DOMINION"
        assert normalize_carrier("OLD DOMINION FREIGHT") == "OLD DOMINION"

    def test_carrier_alias_xpo(self) -> None:
        """Test XPO aliases."""
        assert normalize_carrier("XPO") == "XPO LOGISTICS"

    def test_carrier_alias_rl_carriers(self) -> None:
        """Test R+L Carriers aliases."""
        assert normalize_carrier("R&L CARRIERS") == "R+L CARRIERS"
        assert normalize_carrier("RL CARRIERS") == "R+L CARRIERS"

    def test_unknown_carrier_returns_none(self) -> None:
        """Test that unknown carriers return None."""
        assert normalize_carrier("UNKNOWN CARRIER") is None
        assert normalize_carrier("ABC TRUCKING") is None

    def test_empty_carrier_returns_none(self) -> None:
        """Test that empty carrier returns None."""
        assert normalize_carrier("") is None
        assert normalize_carrier("   ") is None

    def test_whitespace_stripped(self) -> None:
        """Test that whitespace is stripped from carriers."""
        assert normalize_carrier("  UPS  ") == "UPS"
        assert normalize_carrier("\tFEDEX\n") == "FEDEX"


# ============================================================================
# Validation Function Tests
# ============================================================================


class TestValidateBOLNumber:
    """Tests for BOL number validation."""

    def test_valid_bol_number(self) -> None:
        """Test that valid BOL numbers pass."""
        assert validate_bol_number("BOL-2024-001") is None
        assert validate_bol_number("12345678") is None
        assert validate_bol_number("ABC123") is None

    def test_missing_bol_number_error(self) -> None:
        """Test that missing BOL number is an error."""
        issue = validate_bol_number("")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "missing" in issue.message.lower()

    def test_short_bol_number_warning(self) -> None:
        """Test that short BOL numbers generate warning."""
        issue = validate_bol_number("AB")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "too short" in issue.message.lower()


class TestValidateShipperName:
    """Tests for shipper name validation."""

    def test_valid_shipper_name(self) -> None:
        """Test that valid shipper names pass."""
        assert validate_shipper_name("Une Femme Wines") is None
        assert validate_shipper_name("ABC Winery LLC") is None

    def test_missing_shipper_error(self) -> None:
        """Test that missing shipper is an error."""
        issue = validate_shipper_name("")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "missing" in issue.message.lower()

    def test_short_shipper_warning(self) -> None:
        """Test that short shipper names generate warning."""
        issue = validate_shipper_name("A")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING


class TestValidateShipperAddress:
    """Tests for shipper address validation."""

    def test_valid_shipper_address(self) -> None:
        """Test that valid addresses pass."""
        assert validate_shipper_address("123 Main Street, Napa, CA 94558") is None
        assert validate_shipper_address("1234 Wine Valley Rd, Sonoma, CA") is None

    def test_missing_shipper_address_error(self) -> None:
        """Test that missing address is an error."""
        issue = validate_shipper_address("")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "missing" in issue.message.lower()

    def test_incomplete_address_warning(self) -> None:
        """Test that incomplete addresses generate warning."""
        issue = validate_shipper_address("123 Main")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "incomplete" in issue.message.lower()


class TestValidateConsigneeName:
    """Tests for consignee name validation."""

    def test_valid_consignee_name(self) -> None:
        """Test that valid consignee names pass."""
        assert validate_consignee_name("RNDC Distribution") is None
        assert validate_consignee_name("Southern Glazers") is None

    def test_missing_consignee_error(self) -> None:
        """Test that missing consignee is an error."""
        issue = validate_consignee_name("")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "missing" in issue.message.lower()

    def test_short_consignee_warning(self) -> None:
        """Test that short consignee names generate warning."""
        issue = validate_consignee_name("X")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING


class TestValidateConsigneeAddress:
    """Tests for consignee address validation."""

    def test_valid_consignee_address(self) -> None:
        """Test that valid addresses pass."""
        assert validate_consignee_address("456 Distribution Blvd, Houston, TX 77001") is None

    def test_missing_consignee_address_error(self) -> None:
        """Test that missing address is an error."""
        issue = validate_consignee_address("")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "missing" in issue.message.lower()

    def test_incomplete_address_warning(self) -> None:
        """Test that incomplete addresses generate warning."""
        issue = validate_consignee_address("456 Blvd")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING


class TestValidateCarrier:
    """Tests for carrier validation."""

    def test_valid_carrier(self) -> None:
        """Test that valid carriers pass."""
        assert validate_carrier("UPS") is None
        assert validate_carrier("Old Dominion Freight Line") is None

    def test_missing_carrier_error(self) -> None:
        """Test that missing carrier is an error."""
        issue = validate_carrier("")
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "missing" in issue.message.lower()

    def test_short_carrier_warning(self) -> None:
        """Test that short carrier names generate warning."""
        issue = validate_carrier("A")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING


class TestValidateTrackingNumber:
    """Tests for tracking number validation."""

    def test_valid_tracking_number(self) -> None:
        """Test that valid tracking numbers pass."""
        assert validate_tracking_number("1Z999AA10123456784") is None
        assert validate_tracking_number("PRO-123456") is None
        assert validate_tracking_number("ABC123DEF456") is None

    def test_none_tracking_number_valid(self) -> None:
        """Test that None tracking number is valid (optional field)."""
        assert validate_tracking_number(None) is None

    def test_empty_tracking_number_valid(self) -> None:
        """Test that empty tracking number is valid (optional field)."""
        assert validate_tracking_number("") is None

    def test_short_tracking_number_warning(self) -> None:
        """Test that short tracking numbers generate warning."""
        issue = validate_tracking_number("1234")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "too short" in issue.message.lower()

    def test_invalid_characters_warning(self) -> None:
        """Test that invalid characters generate warning."""
        issue = validate_tracking_number("ABC#123@456")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "invalid characters" in issue.message.lower()


class TestValidateShipDate:
    """Tests for ship date validation."""

    def test_valid_ship_date(self) -> None:
        """Test that valid dates pass."""
        yesterday = date.today() - timedelta(days=1)
        assert validate_ship_date(yesterday) is None

    def test_today_ship_date_valid(self) -> None:
        """Test that today's date is valid."""
        assert validate_ship_date(date.today()) is None

    def test_missing_ship_date_warning(self) -> None:
        """Test that missing date is a warning."""
        issue = validate_ship_date(None)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "missing" in issue.message.lower()

    def test_future_date_warning(self) -> None:
        """Test that far future dates generate warning."""
        future = date.today() + timedelta(days=60)
        issue = validate_ship_date(future)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "future" in issue.message.lower()

    def test_near_future_date_valid(self) -> None:
        """Test that near future dates are valid."""
        near_future = date.today() + timedelta(days=7)
        assert validate_ship_date(near_future) is None

    def test_old_date_warning(self) -> None:
        """Test that very old dates generate warning."""
        old_date = date.today() - timedelta(days=400)
        issue = validate_ship_date(old_date)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "1 year" in issue.message.lower()


class TestValidateCargoDescription:
    """Tests for cargo description validation."""

    def test_valid_cargo_description(self) -> None:
        """Test that valid descriptions pass."""
        assert validate_cargo_description("24 cases wine, 250ml bottles") is None
        assert validate_cargo_description("Wine - 50 cases") is None

    def test_missing_cargo_description_warning(self) -> None:
        """Test that missing description is a warning."""
        issue = validate_cargo_description("")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "missing" in issue.message.lower()

    def test_short_cargo_description_warning(self) -> None:
        """Test that short descriptions generate warning."""
        issue = validate_cargo_description("W")
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "too short" in issue.message.lower()


class TestValidateWeight:
    """Tests for weight validation."""

    def test_valid_weight(self) -> None:
        """Test that valid weights pass."""
        assert validate_weight(100.0) is None
        assert validate_weight(5000.0) is None
        assert validate_weight(50000.0) is None

    def test_none_weight_valid(self) -> None:
        """Test that None weight is valid (optional field)."""
        assert validate_weight(None) is None

    def test_zero_weight_error(self) -> None:
        """Test that zero weight is an error."""
        issue = validate_weight(0.0)
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR
        assert "positive" in issue.message.lower()

    def test_negative_weight_error(self) -> None:
        """Test that negative weight is an error."""
        issue = validate_weight(-100.0)
        assert issue is not None
        assert issue.severity == ValidationSeverity.ERROR

    def test_high_weight_warning(self) -> None:
        """Test that unusually high weights generate warning."""
        issue = validate_weight(75000.0)
        assert issue is not None
        assert issue.severity == ValidationSeverity.WARNING
        assert "unusually high" in issue.message.lower()


# ============================================================================
# Accuracy Calculation Tests
# ============================================================================


class TestFieldAccuracy:
    """Tests for field accuracy calculation."""

    def test_calculate_field_accuracy_complete(self) -> None:
        """Test accuracy calculation for complete extraction."""
        extraction = BOLExtraction(
            bol_number="BOL-2024-001",
            shipper_name="Une Femme Wines",
            shipper_address="123 Winery Lane, Napa, CA 94558",
            consignee_name="RNDC Distribution",
            consignee_address="456 Distribution Blvd, Houston, TX 77001",
            carrier="OLD DOMINION",
            tracking_number="PRO-123456",
            ship_date=date.today(),
            cargo_description="24 cases wine",
            weight=500.0,
            confidence=0.95,
        )
        accuracies = calculate_field_accuracy(extraction)

        # Should have all 10 fields
        assert len(accuracies) == 10

        # All fields should be extracted
        assert all(acc.extracted for acc in accuracies)

    def test_calculate_field_accuracy_missing_optional(self) -> None:
        """Test accuracy calculation with missing optional fields."""
        extraction = BOLExtraction(
            bol_number="BOL-2024-001",
            shipper_name="Une Femme Wines",
            shipper_address="123 Winery Lane, Napa, CA 94558",
            consignee_name="RNDC Distribution",
            consignee_address="456 Distribution Blvd, Houston, TX 77001",
            carrier="UPS",
            tracking_number=None,  # Optional
            ship_date=date.today(),
            cargo_description="Wine cases",
            weight=None,  # Optional
            confidence=0.90,
        )
        accuracies = calculate_field_accuracy(extraction)

        # tracking_number not extracted
        tracking_acc = next(a for a in accuracies if a.field_name == "tracking_number")
        assert tracking_acc.extracted is False
        assert tracking_acc.validated is True  # Optional field

        # weight not extracted
        weight_acc = next(a for a in accuracies if a.field_name == "weight")
        assert weight_acc.extracted is False
        assert weight_acc.validated is True  # Optional field

    def test_calculate_field_accuracy_missing_required(self) -> None:
        """Test accuracy calculation with missing required fields."""
        extraction = BOLExtraction(
            bol_number="",  # Missing
            shipper_name="Une Femme Wines",
            shipper_address="",  # Missing
            consignee_name="",  # Missing
            consignee_address="456 Distribution Blvd",
            carrier="UPS",
            confidence=0.80,
        )
        accuracies = calculate_field_accuracy(extraction)

        # bol_number not extracted
        bol_acc = next(a for a in accuracies if a.field_name == "bol_number")
        assert bol_acc.extracted is False

        # shipper_address not extracted
        shipper_addr_acc = next(a for a in accuracies if a.field_name == "shipper_address")
        assert shipper_addr_acc.extracted is False


class TestOverallAccuracy:
    """Tests for overall accuracy calculation."""

    def test_high_accuracy_extraction(self) -> None:
        """Test that complete extraction yields high accuracy."""
        extraction = BOLExtraction(
            bol_number="BOL-2024-001",
            shipper_name="Une Femme Wines",
            shipper_address="123 Winery Lane, Napa, CA 94558",
            consignee_name="RNDC Distribution",
            consignee_address="456 Distribution Blvd, Houston, TX 77001",
            carrier="OLD DOMINION",
            tracking_number="PRO-123456",
            ship_date=date.today(),
            cargo_description="24 cases wine",
            weight=500.0,
            confidence=0.96,
        )
        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        # Should be high accuracy
        assert accuracy > 0.90

    def test_low_accuracy_missing_fields(self) -> None:
        """Test that missing fields yield lower accuracy."""
        extraction = BOLExtraction(
            bol_number="",
            shipper_name="",
            shipper_address="",
            consignee_name="",
            consignee_address="",
            carrier="",
            confidence=0.5,
        )
        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        # Should be low accuracy
        assert accuracy < 0.30

    def test_empty_accuracies_returns_zero(self) -> None:
        """Test that empty accuracies list returns 0."""
        extraction = BOLExtraction(
            bol_number="BOL-001",
            shipper_name="Shipper",
            shipper_address="Address",
            consignee_name="Consignee",
            consignee_address="Address",
            carrier="UPS",
        )
        accuracy = calculate_overall_accuracy(extraction, [])
        assert accuracy == 0.0

    def test_accuracy_above_93_threshold(self) -> None:
        """Test meeting the >93% accuracy requirement."""
        extraction = BOLExtraction(
            bol_number="BOL-2024-00123",
            shipper_name="Une Femme Wines LLC",
            shipper_address="123 Winery Lane, Napa Valley, CA 94558",
            consignee_name="Republic National Distributing Company",
            consignee_address="456 Distribution Boulevard, Houston, TX 77001",
            carrier="OLD DOMINION FREIGHT LINE",
            tracking_number="PRO-9876543210",
            ship_date=date.today(),
            cargo_description="24 cases Une Femme wine, 250ml bottles, fragile",
            weight=720.5,
            confidence=0.96,
        )
        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        # Should meet the >93% requirement
        assert accuracy > 0.93


# ============================================================================
# Carrier Normalization in Extraction Tests
# ============================================================================


class TestNormalizeCarrierInExtraction:
    """Tests for carrier normalization in BOL extraction."""

    def test_normalize_known_carrier_unchanged(self) -> None:
        """Test that known carriers are normalized."""
        extraction = BOLExtraction(
            bol_number="BOL-001",
            shipper_name="Shipper",
            shipper_address="Address",
            consignee_name="Consignee",
            consignee_address="Address",
            carrier="ups",  # Lowercase
            confidence=0.95,
        )
        corrected, issues = normalize_carrier_in_extraction(extraction)

        assert corrected.carrier == "UPS"
        assert len(issues) == 1
        assert issues[0].severity == ValidationSeverity.INFO

    def test_normalize_alias_carrier(self) -> None:
        """Test that alias carriers are normalized."""
        extraction = BOLExtraction(
            bol_number="BOL-001",
            shipper_name="Shipper",
            shipper_address="Address",
            consignee_name="Consignee",
            consignee_address="Address",
            carrier="FEDERAL EXPRESS",
            confidence=0.95,
        )
        corrected, issues = normalize_carrier_in_extraction(extraction)

        assert corrected.carrier == "FEDEX"
        assert len(issues) == 1

    def test_unknown_carrier_unchanged(self) -> None:
        """Test that unknown carriers are not changed."""
        extraction = BOLExtraction(
            bol_number="BOL-001",
            shipper_name="Shipper",
            shipper_address="Address",
            consignee_name="Consignee",
            consignee_address="Address",
            carrier="LOCAL TRUCKING CO",
            confidence=0.95,
        )
        corrected, issues = normalize_carrier_in_extraction(extraction)

        assert corrected.carrier == "LOCAL TRUCKING CO"
        assert len(issues) == 0

    def test_normalize_preserves_other_fields(self) -> None:
        """Test that normalization preserves other fields."""
        extraction = BOLExtraction(
            bol_number="BOL-2024-001",
            shipper_name="Une Femme Wines",
            shipper_address="123 Winery Lane",
            consignee_name="RNDC",
            consignee_address="456 Distribution Blvd",
            carrier="UNITED PARCEL SERVICE",
            tracking_number="1Z999AA10123456784",
            ship_date=date(2024, 1, 15),
            cargo_description="Wine cases",
            weight=500.0,
            confidence=0.92,
        )
        corrected, _ = normalize_carrier_in_extraction(extraction)

        assert corrected.bol_number == "BOL-2024-001"
        assert corrected.shipper_name == "Une Femme Wines"
        assert corrected.tracking_number == "1Z999AA10123456784"
        assert corrected.ship_date == date(2024, 1, 15)
        assert corrected.weight == 500.0


# ============================================================================
# BOLProcessor Integration Tests
# ============================================================================


class TestBOLProcessor:
    """Tests for the BOLProcessor class."""

    @pytest.fixture
    def mock_ocr_client(self) -> MagicMock:
        """Create a mock OCR client."""
        client = MagicMock(spec=AzureDocumentIntelligenceClient)
        return client

    @pytest.fixture
    def processor(self, mock_ocr_client: MagicMock) -> BOLProcessor:
        """Create a processor with mock OCR client."""
        return BOLProcessor(ocr_client=mock_ocr_client)

    def test_process_bol_success(
        self, processor: BOLProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test successful BOL processing."""
        extraction = BOLExtraction(
            bol_number="BOL-2024-001",
            shipper_name="Une Femme Wines",
            shipper_address="123 Winery Lane, Napa, CA 94558",
            consignee_name="RNDC Distribution",
            consignee_address="456 Distribution Blvd, Houston, TX 77001",
            carrier="OLD DOMINION",
            tracking_number="PRO-123456",
            ship_date=date(2024, 1, 15),
            cargo_description="24 cases wine",
            weight=500.0,
            confidence=0.95,
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.BILL_OF_LADING,
            extraction=extraction,
            success=True,
            processing_time_ms=150.0,
        )

        result = processor.process_bol(b"test pdf content")

        assert result.success is True
        assert result.extraction.bol_number == "BOL-2024-001"
        assert len(result.field_accuracies) > 0
        assert result.overall_accuracy > 0

    def test_process_bol_ocr_failure(
        self, processor: BOLProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test handling of OCR failure."""
        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.BILL_OF_LADING,
            extraction=BOLExtraction(
                bol_number="",
                shipper_name="",
                shipper_address="",
                consignee_name="",
                consignee_address="",
                carrier="",
                needs_review=True,
            ),
            success=False,
            error_message="OCR service unavailable",
        )

        result = processor.process_bol(b"test")

        assert result.success is False
        assert result.error_message == "OCR service unavailable"

    def test_process_bol_validation_issues(
        self, processor: BOLProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test that validation issues are captured."""
        extraction = BOLExtraction(
            bol_number="",  # Missing - should be error
            shipper_name="Une Femme Wines",
            shipper_address="123 Winery Lane, Napa, CA 94558",
            consignee_name="",  # Missing - should be error
            consignee_address="456 Distribution Blvd, Houston, TX 77001",
            carrier="UPS",
            ship_date=date.today(),
            cargo_description="Wine",
            confidence=0.90,
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.BILL_OF_LADING,
            extraction=extraction,
            success=True,
        )

        result = processor.process_bol(b"test")

        assert result.success is True
        assert result.has_errors is True
        assert len(result.validation_issues) >= 2

    def test_process_bol_auto_normalize_carrier(
        self, processor: BOLProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test automatic carrier normalization."""
        extraction = BOLExtraction(
            bol_number="BOL-001",
            shipper_name="Shipper",
            shipper_address="123 Address Street, City, ST 12345",
            consignee_name="Consignee",
            consignee_address="456 Destination Ave, City, ST 67890",
            carrier="FEDERAL EXPRESS",  # Alias
            ship_date=date.today(),
            cargo_description="Wine cases",
            confidence=0.95,
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.BILL_OF_LADING,
            extraction=extraction,
            success=True,
        )

        result = processor.process_bol(b"test")

        # Carrier should be normalized
        assert result.extraction.carrier == "FEDEX"

    def test_process_bol_disable_auto_normalize(
        self, mock_ocr_client: MagicMock
    ) -> None:
        """Test disabling automatic carrier normalization."""
        processor = BOLProcessor(
            ocr_client=mock_ocr_client,
            auto_normalize_carrier=False,
        )

        extraction = BOLExtraction(
            bol_number="BOL-001",
            shipper_name="Shipper",
            shipper_address="123 Address Street, City, ST 12345",
            consignee_name="Consignee",
            consignee_address="456 Destination Ave, City, ST 67890",
            carrier="federal express",  # Won't be normalized
            ship_date=date.today(),
            cargo_description="Wine cases",
            confidence=0.95,
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.BILL_OF_LADING,
            extraction=extraction,
            success=True,
        )

        result = processor.process_bol(b"test")

        # Carrier should NOT be normalized
        assert result.extraction.carrier == "federal express"

    def test_process_bol_needs_review_low_accuracy(
        self, processor: BOLProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test that low accuracy triggers review flag."""
        extraction = BOLExtraction(
            bol_number="B",  # Short
            shipper_name="S",  # Short
            shipper_address="Addr",  # Short
            consignee_name="C",  # Short
            consignee_address="Addr",  # Short
            carrier="U",  # Short
            cargo_description="",  # Missing
            confidence=0.50,  # Low confidence
        )

        mock_ocr_client.analyze_document.return_value = ExtractionResult(
            document_type=DocumentType.BILL_OF_LADING,
            extraction=extraction,
            success=True,
        )

        result = processor.process_bol(b"test")

        assert result.needs_review is True

    def test_process_bol_exception_handling(
        self, processor: BOLProcessor, mock_ocr_client: MagicMock
    ) -> None:
        """Test exception handling during processing."""
        mock_ocr_client.analyze_document.side_effect = Exception("Unexpected error")

        result = processor.process_bol(b"test")

        assert result.success is False
        assert "Unexpected error" in result.error_message

    def test_get_known_carriers(self, processor: BOLProcessor) -> None:
        """Test getting known carriers."""
        carriers = processor.get_known_carriers()
        assert carriers == KNOWN_CARRIERS
        assert "UPS" in carriers
        assert "FEDEX" in carriers

    def test_get_carrier_aliases(self, processor: BOLProcessor) -> None:
        """Test getting carrier aliases."""
        aliases = processor.get_carrier_aliases()
        assert aliases == CARRIER_ALIASES
        assert "FEDERAL EXPRESS" in aliases


# ============================================================================
# BOLProcessingResult Tests
# ============================================================================


class TestBOLProcessingResult:
    """Tests for BOLProcessingResult data class."""

    def test_has_errors_true(self) -> None:
        """Test has_errors returns True when errors exist."""
        result = BOLProcessingResult(
            extraction=BOLExtraction(
                bol_number="",
                shipper_name="",
                shipper_address="",
                consignee_name="",
                consignee_address="",
                carrier="",
            ),
            validation_issues=[
                ValidationIssue(
                    field="bol_number",
                    message="Missing",
                    severity=ValidationSeverity.ERROR,
                )
            ],
        )
        assert result.has_errors is True

    def test_has_errors_false(self) -> None:
        """Test has_errors returns False when no errors."""
        result = BOLProcessingResult(
            extraction=BOLExtraction(
                bol_number="BOL-001",
                shipper_name="Shipper",
                shipper_address="Address",
                consignee_name="Consignee",
                consignee_address="Address",
                carrier="UPS",
            ),
            validation_issues=[
                ValidationIssue(
                    field="ship_date",
                    message="Missing",
                    severity=ValidationSeverity.WARNING,
                )
            ],
        )
        assert result.has_errors is False

    def test_has_warnings_true(self) -> None:
        """Test has_warnings returns True when warnings exist."""
        result = BOLProcessingResult(
            extraction=BOLExtraction(
                bol_number="BO",
                shipper_name="S",
                shipper_address="Addr",
                consignee_name="Consignee Name Here",
                consignee_address="456 Full Address",
                carrier="UPS",
            ),
            validation_issues=[
                ValidationIssue(
                    field="bol_number",
                    message="Too short",
                    severity=ValidationSeverity.WARNING,
                )
            ],
        )
        assert result.has_warnings is True


# ============================================================================
# Integration Tests with Real Patterns
# ============================================================================


class TestRealWorldPatterns:
    """Tests with real-world BOL patterns."""

    def test_wine_shipment_bol(self) -> None:
        """Test processing typical wine shipment BOL."""
        extraction = BOLExtraction(
            bol_number="WS-2024-00789",
            shipper_name="Une Femme Wines LLC",
            shipper_address="123 Vineyard Road, Napa Valley, CA 94558",
            consignee_name="Republic National Distributing Company",
            consignee_address="4567 Industrial Boulevard, Houston, TX 77001",
            carrier="OLD DOMINION",
            tracking_number="PRO-9876543210",
            ship_date=date.today() - timedelta(days=2),
            cargo_description="48 cases Une Femme wine, 250ml bottles, handle with care",
            weight=1440.0,
            confidence=0.95,
        )

        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        assert accuracy > 0.93

    def test_southern_glazers_bol(self) -> None:
        """Test processing Southern Glazers-style BOL."""
        extraction = BOLExtraction(
            bol_number="SG-BOL-2024-01234",
            shipper_name="California Winery Partners",
            shipper_address="9876 Wine Country Drive, Sonoma, CA 95476",
            consignee_name="Southern Glazer's Wine & Spirits",
            consignee_address="1234 Distribution Center Parkway, Dallas, TX 75201",
            carrier="XPO LOGISTICS",
            tracking_number="XPO-987654321",
            ship_date=date.today(),
            cargo_description="Mixed wine cases - 96 total",
            weight=2880.0,
            confidence=0.94,
        )

        issues: list[ValidationIssue] = []
        bol_issue = validate_bol_number(extraction.bol_number)
        if bol_issue:
            issues.append(bol_issue)

        shipper_issue = validate_shipper_name(extraction.shipper_name)
        if shipper_issue:
            issues.append(shipper_issue)

        # No errors expected
        assert not any(i.severity == ValidationSeverity.ERROR for i in issues)

    def test_handwritten_bol_low_confidence(self) -> None:
        """Test BOL with potential OCR issues (handwritten)."""
        extraction = BOLExtraction(
            bol_number="HW-001",  # Short due to OCR issues
            shipper_name="Une Femme",
            shipper_address="123 Main St",  # Incomplete
            consignee_name="RNDC",
            consignee_address="456 Blvd",  # Incomplete
            carrier="UPS",
            ship_date=date.today(),
            cargo_description="Wine",
            confidence=0.75,  # Low confidence from handwriting
        )

        accuracies = calculate_field_accuracy(extraction)
        accuracy = calculate_overall_accuracy(extraction, accuracies)

        # Should be below threshold due to low confidence
        assert accuracy < 0.93

    def test_multiple_carrier_formats(self) -> None:
        """Test various carrier name formats."""
        carrier_tests = [
            ("ups", "UPS"),
            ("FEDERAL EXPRESS", "FEDEX"),
            ("OLD DOMINION FREIGHT", "OLD DOMINION"),
            ("XPO", "XPO LOGISTICS"),
            ("R&L CARRIERS", "R+L CARRIERS"),
        ]

        for original, expected in carrier_tests:
            normalized = normalize_carrier(original)
            assert normalized == expected, f"Expected {expected} for {original}, got {normalized}"


# ============================================================================
# Constants Tests
# ============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_known_carriers_contains_major_carriers(self) -> None:
        """Test KNOWN_CARRIERS contains major freight carriers."""
        assert "UPS" in KNOWN_CARRIERS
        assert "FEDEX" in KNOWN_CARRIERS
        assert "OLD DOMINION" in KNOWN_CARRIERS
        assert "XPO LOGISTICS" in KNOWN_CARRIERS

    def test_known_carriers_is_frozenset(self) -> None:
        """Test KNOWN_CARRIERS is immutable."""
        assert isinstance(KNOWN_CARRIERS, frozenset)

    def test_carrier_aliases_maps_to_known_carriers(self) -> None:
        """Test all alias values are known carriers."""
        for alias, normalized in CARRIER_ALIASES.items():
            assert (
                normalized in KNOWN_CARRIERS
            ), f"Alias '{alias}' maps to unknown carrier '{normalized}'"

    def test_carrier_aliases_keys_uppercase(self) -> None:
        """Test all alias keys are uppercase."""
        for alias in CARRIER_ALIASES:
            assert alias == alias.upper(), f"Alias '{alias}' is not uppercase"
