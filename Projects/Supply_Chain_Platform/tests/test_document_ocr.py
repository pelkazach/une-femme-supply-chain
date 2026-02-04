"""Tests for Azure Document Intelligence OCR client."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

from src.services.document_ocr import (
    AzureDocumentIntelligenceClient,
    BOLExtraction,
    DocumentAuthError,
    DocumentProcessingError,
    DocumentType,
    ExtractionResult,
    InvoiceExtraction,
    LineItem,
    MIN_CONFIDENCE_THRESHOLD,
    MODEL_IDS,
    PurchaseOrderExtraction,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client() -> AzureDocumentIntelligenceClient:
    """Create a test client with mock credentials."""
    return AzureDocumentIntelligenceClient(
        endpoint="https://test.cognitiveservices.azure.com",
        api_key="test-api-key",
    )


@pytest.fixture
def unconfigured_client() -> AzureDocumentIntelligenceClient:
    """Create a client without credentials."""
    return AzureDocumentIntelligenceClient(endpoint="", api_key="")


@pytest.fixture
def mock_invoice_result() -> MagicMock:
    """Create a mock AnalyzeResult for an invoice."""
    result = MagicMock()
    result.api_version = "2024-02-29-preview"
    result.model_id = "prebuilt-invoice"
    result.content = "Invoice content"
    result.pages = [MagicMock()]

    # Create document fields
    doc = MagicMock()
    doc.confidence = 0.95

    # Invoice fields
    invoice_id = MagicMock()
    invoice_id.value_string = "INV-2024-001"
    invoice_id.content = "INV-2024-001"

    vendor_name = MagicMock()
    vendor_name.value_string = "Wine Supplier Co"
    vendor_name.content = "Wine Supplier Co"

    invoice_date = MagicMock()
    invoice_date.value_date = date(2024, 1, 15)

    due_date = MagicMock()
    due_date.value_date = date(2024, 2, 15)

    subtotal = MagicMock()
    subtotal.value_currency = MagicMock(amount=1000.00)

    tax = MagicMock()
    tax.value_currency = MagicMock(amount=85.00)

    total = MagicMock()
    total.value_currency = MagicMock(amount=1085.00)

    # Line items
    item1 = MagicMock()
    item1.confidence = 0.92
    item1.value_object = {
        "ProductCode": MagicMock(value_string="UFBub250", content="UFBub250"),
        "Description": MagicMock(
            value_string="Une Femme Bubbles 250ml", content="Une Femme Bubbles 250ml"
        ),
        "Quantity": MagicMock(value_number=100),
        "UnitPrice": MagicMock(value_currency=MagicMock(amount=8.00)),
        "Amount": MagicMock(value_currency=MagicMock(amount=800.00)),
    }

    item2 = MagicMock()
    item2.confidence = 0.94
    item2.value_object = {
        "ProductCode": MagicMock(value_string="UFRos250", content="UFRos250"),
        "Description": MagicMock(
            value_string="Une Femme Rose 250ml", content="Une Femme Rose 250ml"
        ),
        "Quantity": MagicMock(value_number=25),
        "UnitPrice": MagicMock(value_currency=MagicMock(amount=8.00)),
        "Amount": MagicMock(value_currency=MagicMock(amount=200.00)),
    }

    items = MagicMock()
    items.value_array = [item1, item2]

    doc.fields = {
        "InvoiceId": invoice_id,
        "VendorName": vendor_name,
        "InvoiceDate": invoice_date,
        "DueDate": due_date,
        "SubTotal": subtotal,
        "TotalTax": tax,
        "InvoiceTotal": total,
        "Items": items,
    }

    result.documents = [doc]
    return result


@pytest.fixture
def mock_po_result() -> MagicMock:
    """Create a mock AnalyzeResult for a purchase order."""
    result = MagicMock()
    result.api_version = "2024-02-29-preview"
    result.model_id = "custom-po-model"
    result.content = "PO content"
    result.pages = [MagicMock(), MagicMock()]

    doc = MagicMock()
    doc.confidence = 0.90

    po_number = MagicMock()
    po_number.value_string = "PO-2024-100"
    po_number.content = "PO-2024-100"

    vendor_name = MagicMock()
    vendor_name.value_string = "RNDC Distribution"
    vendor_name.content = "RNDC Distribution"

    order_date = MagicMock()
    order_date.value_date = date(2024, 1, 10)

    delivery_date = MagicMock()
    delivery_date.value_date = date(2024, 1, 20)

    total = MagicMock()
    total.value_currency = MagicMock(amount=5000.00)

    # Line items
    item = MagicMock()
    item.confidence = 0.88
    item.value_object = {
        "SKU": MagicMock(value_string="UFCha250", content="UFCha250"),
        "Description": MagicMock(
            value_string="Une Femme Chardonnay 250ml", content="Une Femme Chardonnay 250ml"
        ),
        "Quantity": MagicMock(value_number=500),
        "UnitPrice": MagicMock(value_currency=MagicMock(amount=10.00)),
        "Total": MagicMock(value_currency=MagicMock(amount=5000.00)),
    }

    items = MagicMock()
    items.value_array = [item]

    doc.fields = {
        "PurchaseOrderNumber": po_number,
        "VendorName": vendor_name,
        "OrderDate": order_date,
        "DeliveryDate": delivery_date,
        "Total": total,
        "Items": items,
    }

    result.documents = [doc]
    return result


@pytest.fixture
def mock_bol_result() -> MagicMock:
    """Create a mock AnalyzeResult for a bill of lading."""
    result = MagicMock()
    result.api_version = "2024-02-29-preview"
    result.model_id = "custom-bol-model"
    result.content = "BOL content"
    result.pages = [MagicMock()]

    doc = MagicMock()
    doc.confidence = 0.87

    bol_number = MagicMock()
    bol_number.value_string = "BOL-2024-555"
    bol_number.content = "BOL-2024-555"

    shipper_name = MagicMock()
    shipper_name.value_string = "Une Femme Winery"
    shipper_name.content = "Une Femme Winery"

    shipper_address = MagicMock()
    shipper_address.value_string = "123 Vine Street, Napa CA 94558"
    shipper_address.content = "123 Vine Street, Napa CA 94558"

    consignee_name = MagicMock()
    consignee_name.value_string = "RNDC Texas"
    consignee_name.content = "RNDC Texas"

    consignee_address = MagicMock()
    consignee_address.value_string = "456 Warehouse Ave, Dallas TX 75001"
    consignee_address.content = "456 Warehouse Ave, Dallas TX 75001"

    carrier = MagicMock()
    carrier.value_string = "FedEx Freight"
    carrier.content = "FedEx Freight"

    tracking = MagicMock()
    tracking.value_string = "794644790000"
    tracking.content = "794644790000"

    ship_date = MagicMock()
    ship_date.value_date = date(2024, 1, 12)

    cargo = MagicMock()
    cargo.value_string = "50 cases wine products"
    cargo.content = "50 cases wine products"

    weight = MagicMock()
    weight.value_number = 750.5

    doc.fields = {
        "BOLNumber": bol_number,
        "ShipperName": shipper_name,
        "ShipperAddress": shipper_address,
        "ConsigneeName": consignee_name,
        "ConsigneeAddress": consignee_address,
        "Carrier": carrier,
        "TrackingNumber": tracking,
        "ShipDate": ship_date,
        "CargoDescription": cargo,
        "Weight": weight,
    }

    result.documents = [doc]
    return result


@pytest.fixture
def mock_low_confidence_result() -> MagicMock:
    """Create a mock result with low confidence."""
    result = MagicMock()
    result.api_version = "2024-02-29-preview"
    result.model_id = "prebuilt-invoice"
    result.content = "Faded invoice"
    result.pages = [MagicMock()]

    doc = MagicMock()
    doc.confidence = 0.65  # Below MIN_CONFIDENCE_THRESHOLD

    invoice_id = MagicMock()
    invoice_id.value_string = "???-001"

    doc.fields = {"InvoiceId": invoice_id}
    result.documents = [doc]
    return result


# ============================================================================
# Client Initialization Tests
# ============================================================================


class TestClientInitialization:
    """Tests for AzureDocumentIntelligenceClient initialization."""

    def test_init_with_custom_values(self) -> None:
        """Test client initialization with custom values."""
        client = AzureDocumentIntelligenceClient(
            endpoint="https://custom.cognitiveservices.azure.com",
            api_key="custom-key",
        )
        assert client.endpoint == "https://custom.cognitiveservices.azure.com"
        assert client.api_key == "custom-key"
        assert client.is_configured is True

    def test_init_without_config(self) -> None:
        """Test client initialization without configuration."""
        client = AzureDocumentIntelligenceClient(endpoint="", api_key="")
        assert client.is_configured is False

    def test_is_configured_requires_both_values(self) -> None:
        """Test that is_configured requires both endpoint and key."""
        client1 = AzureDocumentIntelligenceClient(
            endpoint="https://test.azure.com", api_key=""
        )
        assert client1.is_configured is False

        client2 = AzureDocumentIntelligenceClient(endpoint="", api_key="key")
        assert client2.is_configured is False

    def test_get_client_raises_auth_error_when_not_configured(
        self, unconfigured_client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test that _get_client raises error when not configured."""
        with pytest.raises(DocumentAuthError) as exc_info:
            unconfigured_client._get_client()
        assert "not configured" in str(exc_info.value).lower()


# ============================================================================
# Model ID Configuration Tests
# ============================================================================


class TestModelIdConfiguration:
    """Tests for document type to model ID mapping."""

    def test_invoice_uses_prebuilt_model(self) -> None:
        """Test that invoices use the prebuilt-invoice model."""
        assert MODEL_IDS[DocumentType.INVOICE] == "prebuilt-invoice"

    def test_po_uses_custom_model(self) -> None:
        """Test that POs use a custom model."""
        assert MODEL_IDS[DocumentType.PURCHASE_ORDER] == "custom-po-model"

    def test_bol_uses_custom_model(self) -> None:
        """Test that BOLs use a custom model."""
        assert MODEL_IDS[DocumentType.BILL_OF_LADING] == "custom-bol-model"


# ============================================================================
# Invoice Extraction Tests
# ============================================================================


class TestInvoiceExtraction:
    """Tests for invoice document extraction."""

    def test_extract_invoice_all_fields(
        self,
        client: AzureDocumentIntelligenceClient,
        mock_invoice_result: MagicMock,
    ) -> None:
        """Test extracting all fields from an invoice."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_invoice_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test pdf content",
                document_type=DocumentType.INVOICE,
            )

            assert result.success is True
            assert result.document_type == DocumentType.INVOICE

            extraction = result.extraction
            assert isinstance(extraction, InvoiceExtraction)
            assert extraction.invoice_number == "INV-2024-001"
            assert extraction.vendor_name == "Wine Supplier Co"
            assert extraction.invoice_date == date(2024, 1, 15)
            assert extraction.due_date == date(2024, 2, 15)
            assert extraction.subtotal == 1000.00
            assert extraction.tax == 85.00
            assert extraction.total == 1085.00
            assert extraction.confidence == 0.95
            assert extraction.needs_review is False

    def test_extract_invoice_line_items(
        self,
        client: AzureDocumentIntelligenceClient,
        mock_invoice_result: MagicMock,
    ) -> None:
        """Test extracting line items from an invoice."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_invoice_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test",
                document_type=DocumentType.INVOICE,
            )

            extraction = result.extraction
            assert isinstance(extraction, InvoiceExtraction)
            assert len(extraction.line_items) == 2

            item1 = extraction.line_items[0]
            assert item1.sku == "UFBub250"
            assert item1.description == "Une Femme Bubbles 250ml"
            assert item1.quantity == 100
            assert item1.unit_price == 8.00
            assert item1.total == 800.00

            item2 = extraction.line_items[1]
            assert item2.sku == "UFRos250"
            assert item2.quantity == 25

    def test_extract_invoice_low_confidence_flags_review(
        self,
        client: AzureDocumentIntelligenceClient,
        mock_low_confidence_result: MagicMock,
    ) -> None:
        """Test that low confidence extractions are flagged for review."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_low_confidence_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test",
                document_type=DocumentType.INVOICE,
            )

            extraction = result.extraction
            assert isinstance(extraction, InvoiceExtraction)
            assert extraction.confidence == 0.65
            assert extraction.needs_review is True

    def test_extract_invoice_no_documents(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test handling when no documents are found in result."""
        mock_result = MagicMock()
        mock_result.documents = []
        mock_result.pages = []
        mock_result.content = ""
        mock_result.api_version = "2024-02-29-preview"
        mock_result.model_id = "prebuilt-invoice"

        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"empty",
                document_type=DocumentType.INVOICE,
            )

            assert result.success is True
            extraction = result.extraction
            assert isinstance(extraction, InvoiceExtraction)
            assert extraction.invoice_number == ""
            assert extraction.needs_review is True


# ============================================================================
# Purchase Order Extraction Tests
# ============================================================================


class TestPurchaseOrderExtraction:
    """Tests for purchase order document extraction."""

    def test_extract_po_all_fields(
        self,
        client: AzureDocumentIntelligenceClient,
        mock_po_result: MagicMock,
    ) -> None:
        """Test extracting all fields from a purchase order."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_po_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test po",
                document_type=DocumentType.PURCHASE_ORDER,
            )

            assert result.success is True
            assert result.document_type == DocumentType.PURCHASE_ORDER

            extraction = result.extraction
            assert isinstance(extraction, PurchaseOrderExtraction)
            assert extraction.po_number == "PO-2024-100"
            assert extraction.vendor_name == "RNDC Distribution"
            assert extraction.order_date == date(2024, 1, 10)
            assert extraction.delivery_date == date(2024, 1, 20)
            assert extraction.total == 5000.00
            assert extraction.confidence == 0.90
            assert extraction.needs_review is False

    def test_extract_po_line_items(
        self,
        client: AzureDocumentIntelligenceClient,
        mock_po_result: MagicMock,
    ) -> None:
        """Test extracting line items from a PO."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_po_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test",
                document_type=DocumentType.PURCHASE_ORDER,
            )

            extraction = result.extraction
            assert isinstance(extraction, PurchaseOrderExtraction)
            assert len(extraction.line_items) == 1

            item = extraction.line_items[0]
            assert item.sku == "UFCha250"
            assert item.quantity == 500
            assert item.unit_price == 10.00
            assert item.total == 5000.00

    def test_extract_po_alternative_field_names(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test extraction with alternative field names."""
        mock_result = MagicMock()
        mock_result.api_version = "2024-02-29-preview"
        mock_result.model_id = "custom-po-model"
        mock_result.content = "PO content"
        mock_result.pages = [MagicMock()]

        doc = MagicMock()
        doc.confidence = 0.88

        # Use alternative field names
        po_number = MagicMock()
        po_number.value_string = "PO-ALT-001"

        vendor = MagicMock()
        vendor.value_string = "Alt Vendor"

        doc.fields = {
            "PONumber": po_number,  # Alternative to PurchaseOrderNumber
            "Vendor": vendor,  # Alternative to VendorName
        }
        mock_result.documents = [doc]

        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test",
                document_type=DocumentType.PURCHASE_ORDER,
            )

            extraction = result.extraction
            assert isinstance(extraction, PurchaseOrderExtraction)
            assert extraction.po_number == "PO-ALT-001"
            assert extraction.vendor_name == "Alt Vendor"


# ============================================================================
# Bill of Lading Extraction Tests
# ============================================================================


class TestBOLExtraction:
    """Tests for bill of lading document extraction."""

    def test_extract_bol_all_fields(
        self,
        client: AzureDocumentIntelligenceClient,
        mock_bol_result: MagicMock,
    ) -> None:
        """Test extracting all fields from a bill of lading."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_bol_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test bol",
                document_type=DocumentType.BILL_OF_LADING,
            )

            assert result.success is True
            assert result.document_type == DocumentType.BILL_OF_LADING

            extraction = result.extraction
            assert isinstance(extraction, BOLExtraction)
            assert extraction.bol_number == "BOL-2024-555"
            assert extraction.shipper_name == "Une Femme Winery"
            assert extraction.shipper_address == "123 Vine Street, Napa CA 94558"
            assert extraction.consignee_name == "RNDC Texas"
            assert extraction.consignee_address == "456 Warehouse Ave, Dallas TX 75001"
            assert extraction.carrier == "FedEx Freight"
            assert extraction.tracking_number == "794644790000"
            assert extraction.ship_date == date(2024, 1, 12)
            assert extraction.cargo_description == "50 cases wine products"
            assert extraction.weight == 750.5
            assert extraction.confidence == 0.87

    def test_extract_bol_flags_review_near_threshold(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test BOL near confidence threshold."""
        mock_result = MagicMock()
        mock_result.api_version = "2024-02-29-preview"
        mock_result.model_id = "custom-bol-model"
        mock_result.content = ""
        mock_result.pages = [MagicMock()]

        doc = MagicMock()
        doc.confidence = 0.84  # Just below threshold
        doc.fields = {}
        mock_result.documents = [doc]

        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test",
                document_type=DocumentType.BILL_OF_LADING,
            )

            extraction = result.extraction
            assert isinstance(extraction, BOLExtraction)
            assert extraction.needs_review is True


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_authentication_error(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test handling of authentication errors."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_get_client.side_effect = DocumentAuthError("Invalid credentials")

            with pytest.raises(DocumentAuthError) as exc_info:
                client.analyze_document(
                    document_bytes=b"test",
                    document_type=DocumentType.INVOICE,
                )
            assert "Invalid credentials" in str(exc_info.value)

    def test_client_authentication_error_from_azure(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test Azure ClientAuthenticationError is converted."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_di_client.begin_analyze_document.side_effect = (
                ClientAuthenticationError("401 Unauthorized")
            )
            mock_get_client.return_value = mock_di_client

            with pytest.raises(DocumentAuthError) as exc_info:
                client.analyze_document(
                    document_bytes=b"test",
                    document_type=DocumentType.INVOICE,
                )
            assert "Authentication failed" in str(exc_info.value)

    def test_http_response_error_returns_failed_result(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test HTTP errors return failed result instead of raising."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_di_client.begin_analyze_document.side_effect = HttpResponseError(
                "Document too large"
            )
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"large document",
                document_type=DocumentType.INVOICE,
            )

            assert result.success is False
            assert result.error_message is not None
            assert "Document too large" in result.error_message
            assert isinstance(result.extraction, InvoiceExtraction)
            assert result.extraction.needs_review is True


# ============================================================================
# Processing Time Tests
# ============================================================================


class TestProcessingTime:
    """Tests for processing time tracking."""

    def test_processing_time_recorded(
        self,
        client: AzureDocumentIntelligenceClient,
        mock_invoice_result: MagicMock,
    ) -> None:
        """Test that processing time is recorded."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_invoice_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test",
                document_type=DocumentType.INVOICE,
            )

            assert result.processing_time_ms >= 0


# ============================================================================
# Raw Result Tests
# ============================================================================


class TestRawResultInclusion:
    """Tests for including raw result in extraction."""

    def test_raw_result_included_when_requested(
        self,
        client: AzureDocumentIntelligenceClient,
        mock_invoice_result: MagicMock,
    ) -> None:
        """Test that raw result is included when requested."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_invoice_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test",
                document_type=DocumentType.INVOICE,
                include_raw_result=True,
            )

            extraction = result.extraction
            assert isinstance(extraction, InvoiceExtraction)
            assert extraction.raw_result is not None
            assert "api_version" in extraction.raw_result
            assert "model_id" in extraction.raw_result

    def test_raw_result_excluded_by_default(
        self,
        client: AzureDocumentIntelligenceClient,
        mock_invoice_result: MagicMock,
    ) -> None:
        """Test that raw result is excluded by default."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_invoice_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test",
                document_type=DocumentType.INVOICE,
            )

            extraction = result.extraction
            assert isinstance(extraction, InvoiceExtraction)
            assert extraction.raw_result is None


# ============================================================================
# Connection Test Tests
# ============================================================================


class TestConnectionTest:
    """Tests for connection testing."""

    def test_connection_success(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test successful connection test."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_get_client.return_value = MagicMock()
            assert client.test_connection() is True

    def test_connection_failure_not_configured(
        self, unconfigured_client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test connection failure when not configured."""
        assert unconfigured_client.test_connection() is False

    def test_connection_failure_auth_error(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test connection failure on auth error."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_get_client.side_effect = DocumentAuthError("Bad credentials")
            assert client.test_connection() is False


# ============================================================================
# Field Extraction Helper Tests
# ============================================================================


class TestFieldExtractionHelpers:
    """Tests for field extraction helper methods."""

    def test_get_field_value_string(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test extracting string value from field."""
        field = MagicMock()
        field.value_string = "test value"
        field.content = "test content"

        result = client._get_field_value(field, "default")
        assert result == "test value"

    def test_get_field_value_content_fallback(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test falling back to content when value_string is None."""
        field = MagicMock()
        field.value_string = None
        field.content = "content value"

        result = client._get_field_value(field, "default")
        assert result == "content value"

    def test_get_field_value_default(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test returning default when field is None."""
        result = client._get_field_value(None, "default")
        assert result == "default"

    def test_get_date_field(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test extracting date value from field."""
        field = MagicMock()
        field.value_date = date(2024, 1, 15)

        result = client._get_date_field(field)
        assert result == date(2024, 1, 15)

    def test_get_date_field_none(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test returning None when date field is None."""
        result = client._get_date_field(None)
        assert result is None

    def test_get_currency_field(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test extracting currency value from field."""
        field = MagicMock()
        field.value_currency = MagicMock(amount=99.99)

        result = client._get_currency_field(field)
        assert result == 99.99

    def test_get_currency_field_number_fallback(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test falling back to value_number for currency."""
        field = MagicMock()
        field.value_currency = None
        field.value_number = 50.0

        result = client._get_currency_field(field)
        assert result == 50.0

    def test_get_number_field_integer(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test extracting integer value from field."""
        field = MagicMock()
        field.value_number = None
        field.value_integer = 42

        result = client._get_number_field(field)
        assert result == 42.0


# ============================================================================
# Empty Extraction Tests
# ============================================================================


class TestEmptyExtraction:
    """Tests for creating empty extraction objects."""

    def test_create_empty_invoice_extraction(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test creating empty invoice extraction."""
        result = client._create_empty_extraction(DocumentType.INVOICE)
        assert isinstance(result, InvoiceExtraction)
        assert result.invoice_number == ""
        assert result.needs_review is True

    def test_create_empty_po_extraction(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test creating empty PO extraction."""
        result = client._create_empty_extraction(DocumentType.PURCHASE_ORDER)
        assert isinstance(result, PurchaseOrderExtraction)
        assert result.po_number == ""
        assert result.needs_review is True

    def test_create_empty_bol_extraction(
        self, client: AzureDocumentIntelligenceClient
    ) -> None:
        """Test creating empty BOL extraction."""
        result = client._create_empty_extraction(DocumentType.BILL_OF_LADING)
        assert isinstance(result, BOLExtraction)
        assert result.bol_number == ""
        assert result.needs_review is True


# ============================================================================
# Data Class Tests
# ============================================================================


class TestDataClasses:
    """Tests for data classes."""

    def test_line_item_defaults(self) -> None:
        """Test LineItem default values."""
        item = LineItem(sku="TEST", description="Test item", quantity=10)
        assert item.unit_price is None
        assert item.total is None
        assert item.confidence == 0.0

    def test_invoice_extraction_defaults(self) -> None:
        """Test InvoiceExtraction default values."""
        extraction = InvoiceExtraction(
            invoice_number="INV-001",
            vendor_name="Vendor",
            invoice_date=date(2024, 1, 1),
        )
        assert extraction.due_date is None
        assert extraction.line_items == []
        assert extraction.subtotal == 0.0
        assert extraction.tax is None
        assert extraction.total == 0.0
        assert extraction.confidence == 0.0
        assert extraction.raw_result is None
        assert extraction.needs_review is False

    def test_po_extraction_defaults(self) -> None:
        """Test PurchaseOrderExtraction default values."""
        extraction = PurchaseOrderExtraction(
            po_number="PO-001",
            vendor_name="Vendor",
            order_date=date(2024, 1, 1),
        )
        assert extraction.delivery_date is None
        assert extraction.line_items == []
        assert extraction.subtotal is None
        assert extraction.tax is None
        assert extraction.total == 0.0

    def test_bol_extraction_defaults(self) -> None:
        """Test BOLExtraction default values."""
        extraction = BOLExtraction(
            bol_number="BOL-001",
            shipper_name="Shipper",
            shipper_address="Address",
            consignee_name="Consignee",
            consignee_address="Address",
            carrier="Carrier",
        )
        assert extraction.tracking_number is None
        assert extraction.ship_date is None
        assert extraction.cargo_description == ""
        assert extraction.weight is None

    def test_extraction_result_defaults(self) -> None:
        """Test ExtractionResult default values."""
        extraction = InvoiceExtraction(
            invoice_number="INV-001",
            vendor_name="Vendor",
            invoice_date=None,
        )
        result = ExtractionResult(
            document_type=DocumentType.INVOICE,
            extraction=extraction,
            success=True,
        )
        assert result.error_message is None
        assert result.processing_time_ms == 0.0


# ============================================================================
# Confidence Threshold Tests
# ============================================================================


class TestConfidenceThreshold:
    """Tests for confidence threshold handling."""

    def test_min_confidence_threshold_value(self) -> None:
        """Test the minimum confidence threshold value."""
        assert MIN_CONFIDENCE_THRESHOLD == 0.85

    def test_extraction_above_threshold_no_review(
        self,
        client: AzureDocumentIntelligenceClient,
        mock_invoice_result: MagicMock,
    ) -> None:
        """Test that extractions above threshold don't need review."""
        mock_invoice_result.documents[0].confidence = 0.90

        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_invoice_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test",
                document_type=DocumentType.INVOICE,
            )

            extraction = result.extraction
            assert isinstance(extraction, InvoiceExtraction)
            assert extraction.needs_review is False

    def test_extraction_at_threshold_no_review(
        self,
        client: AzureDocumentIntelligenceClient,
        mock_invoice_result: MagicMock,
    ) -> None:
        """Test that extractions at exactly threshold don't need review."""
        mock_invoice_result.documents[0].confidence = 0.85

        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_invoice_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test",
                document_type=DocumentType.INVOICE,
            )

            extraction = result.extraction
            assert isinstance(extraction, InvoiceExtraction)
            assert extraction.needs_review is False

    def test_extraction_below_threshold_needs_review(
        self,
        client: AzureDocumentIntelligenceClient,
        mock_invoice_result: MagicMock,
    ) -> None:
        """Test that extractions below threshold need review."""
        mock_invoice_result.documents[0].confidence = 0.84

        with patch.object(client, "_get_client") as mock_get_client:
            mock_di_client = MagicMock()
            mock_poller = MagicMock()
            mock_poller.result.return_value = mock_invoice_result
            mock_di_client.begin_analyze_document.return_value = mock_poller
            mock_get_client.return_value = mock_di_client

            result = client.analyze_document(
                document_bytes=b"test",
                document_type=DocumentType.INVOICE,
            )

            extraction = result.extraction
            assert isinstance(extraction, InvoiceExtraction)
            assert extraction.needs_review is True
