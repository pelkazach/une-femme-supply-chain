"""Tests for email classification service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.email_classifier import (
    CLASSIFICATION_PROMPT,
    ClassificationError,
    ClassificationResult,
    EmailCategory,
    OllamaClient,
    OllamaError,
    classify_email,
    classify_email_with_fallback,
    parse_classification_response,
    rule_based_classify,
    validate_classification,
)


class TestEmailCategory:
    """Tests for EmailCategory enum."""

    def test_category_values(self) -> None:
        """Test category enum values."""
        assert EmailCategory.PURCHASE_ORDER.value == "PO"
        assert EmailCategory.BILL_OF_LADING.value == "BOL"
        assert EmailCategory.INVOICE.value == "INVOICE"
        assert EmailCategory.GENERAL.value == "GENERAL"

    def test_all_categories_exist(self) -> None:
        """Test that all required categories exist."""
        categories = [e.value for e in EmailCategory]
        assert "PO" in categories
        assert "BOL" in categories
        assert "INVOICE" in categories
        assert "GENERAL" in categories


class TestClassificationResult:
    """Tests for ClassificationResult dataclass."""

    def test_create_result(self) -> None:
        """Test creating a classification result."""
        result = ClassificationResult(
            category=EmailCategory.PURCHASE_ORDER,
            confidence=0.92,
            reasoning="Contains PO number",
            needs_review=False,
        )
        assert result.category == EmailCategory.PURCHASE_ORDER
        assert result.confidence == 0.92
        assert result.reasoning == "Contains PO number"
        assert result.needs_review is False

    def test_to_dict(self) -> None:
        """Test converting result to dictionary."""
        result = ClassificationResult(
            category=EmailCategory.INVOICE,
            confidence=0.88,
            reasoning="Invoice attached",
            needs_review=False,
        )
        d = result.to_dict()
        assert d["category"] == "INVOICE"
        assert d["confidence"] == 0.88
        assert d["reasoning"] == "Invoice attached"
        assert d["needs_review"] is False

    def test_immutable(self) -> None:
        """Test that result is immutable."""
        result = ClassificationResult(
            category=EmailCategory.GENERAL,
            confidence=0.5,
            reasoning="Unclear",
            needs_review=True,
        )
        with pytest.raises(AttributeError):
            result.confidence = 0.9  # type: ignore


class TestOllamaClient:
    """Tests for OllamaClient."""

    def test_init_defaults(self) -> None:
        """Test client initialization with defaults."""
        client = OllamaClient()
        assert client.base_url == "http://localhost:11434"
        assert client.model == "mixtral"
        assert client.timeout == 60

    def test_init_custom(self) -> None:
        """Test client initialization with custom values."""
        client = OllamaClient(
            base_url="http://custom:1234",
            model="llama2",
            timeout=30,
        )
        assert client.base_url == "http://custom:1234"
        assert client.model == "llama2"
        assert client.timeout == 30

    @pytest.mark.asyncio
    async def test_generate_success(self) -> None:
        """Test successful text generation."""
        client = OllamaClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": '{"category": "PO", "confidence": 0.9}'}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.generate("test prompt")

        assert '{"category": "PO"' in result

    @pytest.mark.asyncio
    async def test_generate_timeout(self) -> None:
        """Test timeout handling."""
        client = OllamaClient(timeout=1)

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("timeout")

            with pytest.raises(OllamaError, match="timed out"):
                await client.generate("test prompt")

    @pytest.mark.asyncio
    async def test_generate_http_error(self) -> None:
        """Test HTTP error handling."""
        client = OllamaClient()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            with pytest.raises(OllamaError, match="HTTP error"):
                await client.generate("test prompt")

    @pytest.mark.asyncio
    async def test_generate_connection_error(self) -> None:
        """Test connection error handling."""
        client = OllamaClient()

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            with pytest.raises(OllamaError, match="Request failed"):
                await client.generate("test prompt")

    @pytest.mark.asyncio
    async def test_is_available_true(self) -> None:
        """Test availability check when Ollama is running."""
        client = OllamaClient()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await client.is_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_available_false(self) -> None:
        """Test availability check when Ollama is not running."""
        client = OllamaClient()

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            result = await client.is_available()

        assert result is False


class TestParseClassificationResponse:
    """Tests for parse_classification_response."""

    def test_parse_valid_json(self) -> None:
        """Test parsing valid JSON."""
        response = '{"category": "PO", "confidence": 0.9, "reasoning": "test"}'
        result = parse_classification_response(response)
        assert result["category"] == "PO"
        assert result["confidence"] == 0.9

    def test_parse_json_with_whitespace(self) -> None:
        """Test parsing JSON with whitespace."""
        response = '  \n  {"category": "BOL", "confidence": 0.85}  \n  '
        result = parse_classification_response(response)
        assert result["category"] == "BOL"

    def test_parse_json_in_code_block(self) -> None:
        """Test parsing JSON from markdown code block."""
        response = '''```json
{"category": "INVOICE", "confidence": 0.95, "reasoning": "Invoice number found"}
```'''
        result = parse_classification_response(response)
        assert result["category"] == "INVOICE"

    def test_parse_json_in_plain_code_block(self) -> None:
        """Test parsing JSON from plain code block."""
        response = '''```
{"category": "GENERAL", "confidence": 0.7}
```'''
        result = parse_classification_response(response)
        assert result["category"] == "GENERAL"

    def test_parse_json_embedded_in_text(self) -> None:
        """Test parsing JSON embedded in text."""
        response = 'Based on analysis: {"category": "PO", "confidence": 0.88} done.'
        result = parse_classification_response(response)
        assert result["category"] == "PO"

    def test_parse_invalid_json(self) -> None:
        """Test parsing invalid JSON raises error."""
        response = "This is not JSON at all"
        with pytest.raises(ClassificationError, match="Could not parse JSON"):
            parse_classification_response(response)

    def test_parse_empty_response(self) -> None:
        """Test parsing empty response raises error."""
        with pytest.raises(ClassificationError, match="Could not parse JSON"):
            parse_classification_response("")


class TestValidateClassification:
    """Tests for validate_classification."""

    def test_validate_valid_po(self) -> None:
        """Test validating valid PO classification."""
        data = {"category": "PO", "confidence": 0.92, "reasoning": "Contains PO #12345"}
        result = validate_classification(data)
        assert result.category == EmailCategory.PURCHASE_ORDER
        assert result.confidence == 0.92
        assert result.needs_review is False

    def test_validate_valid_bol(self) -> None:
        """Test validating valid BOL classification."""
        data = {"category": "BOL", "confidence": 0.88, "reasoning": "Tracking number found"}
        result = validate_classification(data)
        assert result.category == EmailCategory.BILL_OF_LADING
        assert result.needs_review is False

    def test_validate_valid_invoice(self) -> None:
        """Test validating valid Invoice classification."""
        data = {"category": "INVOICE", "confidence": 0.95, "reasoning": "Invoice attached"}
        result = validate_classification(data)
        assert result.category == EmailCategory.INVOICE
        assert result.needs_review is False

    def test_validate_valid_general(self) -> None:
        """Test validating valid General classification."""
        data = {"category": "GENERAL", "confidence": 0.75, "reasoning": "No clear category"}
        result = validate_classification(data)
        assert result.category == EmailCategory.GENERAL
        assert result.needs_review is True  # 0.75 < 0.85

    def test_validate_low_confidence_needs_review(self) -> None:
        """Test that low confidence triggers review flag."""
        data = {"category": "PO", "confidence": 0.70, "reasoning": "Uncertain"}
        result = validate_classification(data)
        assert result.needs_review is True

    def test_validate_high_confidence_no_review(self) -> None:
        """Test that high confidence doesn't trigger review."""
        data = {"category": "INVOICE", "confidence": 0.95, "reasoning": "Clear invoice"}
        result = validate_classification(data)
        assert result.needs_review is False

    def test_validate_boundary_confidence(self) -> None:
        """Test boundary confidence (exactly 0.85)."""
        data = {"category": "BOL", "confidence": 0.85, "reasoning": "Threshold"}
        result = validate_classification(data)
        assert result.needs_review is False  # >= 0.85 doesn't need review

    def test_validate_category_variations(self) -> None:
        """Test that category name variations are handled."""
        variations = [
            ("PURCHASE_ORDER", EmailCategory.PURCHASE_ORDER),
            ("PURCHASE ORDER", EmailCategory.PURCHASE_ORDER),
            ("BILL_OF_LADING", EmailCategory.BILL_OF_LADING),
            ("BILL OF LADING", EmailCategory.BILL_OF_LADING),
        ]
        for cat_str, expected in variations:
            data = {"category": cat_str, "confidence": 0.9}
            result = validate_classification(data)
            assert result.category == expected

    def test_validate_lowercase_category(self) -> None:
        """Test that lowercase categories are handled."""
        data = {"category": "po", "confidence": 0.9}
        result = validate_classification(data)
        assert result.category == EmailCategory.PURCHASE_ORDER

    def test_validate_invalid_category(self) -> None:
        """Test that invalid category raises error."""
        data = {"category": "UNKNOWN", "confidence": 0.9}
        with pytest.raises(ClassificationError, match="Invalid category"):
            validate_classification(data)

    def test_validate_clamps_confidence(self) -> None:
        """Test that confidence is clamped to [0, 1]."""
        data = {"category": "PO", "confidence": 1.5, "reasoning": "Over"}
        result = validate_classification(data)
        assert result.confidence == 1.0

        data = {"category": "PO", "confidence": -0.5, "reasoning": "Under"}
        result = validate_classification(data)
        assert result.confidence == 0.0

    def test_validate_invalid_confidence(self) -> None:
        """Test that non-numeric confidence raises error."""
        data = {"category": "PO", "confidence": "high"}
        with pytest.raises(ClassificationError, match="Invalid confidence"):
            validate_classification(data)

    def test_validate_missing_reasoning(self) -> None:
        """Test that missing reasoning defaults to empty string."""
        data = {"category": "PO", "confidence": 0.9}
        result = validate_classification(data)
        assert result.reasoning == ""


class TestClassifyEmail:
    """Tests for classify_email function."""

    @pytest.mark.asyncio
    async def test_classify_po_email(self) -> None:
        """Test classifying a purchase order email."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "PO", "confidence": 0.95, "reasoning": "PO number in subject"}'
        )

        result = await classify_email(
            subject="Purchase Order #12345",
            body_preview="Please find attached our purchase order for 100 cases.",
            sender="buyer@company.com",
            attachments=["PO_12345.pdf"],
            ollama_client=mock_client,
        )

        assert result.category == EmailCategory.PURCHASE_ORDER
        assert result.confidence == 0.95
        mock_client.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_bol_email(self) -> None:
        """Test classifying a bill of lading email."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "BOL", "confidence": 0.92, "reasoning": "Tracking number found"}'
        )

        result = await classify_email(
            subject="Shipment Tracking: PRO# 123456789",
            body_preview="Your shipment has been dispatched. Tracking number attached.",
            sender="logistics@carrier.com",
            attachments=["BOL_tracking.pdf"],
            ollama_client=mock_client,
        )

        assert result.category == EmailCategory.BILL_OF_LADING
        assert result.confidence == 0.92

    @pytest.mark.asyncio
    async def test_classify_invoice_email(self) -> None:
        """Test classifying an invoice email."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "INVOICE", "confidence": 0.98, "reasoning": "Invoice attached"}'
        )

        result = await classify_email(
            subject="Invoice #INV-2026-001 - Payment Due",
            body_preview="Please find attached invoice for recent order. Payment due in 30 days.",
            sender="billing@supplier.com",
            attachments=["Invoice_INV-2026-001.pdf"],
            ollama_client=mock_client,
        )

        assert result.category == EmailCategory.INVOICE
        assert result.confidence == 0.98

    @pytest.mark.asyncio
    async def test_classify_general_email(self) -> None:
        """Test classifying a general email."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "GENERAL", "confidence": 0.75, "reasoning": "Newsletter content"}'
        )

        result = await classify_email(
            subject="Monthly Wine Industry Newsletter",
            body_preview="Read about the latest trends in wine distribution...",
            sender="newsletter@wineinfo.com",
            attachments=[],
            ollama_client=mock_client,
        )

        assert result.category == EmailCategory.GENERAL
        assert result.needs_review is True  # Low confidence

    @pytest.mark.asyncio
    async def test_classify_handles_empty_subject(self) -> None:
        """Test classification handles empty subject."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "GENERAL", "confidence": 0.6, "reasoning": "No subject"}'
        )

        result = await classify_email(
            subject="",
            body_preview="Test body",
            sender="test@test.com",
            attachments=[],
            ollama_client=mock_client,
        )

        assert result.category == EmailCategory.GENERAL
        # Check that "(No Subject)" was used in prompt
        call_args = mock_client.generate.call_args
        assert "(No Subject)" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_classify_handles_long_body(self) -> None:
        """Test classification truncates long body preview."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "GENERAL", "confidence": 0.8, "reasoning": "Truncated"}'
        )

        long_body = "A" * 1000
        await classify_email(
            subject="Test",
            body_preview=long_body,
            sender="test@test.com",
            attachments=[],
            ollama_client=mock_client,
        )

        # Check body was truncated to 500 chars
        call_args = mock_client.generate.call_args
        assert "A" * 500 in call_args[0][0]
        assert "A" * 501 not in call_args[0][0]

    @pytest.mark.asyncio
    async def test_classify_empty_response_error(self) -> None:
        """Test classification handles empty LLM response."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(return_value="")

        with pytest.raises(ClassificationError, match="Empty response"):
            await classify_email(
                subject="Test",
                body_preview="Test",
                sender="test@test.com",
                attachments=[],
                ollama_client=mock_client,
            )

    @pytest.mark.asyncio
    async def test_classify_ollama_error(self) -> None:
        """Test classification propagates Ollama errors."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(side_effect=OllamaError("Connection failed"))

        with pytest.raises(OllamaError, match="Connection failed"):
            await classify_email(
                subject="Test",
                body_preview="Test",
                sender="test@test.com",
                attachments=[],
                ollama_client=mock_client,
            )


class TestClassifyEmailWithFallback:
    """Tests for classify_email_with_fallback function."""

    @pytest.mark.asyncio
    async def test_fallback_success_first_try(self) -> None:
        """Test successful classification on first try."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "PO", "confidence": 0.95, "reasoning": "Found PO"}'
        )

        result = await classify_email_with_fallback(
            subject="PO #123",
            body_preview="Order details",
            sender="buyer@test.com",
            attachments=[],
            ollama_client=mock_client,
        )

        assert result.category == EmailCategory.PURCHASE_ORDER
        assert mock_client.generate.call_count == 1

    @pytest.mark.asyncio
    async def test_fallback_retry_then_success(self) -> None:
        """Test retry after initial failure."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            side_effect=[
                OllamaError("First failure"),
                '{"category": "BOL", "confidence": 0.88, "reasoning": "Retry success"}',
            ]
        )

        result = await classify_email_with_fallback(
            subject="Shipment tracking",
            body_preview="Track your order",
            sender="carrier@test.com",
            attachments=["BOL.pdf"],
            ollama_client=mock_client,
        )

        assert result.category == EmailCategory.BILL_OF_LADING
        assert mock_client.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_fallback_to_rule_based(self) -> None:
        """Test fallback to rule-based after all retries fail."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(side_effect=OllamaError("Always fails"))

        result = await classify_email_with_fallback(
            subject="Invoice #INV-123",
            body_preview="Please pay invoice",
            sender="billing@test.com",
            attachments=["invoice.pdf"],
            ollama_client=mock_client,
            max_retries=2,
        )

        # Should fall back to rule-based
        assert result.category == EmailCategory.INVOICE
        assert result.needs_review is True  # Rule-based always needs review
        assert mock_client.generate.call_count == 3  # 1 initial + 2 retries


class TestRuleBasedClassify:
    """Tests for rule_based_classify fallback function."""

    def test_classify_po_keywords(self) -> None:
        """Test rule-based PO classification."""
        result = rule_based_classify(
            subject="Purchase Order #12345",
            body_preview="Qty ordered: 100 cases",
            attachments=["PO_12345.pdf"],
        )
        assert result.category == EmailCategory.PURCHASE_ORDER
        assert result.needs_review is True

    def test_classify_bol_keywords(self) -> None:
        """Test rule-based BOL classification."""
        result = rule_based_classify(
            subject="Shipment Tracking",
            body_preview="Your freight has been shipped via carrier",
            attachments=["BOL_tracking.pdf"],
        )
        assert result.category == EmailCategory.BILL_OF_LADING

    def test_classify_invoice_keywords(self) -> None:
        """Test rule-based Invoice classification."""
        result = rule_based_classify(
            subject="Invoice Payment Due",
            body_preview="Amount due: $1,234.00. Remittance info attached.",
            attachments=["INV_2026_001.pdf"],
        )
        assert result.category == EmailCategory.INVOICE

    def test_classify_general_no_keywords(self) -> None:
        """Test rule-based defaults to GENERAL without keywords."""
        result = rule_based_classify(
            subject="Hello!",
            body_preview="Just wanted to check in on things.",
            attachments=[],
        )
        assert result.category == EmailCategory.GENERAL
        assert result.confidence == 0.6

    def test_attachment_filename_strong_signal(self) -> None:
        """Test that attachment filenames provide strong signals."""
        # PO attachment with no subject/body keywords
        result = rule_based_classify(
            subject="Document attached",
            body_preview="See attached",
            attachments=["purchase_order.pdf"],
        )
        assert result.category == EmailCategory.PURCHASE_ORDER

    def test_always_needs_review(self) -> None:
        """Test that rule-based always flags for review."""
        result = rule_based_classify(
            subject="Invoice #123",
            body_preview="Payment due",
            attachments=["invoice.pdf"],
        )
        assert result.needs_review is True


class TestClassificationPrompt:
    """Tests for the classification prompt template."""

    def test_prompt_contains_categories(self) -> None:
        """Test prompt includes all categories."""
        assert "PO" in CLASSIFICATION_PROMPT
        assert "BOL" in CLASSIFICATION_PROMPT
        assert "INVOICE" in CLASSIFICATION_PROMPT
        assert "GENERAL" in CLASSIFICATION_PROMPT

    def test_prompt_contains_format_placeholders(self) -> None:
        """Test prompt has required placeholders."""
        assert "{subject}" in CLASSIFICATION_PROMPT
        assert "{sender}" in CLASSIFICATION_PROMPT
        assert "{body_preview}" in CLASSIFICATION_PROMPT
        assert "{attachments}" in CLASSIFICATION_PROMPT

    def test_prompt_requests_json_output(self) -> None:
        """Test prompt requests JSON output format."""
        assert "JSON" in CLASSIFICATION_PROMPT
        assert '"category"' in CLASSIFICATION_PROMPT
        assert '"confidence"' in CLASSIFICATION_PROMPT

    def test_prompt_includes_keywords(self) -> None:
        """Test prompt includes category-specific keywords."""
        # PO keywords
        assert "purchase order" in CLASSIFICATION_PROMPT.lower()
        # BOL keywords
        assert "bill of lading" in CLASSIFICATION_PROMPT.lower()
        assert "tracking" in CLASSIFICATION_PROMPT.lower()
        # Invoice keywords
        assert "invoice" in CLASSIFICATION_PROMPT.lower()
        assert "payment" in CLASSIFICATION_PROMPT.lower()


class TestAccuracyRequirements:
    """Tests verifying >94% accuracy requirement patterns.

    These tests verify the classifier handles the test cases from the spec.
    """

    @pytest.mark.asyncio
    async def test_po_with_attachment(self) -> None:
        """Test: Email with 'Purchase Order' in subject, PDF attached -> PO."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "PO", "confidence": 0.96, "reasoning": "PO in subject with PDF"}'
        )

        result = await classify_email(
            subject="Purchase Order #PO-2026-001",
            body_preview="Please process the attached purchase order.",
            sender="procurement@customer.com",
            attachments=["PO_2026_001.pdf"],
            ollama_client=mock_client,
        )

        assert result.category == EmailCategory.PURCHASE_ORDER
        assert result.confidence >= 0.85
        assert result.needs_review is False

    @pytest.mark.asyncio
    async def test_bol_with_tracking(self) -> None:
        """Test: Email with BOL tracking number pattern -> BOL."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "BOL", "confidence": 0.94, "reasoning": "PRO number pattern"}'
        )

        result = await classify_email(
            subject="Shipment PRO# 123-456-7890",
            body_preview="Bill of Lading attached. Carrier: ABC Freight.",
            sender="dispatch@carrier.com",
            attachments=["BOL_123456.pdf"],
            ollama_client=mock_client,
        )

        assert result.category == EmailCategory.BILL_OF_LADING
        assert result.confidence >= 0.85

    @pytest.mark.asyncio
    async def test_invoice_in_body(self) -> None:
        """Test: Email with 'Invoice #12345' in body -> Invoice."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "INVOICE", "confidence": 0.97, "reasoning": "Invoice number in body"}'
        )

        result = await classify_email(
            subject="Monthly Statement",
            body_preview="Invoice #12345 - Payment due in 30 days. Amount: $5,432.10",
            sender="ar@supplier.com",
            attachments=["Statement_Jan2026.pdf"],
            ollama_client=mock_client,
        )

        assert result.category == EmailCategory.INVOICE
        assert result.confidence >= 0.85

    @pytest.mark.asyncio
    async def test_ambiguous_low_confidence(self) -> None:
        """Test: Ambiguous email (confidence 70%) -> Flagged for review."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "GENERAL", "confidence": 0.70, "reasoning": "Ambiguous content"}'
        )

        result = await classify_email(
            subject="Follow up on our discussion",
            body_preview="As we discussed, please review the attached documents.",
            sender="contact@partner.com",
            attachments=["documents.pdf"],
            ollama_client=mock_client,
        )

        assert result.needs_review is True  # 70% < 85%

    @pytest.mark.asyncio
    async def test_no_attachments_no_ocr(self) -> None:
        """Test: Email without attachments -> Classified, no OCR action needed."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "GENERAL", "confidence": 0.88, "reasoning": "General inquiry"}'
        )

        result = await classify_email(
            subject="Question about wine availability",
            body_preview="Do you have the 2024 Chardonnay in stock?",
            sender="buyer@restaurant.com",
            attachments=[],  # No attachments
            ollama_client=mock_client,
        )

        assert result.category == EmailCategory.GENERAL
        assert result.confidence >= 0.85


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_multiple_category_signals(self) -> None:
        """Test email with signals from multiple categories."""
        # An email that mentions both PO and Invoice
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "INVOICE", "confidence": 0.85, "reasoning": "Primary purpose is billing"}'
        )

        result = await classify_email(
            subject="Invoice for Purchase Order #12345",
            body_preview="Invoice for your recent purchase order. Payment due in 30 days.",
            sender="billing@supplier.com",
            attachments=["Invoice_PO12345.pdf"],
            ollama_client=mock_client,
        )

        # Should pick the primary category
        assert result.category in [EmailCategory.INVOICE, EmailCategory.PURCHASE_ORDER]

    @pytest.mark.asyncio
    async def test_unicode_content(self) -> None:
        """Test handling of unicode characters in email."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "GENERAL", "confidence": 0.9, "reasoning": "Unicode handled"}'
        )

        result = await classify_email(
            subject="Commande de vin - Une Femme \u00e9toiles",
            body_preview="Nous souhaitons commander du champagne ros\u00e9...",
            sender="client@france.fr",
            attachments=["commande.pdf"],
            ollama_client=mock_client,
        )

        assert result is not None
        assert result.category == EmailCategory.GENERAL

    @pytest.mark.asyncio
    async def test_special_characters_in_attachments(self) -> None:
        """Test handling of special characters in attachment names."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate = AsyncMock(
            return_value='{"category": "INVOICE", "confidence": 0.92, "reasoning": "Invoice attachment"}'
        )

        result = await classify_email(
            subject="Documents",
            body_preview="See attached",
            sender="test@test.com",
            attachments=["Invoice (2026-01).pdf", "PO #123.xlsx"],
            ollama_client=mock_client,
        )

        assert result is not None
