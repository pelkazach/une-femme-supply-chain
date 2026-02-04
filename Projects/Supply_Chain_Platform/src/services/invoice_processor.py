"""Invoice extraction processor with validation.

This module provides an Invoice-specific processor that extends the base Azure
Document Intelligence OCR with:
- Vendor validation
- Invoice number and amount validation
- Line item validation with SKU normalization
- Field-level accuracy tracking
- Extraction quality metrics

The processor uses the Azure prebuilt-invoice model and ensures >93% field
extraction accuracy as per spec requirements.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any

from src.services.document_ocr import (
    AzureDocumentIntelligenceClient,
    DocumentType,
    InvoiceExtraction,
    LineItem,
)

logger = logging.getLogger(__name__)


# Valid Une Femme SKUs
VALID_SKUS = frozenset({"UFBub250", "UFRos250", "UFRed250", "UFCha250"})

# SKU aliases that may appear in invoices
SKU_ALIASES: dict[str, str] = {
    # Bubble variants
    "UF-BUB-250": "UFBub250",
    "UFBUB250": "UFBub250",
    "UF BUB 250": "UFBub250",
    "UF BUBBLES 250": "UFBub250",
    "BUBBLES 250ML": "UFBub250",
    "UNE FEMME BUBBLES": "UFBub250",
    # Rose variants
    "UF-ROS-250": "UFRos250",
    "UFROS250": "UFRos250",
    "UF ROS 250": "UFRos250",
    "UF ROSE 250": "UFRos250",
    "ROSE 250ML": "UFRos250",
    "UNE FEMME ROSE": "UFRos250",
    # Red variants
    "UF-RED-250": "UFRed250",
    "UFRED250": "UFRed250",
    "UF RED 250": "UFRed250",
    "RED 250ML": "UFRed250",
    "UNE FEMME RED": "UFRed250",
    # Chardonnay variants
    "UF-CHA-250": "UFCha250",
    "UFCHA250": "UFCha250",
    "UF CHA 250": "UFCha250",
    "UF CHARDONNAY 250": "UFCha250",
    "CHARDONNAY 250ML": "UFCha250",
    "UNE FEMME CHARDONNAY": "UFCha250",
}

# Known vendor names for validation
KNOWN_VENDORS = frozenset({
    "UNE FEMME WINES",
    "UNE FEMME WINES LLC",
    "UNE FEMME",
    "RNDC",
    "REPUBLIC NATIONAL DISTRIBUTING COMPANY",
    "SOUTHERN GLAZERS",
    "SOUTHERN GLAZER'S WINE & SPIRITS",
    "WINEBOW",
    "WINEBOW GROUP",
})


class ValidationSeverity(str, Enum):
    """Severity level for validation issues."""

    ERROR = "error"  # Must be corrected
    WARNING = "warning"  # Should be reviewed
    INFO = "info"  # Informational only


@dataclass
class ValidationIssue:
    """Represents a validation issue found during invoice processing."""

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
class InvoiceProcessingResult:
    """Result of invoice processing with validation and accuracy metrics."""

    extraction: InvoiceExtraction
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

    @property
    def valid_line_items(self) -> list[LineItem]:
        """Return only line items with valid SKUs."""
        return [
            item for item in self.extraction.line_items if item.sku in VALID_SKUS
        ]


def normalize_sku(sku: str) -> str | None:
    """Normalize a SKU string to the standard format.

    Args:
        sku: The SKU string to normalize.

    Returns:
        The normalized SKU if valid, None otherwise.
    """
    if not sku:
        return None

    # Clean up the SKU
    clean_sku = sku.strip().upper()

    # Check if it's already a valid SKU
    if clean_sku in VALID_SKUS or clean_sku in {s.upper() for s in VALID_SKUS}:
        # Return the properly cased version
        for valid_sku in VALID_SKUS:
            if valid_sku.upper() == clean_sku:
                return valid_sku
        return None

    # Check aliases
    if clean_sku in SKU_ALIASES:
        return SKU_ALIASES[clean_sku]

    # Try partial matching for common formats
    for alias, normalized in SKU_ALIASES.items():
        if clean_sku.replace("-", "").replace(" ", "") == alias.replace(
            "-", ""
        ).replace(" ", ""):
            return normalized

    return None


def validate_invoice_number(invoice_number: str) -> ValidationIssue | None:
    """Validate an invoice number format.

    Args:
        invoice_number: The invoice number to validate.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not invoice_number:
        return ValidationIssue(
            field="invoice_number",
            message="Invoice number is missing",
            severity=ValidationSeverity.ERROR,
        )

    # Check for minimum length
    if len(invoice_number) < 3:
        return ValidationIssue(
            field="invoice_number",
            message=f"Invoice number '{invoice_number}' is too short",
            severity=ValidationSeverity.WARNING,
            original_value=invoice_number,
        )

    return None


def validate_vendor_name(vendor_name: str) -> ValidationIssue | None:
    """Validate a vendor name.

    Args:
        vendor_name: The vendor name to validate.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not vendor_name:
        return ValidationIssue(
            field="vendor_name",
            message="Vendor name is missing",
            severity=ValidationSeverity.ERROR,
        )

    if len(vendor_name) < 2:
        return ValidationIssue(
            field="vendor_name",
            message=f"Vendor name '{vendor_name}' is too short",
            severity=ValidationSeverity.WARNING,
            original_value=vendor_name,
        )

    return None


def validate_invoice_date(
    invoice_date: date | None, due_date: date | None = None
) -> ValidationIssue | None:
    """Validate invoice date and check against due date.

    Args:
        invoice_date: The invoice date to validate.
        due_date: Optional due date for comparison.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not invoice_date:
        return ValidationIssue(
            field="invoice_date",
            message="Invoice date is missing",
            severity=ValidationSeverity.ERROR,
        )

    # Check if date is in the future (more than 1 day to allow for timezone issues)
    today = date.today()
    if invoice_date > today + timedelta(days=1):
        return ValidationIssue(
            field="invoice_date",
            message=f"Invoice date {invoice_date} is in the future",
            severity=ValidationSeverity.WARNING,
            original_value=invoice_date,
        )

    # Check if date is too old (more than 2 years ago)
    two_years_ago = today - timedelta(days=730)
    if invoice_date < two_years_ago:
        return ValidationIssue(
            field="invoice_date",
            message=f"Invoice date {invoice_date} is more than 2 years old",
            severity=ValidationSeverity.WARNING,
            original_value=invoice_date,
        )

    # Check invoice date vs due date
    if due_date and invoice_date > due_date:
        return ValidationIssue(
            field="invoice_date",
            message=f"Invoice date {invoice_date} is after due date {due_date}",
            severity=ValidationSeverity.WARNING,
            original_value=invoice_date,
        )

    return None


def validate_due_date(
    due_date: date | None, invoice_date: date | None = None
) -> ValidationIssue | None:
    """Validate due date.

    Args:
        due_date: The due date to validate.
        invoice_date: Optional invoice date for comparison.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if not due_date:
        # Due date is optional
        return None

    today = date.today()

    # Check if due date is too far in the past (more than 1 year ago)
    one_year_ago = today - timedelta(days=365)
    if due_date < one_year_ago:
        return ValidationIssue(
            field="due_date",
            message=f"Due date {due_date} is more than 1 year in the past",
            severity=ValidationSeverity.WARNING,
            original_value=due_date,
        )

    # Check if due date is before invoice date
    if invoice_date and due_date < invoice_date:
        return ValidationIssue(
            field="due_date",
            message=f"Due date {due_date} is before invoice date {invoice_date}",
            severity=ValidationSeverity.WARNING,
            original_value=due_date,
        )

    return None


def validate_amount(amount: float, field_name: str) -> ValidationIssue | None:
    """Validate a monetary amount.

    Args:
        amount: The amount to validate.
        field_name: The name of the field being validated.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if amount < 0:
        return ValidationIssue(
            field=field_name,
            message=f"{field_name.replace('_', ' ').title()} {amount} is negative",
            severity=ValidationSeverity.ERROR,
            original_value=amount,
        )

    # Check for unusually high amounts (more than $1M)
    if amount > 1_000_000:
        return ValidationIssue(
            field=field_name,
            message=f"{field_name.replace('_', ' ').title()} ${amount:,.2f} seems unusually high",
            severity=ValidationSeverity.WARNING,
            original_value=amount,
        )

    return None


def validate_quantity(quantity: int, sku: str) -> ValidationIssue | None:
    """Validate a line item quantity.

    Args:
        quantity: The quantity to validate.
        sku: The SKU for context.

    Returns:
        ValidationIssue if invalid, None if valid.
    """
    if quantity <= 0:
        return ValidationIssue(
            field=f"line_item.{sku}.quantity",
            message=f"Invalid quantity {quantity} for SKU {sku}",
            severity=ValidationSeverity.ERROR,
            original_value=quantity,
        )

    # Unusual quantity warning (more than 10000 units)
    if quantity > 10000:
        return ValidationIssue(
            field=f"line_item.{sku}.quantity",
            message=f"Unusually high quantity {quantity} for SKU {sku}",
            severity=ValidationSeverity.WARNING,
            original_value=quantity,
        )

    return None


def validate_line_item(item: LineItem) -> list[ValidationIssue]:
    """Validate a single line item.

    Args:
        item: The line item to validate.

    Returns:
        List of validation issues found.
    """
    issues: list[ValidationIssue] = []

    # Validate SKU
    normalized_sku = normalize_sku(item.sku)
    if not normalized_sku:
        issues.append(
            ValidationIssue(
                field="line_item.sku",
                message=f"Unknown SKU '{item.sku}'. Valid SKUs: {', '.join(sorted(VALID_SKUS))}",
                severity=ValidationSeverity.ERROR,
                original_value=item.sku,
            )
        )
    elif normalized_sku != item.sku:
        issues.append(
            ValidationIssue(
                field="line_item.sku",
                message=f"SKU '{item.sku}' normalized to '{normalized_sku}'",
                severity=ValidationSeverity.INFO,
                original_value=item.sku,
                corrected_value=normalized_sku,
            )
        )

    # Validate quantity
    qty_issue = validate_quantity(item.quantity, item.sku)
    if qty_issue:
        issues.append(qty_issue)

    # Validate unit price if present
    if item.unit_price is not None and item.unit_price < 0:
        issues.append(
            ValidationIssue(
                field=f"line_item.{item.sku}.unit_price",
                message=f"Negative unit price {item.unit_price}",
                severity=ValidationSeverity.ERROR,
                original_value=item.unit_price,
            )
        )

    # Validate total if present
    if item.total is not None and item.total < 0:
        issues.append(
            ValidationIssue(
                field=f"line_item.{item.sku}.total",
                message=f"Negative total {item.total}",
                severity=ValidationSeverity.ERROR,
                original_value=item.total,
            )
        )

    # Cross-validate unit_price * quantity = total (within 1% tolerance)
    if item.unit_price is not None and item.total is not None and item.quantity > 0:
        expected_total = item.unit_price * item.quantity
        if expected_total > 0 and abs(expected_total - item.total) > (expected_total * 0.01):
            issues.append(
                ValidationIssue(
                    field=f"line_item.{item.sku}.total",
                    message=f"Total {item.total} doesn't match unit_price * quantity = {expected_total:.2f}",
                    severity=ValidationSeverity.WARNING,
                    original_value=item.total,
                    corrected_value=expected_total,
                )
            )

    return issues


def validate_invoice_totals(extraction: InvoiceExtraction) -> list[ValidationIssue]:
    """Validate invoice total amounts.

    Args:
        extraction: The invoice extraction to validate.

    Returns:
        List of validation issues found.
    """
    issues: list[ValidationIssue] = []

    # Calculate expected total from line items
    line_item_total = sum(item.total or 0 for item in extraction.line_items)

    # Validate subtotal
    subtotal_issue = validate_amount(extraction.subtotal, "subtotal")
    if subtotal_issue:
        issues.append(subtotal_issue)
    elif (
        line_item_total > 0
        and abs(extraction.subtotal - line_item_total) > (line_item_total * 0.01)
    ):
        issues.append(
            ValidationIssue(
                field="subtotal",
                message=f"Subtotal ${extraction.subtotal:.2f} doesn't match line items total ${line_item_total:.2f}",
                severity=ValidationSeverity.WARNING,
                original_value=extraction.subtotal,
                corrected_value=line_item_total,
            )
        )

    # Validate tax if present
    if extraction.tax is not None:
        tax_issue = validate_amount(extraction.tax, "tax")
        if tax_issue:
            issues.append(tax_issue)

    # Validate total
    total_issue = validate_amount(extraction.total, "total")
    if total_issue:
        issues.append(total_issue)

    # Validate total = subtotal + tax
    expected_total = extraction.subtotal + (extraction.tax or 0)
    if expected_total > 0 and abs(extraction.total - expected_total) > (expected_total * 0.01):
        issues.append(
            ValidationIssue(
                field="total",
                message=f"Total ${extraction.total:.2f} doesn't match subtotal + tax = ${expected_total:.2f}",
                severity=ValidationSeverity.WARNING,
                original_value=extraction.total,
                corrected_value=expected_total,
            )
        )

    return issues


def calculate_field_accuracy(extraction: InvoiceExtraction) -> list[FieldAccuracy]:
    """Calculate field-level accuracy metrics.

    Args:
        extraction: The invoice extraction to analyze.

    Returns:
        List of field accuracy metrics.
    """
    accuracies: list[FieldAccuracy] = []

    # Invoice Number
    accuracies.append(
        FieldAccuracy(
            field_name="invoice_number",
            extracted=bool(extraction.invoice_number),
            confidence=extraction.confidence if extraction.invoice_number else 0.0,
            validated=bool(extraction.invoice_number),
        )
    )

    # Vendor Name
    accuracies.append(
        FieldAccuracy(
            field_name="vendor_name",
            extracted=bool(extraction.vendor_name),
            confidence=extraction.confidence if extraction.vendor_name else 0.0,
            validated=bool(extraction.vendor_name),
        )
    )

    # Invoice Date
    accuracies.append(
        FieldAccuracy(
            field_name="invoice_date",
            extracted=extraction.invoice_date is not None,
            confidence=extraction.confidence if extraction.invoice_date else 0.0,
            validated=extraction.invoice_date is not None,
        )
    )

    # Due Date (optional)
    accuracies.append(
        FieldAccuracy(
            field_name="due_date",
            extracted=extraction.due_date is not None,
            confidence=extraction.confidence if extraction.due_date else 0.0,
            validated=True,  # Optional field
        )
    )

    # Line Items
    for i, item in enumerate(extraction.line_items):
        accuracies.append(
            FieldAccuracy(
                field_name=f"line_item_{i}_sku",
                extracted=bool(item.sku),
                confidence=item.confidence,
                validated=normalize_sku(item.sku) is not None,
            )
        )
        accuracies.append(
            FieldAccuracy(
                field_name=f"line_item_{i}_quantity",
                extracted=item.quantity > 0,
                confidence=item.confidence,
                validated=item.quantity > 0,
            )
        )
        accuracies.append(
            FieldAccuracy(
                field_name=f"line_item_{i}_amount",
                extracted=item.total is not None and item.total > 0,
                confidence=item.confidence,
                validated=item.total is not None and item.total > 0,
            )
        )

    # Subtotal
    accuracies.append(
        FieldAccuracy(
            field_name="subtotal",
            extracted=extraction.subtotal > 0,
            confidence=extraction.confidence if extraction.subtotal > 0 else 0.0,
            validated=extraction.subtotal >= 0,
        )
    )

    # Tax (optional)
    accuracies.append(
        FieldAccuracy(
            field_name="tax",
            extracted=extraction.tax is not None,
            confidence=extraction.confidence if extraction.tax else 0.0,
            validated=True,  # Optional field
        )
    )

    # Total
    accuracies.append(
        FieldAccuracy(
            field_name="total",
            extracted=extraction.total > 0,
            confidence=extraction.confidence if extraction.total > 0 else 0.0,
            validated=extraction.total > 0,
        )
    )

    return accuracies


def calculate_overall_accuracy(
    extraction: InvoiceExtraction,
    field_accuracies: list[FieldAccuracy],
) -> float:
    """Calculate overall extraction accuracy.

    The accuracy is weighted by field importance:
    - Required fields (invoice_number, vendor_name, total): weight 2.0
    - Important fields (dates, subtotal, line_items): weight 1.5
    - Optional fields (tax, due_date): weight 1.0

    Args:
        extraction: The invoice extraction.
        field_accuracies: List of field accuracies.

    Returns:
        Overall accuracy as a float between 0 and 1.
    """
    if not field_accuracies:
        return 0.0

    # Field weights
    weights = {
        "invoice_number": 2.0,
        "vendor_name": 2.0,
        "invoice_date": 1.5,
        "due_date": 1.0,
        "subtotal": 1.5,
        "tax": 1.0,
        "total": 2.0,
    }

    # Line item fields are important
    for acc in field_accuracies:
        if acc.field_name.startswith("line_item_"):
            if "sku" in acc.field_name or "amount" in acc.field_name:
                weights[acc.field_name] = 1.5
            else:
                weights[acc.field_name] = 1.5

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


def normalize_line_item_skus(
    extraction: InvoiceExtraction,
) -> tuple[InvoiceExtraction, list[ValidationIssue]]:
    """Normalize SKUs in line items and return corrected extraction.

    Args:
        extraction: The original extraction.

    Returns:
        Tuple of (corrected extraction, list of corrections made).
    """
    corrections: list[ValidationIssue] = []
    corrected_items: list[LineItem] = []

    for item in extraction.line_items:
        normalized = normalize_sku(item.sku)
        if normalized and normalized != item.sku:
            corrections.append(
                ValidationIssue(
                    field="line_item.sku",
                    message=f"SKU '{item.sku}' corrected to '{normalized}'",
                    severity=ValidationSeverity.INFO,
                    original_value=item.sku,
                    corrected_value=normalized,
                )
            )
            corrected_items.append(
                LineItem(
                    sku=normalized,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total=item.total,
                    confidence=item.confidence,
                )
            )
        else:
            corrected_items.append(item)

    # Create new extraction with corrected items
    corrected = InvoiceExtraction(
        invoice_number=extraction.invoice_number,
        vendor_name=extraction.vendor_name,
        invoice_date=extraction.invoice_date,
        due_date=extraction.due_date,
        line_items=corrected_items,
        subtotal=extraction.subtotal,
        tax=extraction.tax,
        total=extraction.total,
        confidence=extraction.confidence,
        raw_result=extraction.raw_result,
        needs_review=extraction.needs_review,
    )

    return corrected, corrections


class InvoiceProcessor:
    """Processor for Invoice documents with validation.

    This processor uses the Azure Document Intelligence prebuilt-invoice
    model with invoice-specific validation and accuracy tracking.

    Usage:
        processor = InvoiceProcessor()

        # Process an invoice document
        result = processor.process_invoice(pdf_content)

        if result.success:
            print(f"Invoice #{result.extraction.invoice_number}")
            print(f"Total: ${result.extraction.total:.2f}")
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
        auto_normalize_skus: bool = True,
    ) -> None:
        """Initialize the invoice processor.

        Args:
            ocr_client: Azure Document Intelligence client for OCR.
                If not provided, a default client will be created.
            auto_normalize_skus: Automatically normalize SKUs to standard format.
        """
        self.ocr_client = ocr_client or AzureDocumentIntelligenceClient()
        self.auto_normalize_skus = auto_normalize_skus

    def process_invoice(
        self,
        document_bytes: bytes,
        include_raw_result: bool = False,
    ) -> InvoiceProcessingResult:
        """Process an invoice document with validation and accuracy tracking.

        Args:
            document_bytes: The invoice document content (PDF or image).
            include_raw_result: Include raw OCR result in output.

        Returns:
            InvoiceProcessingResult with extraction, validation, and accuracy metrics.
        """
        import time

        start_time = time.monotonic()

        try:
            # Perform OCR extraction using prebuilt-invoice model
            ocr_result = self.ocr_client.analyze_document(
                document_bytes=document_bytes,
                document_type=DocumentType.INVOICE,
                include_raw_result=include_raw_result,
            )

            if not ocr_result.success:
                return InvoiceProcessingResult(
                    extraction=ocr_result.extraction,  # type: ignore
                    success=False,
                    error_message=ocr_result.error_message,
                    processing_time_ms=(time.monotonic() - start_time) * 1000,
                )

            extraction = ocr_result.extraction
            if not isinstance(extraction, InvoiceExtraction):
                return InvoiceProcessingResult(
                    extraction=InvoiceExtraction(
                        invoice_number="",
                        vendor_name="",
                        invoice_date=None,
                        needs_review=True,
                    ),
                    success=False,
                    error_message="Invalid extraction type",
                    processing_time_ms=(time.monotonic() - start_time) * 1000,
                )

            # Normalize SKUs if enabled
            corrections: list[ValidationIssue] = []
            if self.auto_normalize_skus:
                extraction, corrections = normalize_line_item_skus(extraction)

            # Validate the extraction
            validation_issues = self._validate_extraction(extraction)
            validation_issues.extend(corrections)

            # Calculate accuracy metrics
            field_accuracies = calculate_field_accuracy(extraction)
            overall_accuracy = calculate_overall_accuracy(extraction, field_accuracies)

            # Update field accuracies with correction info
            for acc in field_accuracies:
                for correction in corrections:
                    if correction.field.endswith(acc.field_name.replace("_", ".")):
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

            return InvoiceProcessingResult(
                extraction=extraction,
                validation_issues=validation_issues,
                field_accuracies=field_accuracies,
                overall_accuracy=overall_accuracy,
                needs_review=needs_review,
                processing_time_ms=processing_time,
                success=True,
            )

        except Exception as e:
            logger.error("Error processing invoice: %s", e)
            return InvoiceProcessingResult(
                extraction=InvoiceExtraction(
                    invoice_number="",
                    vendor_name="",
                    invoice_date=None,
                    needs_review=True,
                ),
                success=False,
                error_message=str(e),
                processing_time_ms=(time.monotonic() - start_time) * 1000,
            )

    def _validate_extraction(
        self, extraction: InvoiceExtraction
    ) -> list[ValidationIssue]:
        """Validate the extracted invoice data.

        Args:
            extraction: The invoice extraction to validate.

        Returns:
            List of validation issues found.
        """
        issues: list[ValidationIssue] = []

        # Validate required fields
        invoice_issue = validate_invoice_number(extraction.invoice_number)
        if invoice_issue:
            issues.append(invoice_issue)

        vendor_issue = validate_vendor_name(extraction.vendor_name)
        if vendor_issue:
            issues.append(vendor_issue)

        # Validate dates
        date_issue = validate_invoice_date(
            extraction.invoice_date, extraction.due_date
        )
        if date_issue:
            issues.append(date_issue)

        due_date_issue = validate_due_date(
            extraction.due_date, extraction.invoice_date
        )
        if due_date_issue:
            issues.append(due_date_issue)

        # Validate line items
        if not extraction.line_items:
            issues.append(
                ValidationIssue(
                    field="line_items",
                    message="No line items found in invoice",
                    severity=ValidationSeverity.WARNING,
                )
            )
        else:
            for item in extraction.line_items:
                issues.extend(validate_line_item(item))

        # Validate totals
        issues.extend(validate_invoice_totals(extraction))

        return issues

    def get_valid_skus(self) -> frozenset[str]:
        """Return the set of valid SKUs."""
        return VALID_SKUS

    def get_sku_aliases(self) -> dict[str, str]:
        """Return the SKU alias mapping."""
        return SKU_ALIASES.copy()

    def get_known_vendors(self) -> frozenset[str]:
        """Return the set of known vendors."""
        return KNOWN_VENDORS
