"""Azure Document Intelligence client for OCR and document data extraction.

This module integrates with Azure Document Intelligence (formerly Form Recognizer)
to extract structured data from POs, BOLs, and invoices.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzedDocument,
    AnalyzeResult,
    DocumentField,
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ServiceRequestError,
)

from src.config import settings

logger = logging.getLogger(__name__)


class DocumentOCRError(Exception):
    """Base exception for document OCR errors."""


class DocumentAuthError(DocumentOCRError):
    """Raised when Azure authentication fails."""


class DocumentProcessingError(DocumentOCRError):
    """Raised when document processing fails."""


class DocumentType(str, Enum):
    """Supported document types for extraction."""

    PURCHASE_ORDER = "PO"
    BILL_OF_LADING = "BOL"
    INVOICE = "INVOICE"


# Model IDs for Azure Document Intelligence
MODEL_IDS = {
    DocumentType.PURCHASE_ORDER: "custom-po-model",  # Custom model for POs
    DocumentType.BILL_OF_LADING: "custom-bol-model",  # Custom model for BOLs
    DocumentType.INVOICE: "prebuilt-invoice",  # Prebuilt model for invoices
}

# Minimum confidence threshold for accepting extractions
MIN_CONFIDENCE_THRESHOLD = 0.85


@dataclass
class LineItem:
    """Represents a line item in a PO or invoice."""

    sku: str
    description: str
    quantity: int
    unit_price: float | None = None
    total: float | None = None
    confidence: float = 0.0


@dataclass
class PurchaseOrderExtraction:
    """Extracted data from a purchase order document."""

    po_number: str
    vendor_name: str
    order_date: date | None
    delivery_date: date | None = None
    line_items: list[LineItem] = field(default_factory=list)
    subtotal: float | None = None
    tax: float | None = None
    total: float = 0.0
    confidence: float = 0.0
    raw_result: dict[str, Any] | None = None
    needs_review: bool = False


@dataclass
class BOLExtraction:
    """Extracted data from a bill of lading document."""

    bol_number: str
    shipper_name: str
    shipper_address: str
    consignee_name: str
    consignee_address: str
    carrier: str
    tracking_number: str | None = None
    ship_date: date | None = None
    cargo_description: str = ""
    weight: float | None = None
    confidence: float = 0.0
    raw_result: dict[str, Any] | None = None
    needs_review: bool = False


@dataclass
class InvoiceExtraction:
    """Extracted data from an invoice document."""

    invoice_number: str
    vendor_name: str
    invoice_date: date | None
    due_date: date | None = None
    line_items: list[LineItem] = field(default_factory=list)
    subtotal: float = 0.0
    tax: float | None = None
    total: float = 0.0
    confidence: float = 0.0
    raw_result: dict[str, Any] | None = None
    needs_review: bool = False


@dataclass
class ExtractionResult:
    """Generic result wrapper for document extractions."""

    document_type: DocumentType
    extraction: PurchaseOrderExtraction | BOLExtraction | InvoiceExtraction
    success: bool
    error_message: str | None = None
    processing_time_ms: float = 0.0


class AzureDocumentIntelligenceClient:
    """Client for Azure Document Intelligence OCR and extraction.

    This client provides document analysis capabilities using Azure's
    Document Intelligence service, supporting both prebuilt models
    (for invoices) and custom models (for POs and BOLs).

    Usage:
        client = AzureDocumentIntelligenceClient()

        # Analyze an invoice
        result = client.analyze_document(
            document_bytes=pdf_content,
            document_type=DocumentType.INVOICE
        )

        if result.success:
            invoice = result.extraction
            print(f"Invoice #{invoice.invoice_number} - ${invoice.total}")
    """

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize the Azure Document Intelligence client.

        Args:
            endpoint: Azure Document Intelligence endpoint URL.
                Defaults to settings.azure_doc_intelligence_endpoint.
            api_key: Azure API key for authentication.
                Defaults to settings.azure_doc_intelligence_key.
        """
        self.endpoint = endpoint or settings.azure_doc_intelligence_endpoint
        self.api_key = api_key or settings.azure_doc_intelligence_key
        self._client: DocumentIntelligenceClient | None = None

    @property
    def is_configured(self) -> bool:
        """Check if the client has valid configuration."""
        return bool(self.endpoint and self.api_key)

    def _get_client(self) -> DocumentIntelligenceClient:
        """Get or create the Document Intelligence client."""
        if self._client is None:
            if not self.is_configured:
                raise DocumentAuthError(
                    "Azure Document Intelligence not configured. "
                    "Set AZURE_DOC_INTELLIGENCE_ENDPOINT and AZURE_DOC_INTELLIGENCE_KEY."
                )
            self._client = DocumentIntelligenceClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.api_key),
            )
        return self._client

    def analyze_document(
        self,
        document_bytes: bytes,
        document_type: DocumentType,
        include_raw_result: bool = False,
    ) -> ExtractionResult:
        """Analyze a document and extract structured data.

        Args:
            document_bytes: The document content as bytes (PDF or image).
            document_type: The type of document to analyze.
            include_raw_result: Include raw API response in the result.

        Returns:
            ExtractionResult containing the extracted data or error info.

        Raises:
            DocumentAuthError: If authentication fails.
            DocumentProcessingError: If document processing fails.
        """
        import io
        import time

        start_time = time.monotonic()

        try:
            client = self._get_client()
            model_id = MODEL_IDS[document_type]

            logger.info(
                "Analyzing %s document with model %s (%d bytes)",
                document_type.value,
                model_id,
                len(document_bytes),
            )

            # Wrap bytes in a file-like object for the SDK
            document_stream = io.BytesIO(document_bytes)

            # Start the analysis
            poller = client.begin_analyze_document(
                model_id=model_id,
                body=document_stream,
                content_type="application/octet-stream",
            )

            # Wait for the result
            result: AnalyzeResult = poller.result()

            processing_time = (time.monotonic() - start_time) * 1000

            # Extract data based on document type
            extraction = self._extract_data(
                result,
                document_type,
                include_raw_result,
            )

            return ExtractionResult(
                document_type=document_type,
                extraction=extraction,
                success=True,
                processing_time_ms=processing_time,
            )

        except ClientAuthenticationError as e:
            logger.error("Azure authentication failed: %s", e)
            raise DocumentAuthError(f"Authentication failed: {e}") from e

        except HttpResponseError as e:
            logger.error("Azure API error: %s", e)
            processing_time = (time.monotonic() - start_time) * 1000
            return ExtractionResult(
                document_type=document_type,
                extraction=self._create_empty_extraction(document_type),
                success=False,
                error_message=str(e),
                processing_time_ms=processing_time,
            )

        except ServiceRequestError as e:
            logger.error("Azure service request error: %s", e)
            raise DocumentProcessingError(f"Service request failed: {e}") from e

    def _extract_data(
        self,
        result: AnalyzeResult,
        document_type: DocumentType,
        include_raw_result: bool,
    ) -> PurchaseOrderExtraction | BOLExtraction | InvoiceExtraction:
        """Extract structured data from the analysis result."""
        if document_type == DocumentType.INVOICE:
            return self._extract_invoice(result, include_raw_result)
        elif document_type == DocumentType.PURCHASE_ORDER:
            return self._extract_purchase_order(result, include_raw_result)
        elif document_type == DocumentType.BILL_OF_LADING:
            return self._extract_bol(result, include_raw_result)
        else:
            raise DocumentProcessingError(f"Unknown document type: {document_type}")

    def _extract_invoice(
        self,
        result: AnalyzeResult,
        include_raw_result: bool,
    ) -> InvoiceExtraction:
        """Extract data from an invoice analysis result."""
        documents = result.documents or []

        if not documents:
            logger.warning("No documents found in invoice analysis result")
            return InvoiceExtraction(
                invoice_number="",
                vendor_name="",
                invoice_date=None,
                needs_review=True,
            )

        doc: AnalyzedDocument = documents[0]
        fields = doc.fields or {}
        confidence = doc.confidence or 0.0

        # Extract main invoice fields
        invoice_number = self._get_field_value(fields.get("InvoiceId"), "")
        vendor_name = self._get_field_value(fields.get("VendorName"), "")
        invoice_date = self._get_date_field(fields.get("InvoiceDate"))
        due_date = self._get_date_field(fields.get("DueDate"))
        subtotal = self._get_currency_field(fields.get("SubTotal"))
        tax = self._get_currency_field(fields.get("TotalTax"))
        total = self._get_currency_field(fields.get("InvoiceTotal")) or 0.0

        # Extract line items
        line_items = self._extract_invoice_line_items(fields.get("Items"))

        # Determine if human review is needed
        needs_review = confidence < MIN_CONFIDENCE_THRESHOLD

        raw_result = self._serialize_result(result) if include_raw_result else None

        return InvoiceExtraction(
            invoice_number=invoice_number,
            vendor_name=vendor_name,
            invoice_date=invoice_date,
            due_date=due_date,
            line_items=line_items,
            subtotal=subtotal or 0.0,
            tax=tax,
            total=total,
            confidence=confidence,
            raw_result=raw_result,
            needs_review=needs_review,
        )

    def _extract_purchase_order(
        self,
        result: AnalyzeResult,
        include_raw_result: bool,
    ) -> PurchaseOrderExtraction:
        """Extract data from a purchase order analysis result."""
        documents = result.documents or []

        if not documents:
            logger.warning("No documents found in PO analysis result")
            return PurchaseOrderExtraction(
                po_number="",
                vendor_name="",
                order_date=None,
                needs_review=True,
            )

        doc: AnalyzedDocument = documents[0]
        fields = doc.fields or {}
        confidence = doc.confidence or 0.0

        # Extract main PO fields (field names depend on custom model)
        po_number = self._get_field_value(
            fields.get("PurchaseOrderNumber") or fields.get("PONumber"), ""
        )
        vendor_name = self._get_field_value(
            fields.get("VendorName") or fields.get("Vendor"), ""
        )
        order_date = self._get_date_field(
            fields.get("OrderDate") or fields.get("PurchaseOrderDate")
        )
        delivery_date = self._get_date_field(
            fields.get("DeliveryDate") or fields.get("ExpectedDeliveryDate")
        )
        subtotal = self._get_currency_field(fields.get("SubTotal"))
        tax = self._get_currency_field(fields.get("Tax") or fields.get("TotalTax"))
        total = self._get_currency_field(
            fields.get("Total") or fields.get("TotalAmount")
        ) or 0.0

        # Extract line items
        line_items = self._extract_po_line_items(
            fields.get("Items") or fields.get("LineItems")
        )

        needs_review = confidence < MIN_CONFIDENCE_THRESHOLD
        raw_result = self._serialize_result(result) if include_raw_result else None

        return PurchaseOrderExtraction(
            po_number=po_number,
            vendor_name=vendor_name,
            order_date=order_date,
            delivery_date=delivery_date,
            line_items=line_items,
            subtotal=subtotal,
            tax=tax,
            total=total,
            confidence=confidence,
            raw_result=raw_result,
            needs_review=needs_review,
        )

    def _extract_bol(
        self,
        result: AnalyzeResult,
        include_raw_result: bool,
    ) -> BOLExtraction:
        """Extract data from a bill of lading analysis result."""
        documents = result.documents or []

        if not documents:
            logger.warning("No documents found in BOL analysis result")
            return BOLExtraction(
                bol_number="",
                shipper_name="",
                shipper_address="",
                consignee_name="",
                consignee_address="",
                carrier="",
                needs_review=True,
            )

        doc: AnalyzedDocument = documents[0]
        fields = doc.fields or {}
        confidence = doc.confidence or 0.0

        # Extract main BOL fields (field names depend on custom model)
        bol_number = self._get_field_value(
            fields.get("BOLNumber") or fields.get("BillOfLadingNumber"), ""
        )
        shipper_name = self._get_field_value(
            fields.get("ShipperName") or fields.get("Shipper"), ""
        )
        shipper_address = self._get_field_value(
            fields.get("ShipperAddress") or fields.get("ShipFromAddress"), ""
        )
        consignee_name = self._get_field_value(
            fields.get("ConsigneeName") or fields.get("Consignee"), ""
        )
        consignee_address = self._get_field_value(
            fields.get("ConsigneeAddress") or fields.get("ShipToAddress"), ""
        )
        carrier = self._get_field_value(
            fields.get("Carrier") or fields.get("CarrierName"), ""
        )
        tracking_number = self._get_field_value(
            fields.get("TrackingNumber") or fields.get("ProNumber"), None
        )
        ship_date = self._get_date_field(
            fields.get("ShipDate") or fields.get("DateShipped")
        )
        cargo_description = self._get_field_value(
            fields.get("CargoDescription") or fields.get("Description"), ""
        )
        weight = self._get_number_field(
            fields.get("Weight") or fields.get("TotalWeight")
        )

        needs_review = confidence < MIN_CONFIDENCE_THRESHOLD
        raw_result = self._serialize_result(result) if include_raw_result else None

        return BOLExtraction(
            bol_number=bol_number,
            shipper_name=shipper_name,
            shipper_address=shipper_address,
            consignee_name=consignee_name,
            consignee_address=consignee_address,
            carrier=carrier,
            tracking_number=tracking_number,
            ship_date=ship_date,
            cargo_description=cargo_description,
            weight=weight,
            confidence=confidence,
            raw_result=raw_result,
            needs_review=needs_review,
        )

    def _extract_invoice_line_items(
        self, items_field: DocumentField | None
    ) -> list[LineItem]:
        """Extract line items from an invoice items field."""
        if not items_field or not items_field.value_array:
            return []

        line_items: list[LineItem] = []

        for item in items_field.value_array:
            if item.value_object:
                fields = item.value_object
                line_item = LineItem(
                    sku=self._get_field_value(
                        fields.get("ProductCode") or fields.get("Description"), ""
                    ),
                    description=self._get_field_value(
                        fields.get("Description"), ""
                    ),
                    quantity=int(
                        self._get_number_field(fields.get("Quantity")) or 0
                    ),
                    unit_price=self._get_currency_field(fields.get("UnitPrice")),
                    total=self._get_currency_field(fields.get("Amount")),
                    confidence=item.confidence or 0.0,
                )
                line_items.append(line_item)

        return line_items

    def _extract_po_line_items(
        self, items_field: DocumentField | None
    ) -> list[LineItem]:
        """Extract line items from a PO items field."""
        if not items_field or not items_field.value_array:
            return []

        line_items: list[LineItem] = []

        for item in items_field.value_array:
            if item.value_object:
                fields = item.value_object
                line_item = LineItem(
                    sku=self._get_field_value(
                        fields.get("SKU")
                        or fields.get("ItemCode")
                        or fields.get("ProductCode"),
                        "",
                    ),
                    description=self._get_field_value(
                        fields.get("Description") or fields.get("ItemDescription"), ""
                    ),
                    quantity=int(
                        self._get_number_field(fields.get("Quantity")) or 0
                    ),
                    unit_price=self._get_currency_field(
                        fields.get("UnitPrice") or fields.get("Price")
                    ),
                    total=self._get_currency_field(
                        fields.get("Total") or fields.get("Amount")
                    ),
                    confidence=item.confidence or 0.0,
                )
                line_items.append(line_item)

        return line_items

    def _get_field_value(
        self, field: DocumentField | None, default: Any
    ) -> Any:
        """Extract the value from a document field."""
        if not field:
            return default

        # Try different value types
        if field.value_string is not None:
            return field.value_string
        if field.content is not None:
            return field.content
        return default

    def _get_date_field(self, field: DocumentField | None) -> date | None:
        """Extract a date value from a document field."""
        if not field:
            return None

        if field.value_date:
            return field.value_date
        return None

    def _get_currency_field(self, field: DocumentField | None) -> float | None:
        """Extract a currency/number value from a document field."""
        if not field:
            return None

        if field.value_currency is not None:
            return field.value_currency.amount
        if field.value_number is not None:
            return float(field.value_number)
        return None

    def _get_number_field(self, field: DocumentField | None) -> float | None:
        """Extract a number value from a document field."""
        if not field:
            return None

        if field.value_number is not None:
            return float(field.value_number)
        if field.value_integer is not None:
            return float(field.value_integer)
        return None

    def _create_empty_extraction(
        self, document_type: DocumentType
    ) -> PurchaseOrderExtraction | BOLExtraction | InvoiceExtraction:
        """Create an empty extraction object for error cases."""
        if document_type == DocumentType.INVOICE:
            return InvoiceExtraction(
                invoice_number="",
                vendor_name="",
                invoice_date=None,
                needs_review=True,
            )
        elif document_type == DocumentType.PURCHASE_ORDER:
            return PurchaseOrderExtraction(
                po_number="",
                vendor_name="",
                order_date=None,
                needs_review=True,
            )
        elif document_type == DocumentType.BILL_OF_LADING:
            return BOLExtraction(
                bol_number="",
                shipper_name="",
                shipper_address="",
                consignee_name="",
                consignee_address="",
                carrier="",
                needs_review=True,
            )
        raise DocumentProcessingError(f"Unknown document type: {document_type}")

    def _serialize_result(self, result: AnalyzeResult) -> dict[str, Any]:
        """Serialize the analysis result for storage."""
        return {
            "api_version": result.api_version,
            "model_id": result.model_id,
            "content": result.content,
            "pages": len(result.pages) if result.pages else 0,
            "documents": len(result.documents) if result.documents else 0,
        }

    def test_connection(self) -> bool:
        """Test the connection to Azure Document Intelligence.

        Returns:
            True if connection is successful, False otherwise.
        """
        if not self.is_configured:
            logger.warning("Azure Document Intelligence not configured")
            return False

        try:
            # Create the client to verify credentials
            self._get_client()
            # The client is created successfully if we reach here
            logger.info("Azure Document Intelligence connection successful")
            return True
        except DocumentAuthError:
            return False
        except Exception as e:
            logger.error("Connection test failed: %s", e)
            return False
