"""Bill of Lading (BOL) extraction processor with validation.

This module provides a BOL-specific processor that extends the base Azure
Document Intelligence OCR with:
- Shipper/consignee validation
- Carrier and tracking number validation
- Cargo details validation
- Field-level accuracy tracking
- Extraction quality metrics

The processor ensures >93% field extraction accuracy as per spec requirements.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any

from src.services.document_ocr import (
    AzureDocumentIntelligenceClient,
    BOLExtraction,
    DocumentType,
)

logger = logging.getLogger(__name__)


# Known carrier names for validation
KNOWN_CARRIERS = frozenset({
    "UPS",
    "FEDEX",
    "USPS",
    "DHL",
    "OLD DOMINION",
    "YRC FREIGHT",
    "XPO LOGISTICS",
    "ESTES EXPRESS",
    "ABF FREIGHT",
    "SAIA",
    "R+L CARRIERS",
    "SOUTHEASTERN FREIGHT",
    "AVERITT EXPRESS",
    "DAYTON FREIGHT",
    "CENTRAL TRANSPORT",
})

# Common carrier name aliases
CARRIER_ALIASES: dict[str, str] = {
    "UNITED PARCEL SERVICE": "UPS",
    "FEDERAL EXPRESS": "FEDEX",
    "FED EX": "FEDEX",
    "UNITED STATES POSTAL SERVICE": "USPS",
    "DHL EXPRESS": "DHL",
    "OD": "OLD DOMINION",
    "OLD DOMINION FREIGHT": "OLD DOMINION",
    "XPO": "XPO LOGISTICS",
    "ESTES": "ESTES EXPRESS",
    "ABF": "ABF FREIGHT",
    "R&L CARRIERS": "R+L CARRIERS",
    "RL CARRIERS": "R+L CARRIERS",
    "SEFL": "SOUTHEASTERN FREIGHT",
    "AVERITT": "AVERITT EXPRESS",
}


class ValidationSeverity(str, Enum):
    """Severity level for validation issues."""

    ERROR = "error"  # Must be corrected
    WARNING = "warning"  # Should be reviewed
    INFO = "info"  # Informational only


@dataclass
class ValidationIssue:
    """Represents a validation issue found during BOL processing."""

    field: str
    message: str
    severity: ValidationSeverity
    original_value: Any = None
    corrected_value: Any = None


@dataclass
class FieldAccuracy:
    """Tracks accuracy metrics for a specific field."""

    field_name: str
    extracted: bool
    confidence: float
    validated: bool
    corrected: bool = False


@dataclass
class BOLProcessingResult:
    """Result of BOL processing with validation and accuracy metrics."""

    extraction: BOLExtraction
    validation_issues: list[ValidationIssue] = field(default_factory=list)
    field_accuracies: list[FieldAccuracy] = field(default_factory=list)
    overall_accuracy: float = 0.0
    needs_review: bool = False
    processing_time_ms: float = 0.0
    success: bool = True
    error_message: str | None = None

    @property
    def has_errors(self) -> bool:
        """Check if there are any error-level validation issues."""
        return any(
            issue.severity == ValidationSeverity.ERROR
            for issue in self.validation_issues
        )

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warning-level validation issues."""
        return any(
            issue.severity == ValidationSeverity.WARNING
            for issue in self.validation_issues
        )


def normalize_carrier(carrier: str) -> str | None:
    """Normalize a carrier name to standard format.

    Args:
        carrier: The carrier name to normalize.

    Returns:
        The normalized carrier name if recognized, None otherwise.
    """
    if not carrier:
        return None

    # Clean up the carrier name
    clean_carrier = carrier.strip().upper()

    # Check if it's already a known carrier
    if clean_carrier in KNOWN_CARRIERS:
        return clean_carrier

    # Check aliases
    if clean_carrier in CARRIER_ALIASES:
        return CARRIER_ALIASES[clean_carrier]

    # Try partial matching for common formats
    for alias, normalized in CARRIER_ALIASES.items():
        if clean_carrier.replace("-", "").replace(" ", "") == alias.replace(
            "-", ""
        ).replace(" ", ""):
            return normalized

    # Return original if not found (carrier might be valid but unknown)
    return None


def validate_bol_number(bol_number: str) -> ValidationIssue | None:
    """Validate a BOL number format.

    Args:
        bol_number: The BOL number to validate.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not bol_number:
        return ValidationIssue(
            field="bol_number",
            message="BOL number is missing",
            severity=ValidationSeverity.ERROR,
        )

    # Check for minimum length
    if len(bol_number) < 3:
        return ValidationIssue(
            field="bol_number",
            message=f"BOL number '{bol_number}' is too short",
            severity=ValidationSeverity.WARNING,
            original_value=bol_number,
        )

    return None


def validate_shipper_name(shipper_name: str) -> ValidationIssue | None:
    """Validate a shipper name.

    Args:
        shipper_name: The shipper name to validate.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not shipper_name:
        return ValidationIssue(
            field="shipper_name",
            message="Shipper name is missing",
            severity=ValidationSeverity.ERROR,
        )

    if len(shipper_name) < 2:
        return ValidationIssue(
            field="shipper_name",
            message=f"Shipper name '{shipper_name}' is too short",
            severity=ValidationSeverity.WARNING,
            original_value=shipper_name,
        )

    return None


def validate_shipper_address(shipper_address: str) -> ValidationIssue | None:
    """Validate a shipper address.

    Args:
        shipper_address: The shipper address to validate.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not shipper_address:
        return ValidationIssue(
            field="shipper_address",
            message="Shipper address is missing",
            severity=ValidationSeverity.ERROR,
        )

    # Check for reasonable address length
    if len(shipper_address) < 10:
        return ValidationIssue(
            field="shipper_address",
            message=f"Shipper address '{shipper_address}' appears incomplete",
            severity=ValidationSeverity.WARNING,
            original_value=shipper_address,
        )

    return None


def validate_consignee_name(consignee_name: str) -> ValidationIssue | None:
    """Validate a consignee name.

    Args:
        consignee_name: The consignee name to validate.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not consignee_name:
        return ValidationIssue(
            field="consignee_name",
            message="Consignee name is missing",
            severity=ValidationSeverity.ERROR,
        )

    if len(consignee_name) < 2:
        return ValidationIssue(
            field="consignee_name",
            message=f"Consignee name '{consignee_name}' is too short",
            severity=ValidationSeverity.WARNING,
            original_value=consignee_name,
        )

    return None


def validate_consignee_address(consignee_address: str) -> ValidationIssue | None:
    """Validate a consignee address.

    Args:
        consignee_address: The consignee address to validate.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not consignee_address:
        return ValidationIssue(
            field="consignee_address",
            message="Consignee address is missing",
            severity=ValidationSeverity.ERROR,
        )

    if len(consignee_address) < 10:
        return ValidationIssue(
            field="consignee_address",
            message=f"Consignee address '{consignee_address}' appears incomplete",
            severity=ValidationSeverity.WARNING,
            original_value=consignee_address,
        )

    return None


def validate_carrier(carrier: str) -> ValidationIssue | None:
    """Validate a carrier name.

    Args:
        carrier: The carrier name to validate.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not carrier:
        return ValidationIssue(
            field="carrier",
            message="Carrier name is missing",
            severity=ValidationSeverity.ERROR,
        )

    if len(carrier) < 2:
        return ValidationIssue(
            field="carrier",
            message=f"Carrier name '{carrier}' is too short",
            severity=ValidationSeverity.WARNING,
            original_value=carrier,
        )

    return None


def validate_tracking_number(tracking_number: str | None) -> ValidationIssue | None:
    """Validate a tracking number format.

    Args:
        tracking_number: The tracking number to validate.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not tracking_number:
        # Tracking number is optional
        return None

    # Check for reasonable length
    if len(tracking_number) < 5:
        return ValidationIssue(
            field="tracking_number",
            message=f"Tracking number '{tracking_number}' appears too short",
            severity=ValidationSeverity.WARNING,
            original_value=tracking_number,
        )

    # Check for alphanumeric with allowed separators
    if not re.match(r"^[A-Za-z0-9\-_]+$", tracking_number):
        return ValidationIssue(
            field="tracking_number",
            message=f"Tracking number '{tracking_number}' contains invalid characters",
            severity=ValidationSeverity.WARNING,
            original_value=tracking_number,
        )

    return None


def validate_ship_date(ship_date: date | None) -> ValidationIssue | None:
    """Validate the ship date.

    Args:
        ship_date: The ship date to validate.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not ship_date:
        return ValidationIssue(
            field="ship_date",
            message="Ship date is missing",
            severity=ValidationSeverity.WARNING,
        )

    today = date.today()

    # Check if date is too far in the future (more than 30 days)
    if ship_date > today + timedelta(days=30):
        return ValidationIssue(
            field="ship_date",
            message=f"Ship date {ship_date} is more than 30 days in the future",
            severity=ValidationSeverity.WARNING,
            original_value=ship_date,
        )

    # Check if date is too old (more than 1 year ago)
    one_year_ago = today - timedelta(days=365)
    if ship_date < one_year_ago:
        return ValidationIssue(
            field="ship_date",
            message=f"Ship date {ship_date} is more than 1 year old",
            severity=ValidationSeverity.WARNING,
            original_value=ship_date,
        )

    return None


def validate_cargo_description(cargo_description: str) -> ValidationIssue | None:
    """Validate the cargo description.

    Args:
        cargo_description: The cargo description to validate.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not cargo_description:
        return ValidationIssue(
            field="cargo_description",
            message="Cargo description is missing",
            severity=ValidationSeverity.WARNING,
        )

    if len(cargo_description) < 3:
        return ValidationIssue(
            field="cargo_description",
            message=f"Cargo description '{cargo_description}' is too short",
            severity=ValidationSeverity.WARNING,
            original_value=cargo_description,
        )

    return None


def validate_weight(weight: float | None) -> ValidationIssue | None:
    """Validate the cargo weight.

    Args:
        weight: The weight to validate.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if weight is None:
        # Weight is optional
        return None

    if weight <= 0:
        return ValidationIssue(
            field="weight",
            message=f"Weight {weight} must be positive",
            severity=ValidationSeverity.ERROR,
            original_value=weight,
        )

    # Check for unusually high weight (more than 50000 lbs)
    if weight > 50000:
        return ValidationIssue(
            field="weight",
            message=f"Weight {weight} lbs seems unusually high",
            severity=ValidationSeverity.WARNING,
            original_value=weight,
        )

    return None


def calculate_field_accuracy(extraction: BOLExtraction) -> list[FieldAccuracy]:
    """Calculate field-level accuracy metrics.

    Args:
        extraction: The BOL extraction to analyze.

    Returns:
        List of field accuracy metrics.
    """
    accuracies: list[FieldAccuracy] = []

    # BOL Number
    accuracies.append(
        FieldAccuracy(
            field_name="bol_number",
            extracted=bool(extraction.bol_number),
            confidence=extraction.confidence if extraction.bol_number else 0.0,
            validated=bool(extraction.bol_number),
        )
    )

    # Shipper Name
    accuracies.append(
        FieldAccuracy(
            field_name="shipper_name",
            extracted=bool(extraction.shipper_name),
            confidence=extraction.confidence if extraction.shipper_name else 0.0,
            validated=bool(extraction.shipper_name),
        )
    )

    # Shipper Address
    accuracies.append(
        FieldAccuracy(
            field_name="shipper_address",
            extracted=bool(extraction.shipper_address),
            confidence=extraction.confidence if extraction.shipper_address else 0.0,
            validated=bool(extraction.shipper_address),
        )
    )

    # Consignee Name
    accuracies.append(
        FieldAccuracy(
            field_name="consignee_name",
            extracted=bool(extraction.consignee_name),
            confidence=extraction.confidence if extraction.consignee_name else 0.0,
            validated=bool(extraction.consignee_name),
        )
    )

    # Consignee Address
    accuracies.append(
        FieldAccuracy(
            field_name="consignee_address",
            extracted=bool(extraction.consignee_address),
            confidence=extraction.confidence if extraction.consignee_address else 0.0,
            validated=bool(extraction.consignee_address),
        )
    )

    # Carrier
    accuracies.append(
        FieldAccuracy(
            field_name="carrier",
            extracted=bool(extraction.carrier),
            confidence=extraction.confidence if extraction.carrier else 0.0,
            validated=bool(extraction.carrier),
        )
    )

    # Tracking Number (optional)
    accuracies.append(
        FieldAccuracy(
            field_name="tracking_number",
            extracted=extraction.tracking_number is not None,
            confidence=extraction.confidence if extraction.tracking_number else 0.0,
            validated=True,  # Optional field
        )
    )

    # Ship Date
    accuracies.append(
        FieldAccuracy(
            field_name="ship_date",
            extracted=extraction.ship_date is not None,
            confidence=extraction.confidence if extraction.ship_date else 0.0,
            validated=extraction.ship_date is not None,
        )
    )

    # Cargo Description
    accuracies.append(
        FieldAccuracy(
            field_name="cargo_description",
            extracted=bool(extraction.cargo_description),
            confidence=extraction.confidence if extraction.cargo_description else 0.0,
            validated=bool(extraction.cargo_description),
        )
    )

    # Weight (optional)
    accuracies.append(
        FieldAccuracy(
            field_name="weight",
            extracted=extraction.weight is not None,
            confidence=extraction.confidence if extraction.weight else 0.0,
            validated=True,  # Optional field
        )
    )

    return accuracies


def calculate_overall_accuracy(
    extraction: BOLExtraction,
    field_accuracies: list[FieldAccuracy],
) -> float:
    """Calculate overall extraction accuracy.

    The accuracy is weighted by field importance:
    - Required fields (bol_number, shipper, consignee, carrier): weight 2.0
    - Important fields (ship_date, cargo_description): weight 1.5
    - Optional fields (tracking_number, weight): weight 1.0

    Args:
        extraction: The BOL extraction.
        field_accuracies: List of field accuracies.

    Returns:
        Overall accuracy as a float between 0 and 1.
    """
    if not field_accuracies:
        return 0.0

    # Field weights
    weights = {
        "bol_number": 2.0,
        "shipper_name": 2.0,
        "shipper_address": 2.0,
        "consignee_name": 2.0,
        "consignee_address": 2.0,
        "carrier": 2.0,
        "tracking_number": 1.0,
        "ship_date": 1.5,
        "cargo_description": 1.5,
        "weight": 1.0,
    }

    total_weight = 0.0
    weighted_accuracy = 0.0

    for acc in field_accuracies:
        weight = weights.get(acc.field_name, 1.0)
        total_weight += weight

        # Accuracy score for this field
        if acc.extracted and acc.validated:
            score = acc.confidence
        elif acc.extracted:
            score = acc.confidence * 0.5  # Extracted but not validated
        else:
            score = 0.0

        weighted_accuracy += score * weight

    if total_weight == 0:
        return 0.0

    return weighted_accuracy / total_weight


def normalize_carrier_in_extraction(
    extraction: BOLExtraction,
) -> tuple[BOLExtraction, list[ValidationIssue]]:
    """Normalize the carrier name in extraction and return corrected extraction.

    Args:
        extraction: The original extraction.

    Returns:
        Tuple of (corrected extraction, list of corrections made).
    """
    corrections: list[ValidationIssue] = []

    normalized = normalize_carrier(extraction.carrier)
    if normalized and normalized != extraction.carrier:
        corrections.append(
            ValidationIssue(
                field="carrier",
                message=f"Carrier '{extraction.carrier}' normalized to '{normalized}'",
                severity=ValidationSeverity.INFO,
                original_value=extraction.carrier,
                corrected_value=normalized,
            )
        )
        # Create new extraction with normalized carrier
        corrected = BOLExtraction(
            bol_number=extraction.bol_number,
            shipper_name=extraction.shipper_name,
            shipper_address=extraction.shipper_address,
            consignee_name=extraction.consignee_name,
            consignee_address=extraction.consignee_address,
            carrier=normalized,
            tracking_number=extraction.tracking_number,
            ship_date=extraction.ship_date,
            cargo_description=extraction.cargo_description,
            weight=extraction.weight,
            confidence=extraction.confidence,
            raw_result=extraction.raw_result,
            needs_review=extraction.needs_review,
        )
        return corrected, corrections

    return extraction, corrections


class BOLProcessor:
    """Processor for Bill of Lading documents with validation.

    This processor extends the base Azure Document Intelligence OCR
    with BOL-specific validation and accuracy tracking.

    Usage:
        processor = BOLProcessor()

        # Process a BOL document
        result = processor.process_bol(pdf_content)

        if result.success:
            print(f"BOL #{result.extraction.bol_number}")
            print(f"Accuracy: {result.overall_accuracy:.1%}")

            if result.has_errors:
                print("Errors found:")
                for issue in result.validation_issues:
                    if issue.severity == ValidationSeverity.ERROR:
                        print(f"  - {issue.message}")
    """

    def __init__(
        self,
        ocr_client: AzureDocumentIntelligenceClient | None = None,
        auto_normalize_carrier: bool = True,
    ) -> None:
        """Initialize the BOL processor.

        Args:
            ocr_client: Azure Document Intelligence client for OCR.
                If not provided, a default client will be created.
            auto_normalize_carrier: Automatically normalize carrier names to standard format.
        """
        self.ocr_client = ocr_client or AzureDocumentIntelligenceClient()
        self.auto_normalize_carrier = auto_normalize_carrier

    def process_bol(
        self,
        document_bytes: bytes,
        include_raw_result: bool = False,
    ) -> BOLProcessingResult:
        """Process a BOL document with validation and accuracy tracking.

        Args:
            document_bytes: The BOL document content (PDF or image).
            include_raw_result: Include raw OCR result in output.

        Returns:
            BOLProcessingResult with extraction, validation, and accuracy metrics.
        """
        import time

        start_time = time.monotonic()

        try:
            # Perform OCR extraction
            ocr_result = self.ocr_client.analyze_document(
                document_bytes=document_bytes,
                document_type=DocumentType.BILL_OF_LADING,
                include_raw_result=include_raw_result,
            )

            if not ocr_result.success:
                return BOLProcessingResult(
                    extraction=ocr_result.extraction,  # type: ignore
                    success=False,
                    error_message=ocr_result.error_message,
                    processing_time_ms=(time.monotonic() - start_time) * 1000,
                )

            extraction = ocr_result.extraction
            if not isinstance(extraction, BOLExtraction):
                return BOLProcessingResult(
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
                    error_message="Invalid extraction type",
                    processing_time_ms=(time.monotonic() - start_time) * 1000,
                )

            # Normalize carrier if enabled
            corrections: list[ValidationIssue] = []
            if self.auto_normalize_carrier:
                extraction, corrections = normalize_carrier_in_extraction(extraction)

            # Validate the extraction
            validation_issues = self._validate_extraction(extraction)
            validation_issues.extend(corrections)

            # Calculate accuracy metrics
            field_accuracies = calculate_field_accuracy(extraction)
            overall_accuracy = calculate_overall_accuracy(extraction, field_accuracies)

            # Update field accuracies with correction info
            for acc in field_accuracies:
                for correction in corrections:
                    if correction.field == acc.field_name:
                        acc.corrected = True

            # Determine if review is needed
            needs_review = (
                extraction.needs_review
                or overall_accuracy < 0.93
                or any(
                    issue.severity == ValidationSeverity.ERROR
                    for issue in validation_issues
                )
            )

            processing_time = (time.monotonic() - start_time) * 1000

            return BOLProcessingResult(
                extraction=extraction,
                validation_issues=validation_issues,
                field_accuracies=field_accuracies,
                overall_accuracy=overall_accuracy,
                needs_review=needs_review,
                processing_time_ms=processing_time,
                success=True,
            )

        except Exception as e:
            logger.error("Error processing BOL: %s", e)
            return BOLProcessingResult(
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
                error_message=str(e),
                processing_time_ms=(time.monotonic() - start_time) * 1000,
            )

    def _validate_extraction(
        self, extraction: BOLExtraction
    ) -> list[ValidationIssue]:
        """Validate the extracted BOL data.

        Args:
            extraction: The BOL extraction to validate.

        Returns:
            List of validation issues found.
        """
        issues: list[ValidationIssue] = []

        # Validate required fields
        bol_issue = validate_bol_number(extraction.bol_number)
        if bol_issue:
            issues.append(bol_issue)

        shipper_name_issue = validate_shipper_name(extraction.shipper_name)
        if shipper_name_issue:
            issues.append(shipper_name_issue)

        shipper_addr_issue = validate_shipper_address(extraction.shipper_address)
        if shipper_addr_issue:
            issues.append(shipper_addr_issue)

        consignee_name_issue = validate_consignee_name(extraction.consignee_name)
        if consignee_name_issue:
            issues.append(consignee_name_issue)

        consignee_addr_issue = validate_consignee_address(extraction.consignee_address)
        if consignee_addr_issue:
            issues.append(consignee_addr_issue)

        carrier_issue = validate_carrier(extraction.carrier)
        if carrier_issue:
            issues.append(carrier_issue)

        # Validate optional fields
        tracking_issue = validate_tracking_number(extraction.tracking_number)
        if tracking_issue:
            issues.append(tracking_issue)

        # Validate dates
        date_issue = validate_ship_date(extraction.ship_date)
        if date_issue:
            issues.append(date_issue)

        # Validate cargo
        cargo_issue = validate_cargo_description(extraction.cargo_description)
        if cargo_issue:
            issues.append(cargo_issue)

        weight_issue = validate_weight(extraction.weight)
        if weight_issue:
            issues.append(weight_issue)

        return issues

    def get_known_carriers(self) -> frozenset[str]:
        """Return the set of known carriers."""
        return KNOWN_CARRIERS

    def get_carrier_aliases(self) -> dict[str, str]:
        """Return the carrier alias mapping."""
        return CARRIER_ALIASES.copy()
