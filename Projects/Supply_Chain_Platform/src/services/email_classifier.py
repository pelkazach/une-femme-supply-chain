"""Email classification service using Ollama/Mixtral.

This module provides email classification into categories (PO, BOL, Invoice, General)
using a local Ollama LLM for cost-effective inference.
"""

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class EmailCategory(Enum):
    """Email classification categories."""

    PURCHASE_ORDER = "PO"
    BILL_OF_LADING = "BOL"
    INVOICE = "INVOICE"
    GENERAL = "GENERAL"


class OllamaError(Exception):
    """Raised when Ollama API call fails."""


class ClassificationError(Exception):
    """Raised when email classification fails."""


@dataclass(frozen=True)
class ClassificationResult:
    """Result of email classification."""

    category: EmailCategory
    confidence: float
    reasoning: str
    needs_review: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "needs_review": self.needs_review,
        }


# Classification prompt template
CLASSIFICATION_PROMPT = """You are an email classifier for a wine supply chain company. Your task is to classify incoming emails into one of four categories based on their content.

CATEGORIES:
1. PO (Purchase Order) - Emails containing or requesting purchase orders, order confirmations, order modifications, reorder requests
2. BOL (Bill of Lading) - Emails about shipping documents, tracking information, freight documents, delivery confirmations, carrier information
3. INVOICE - Emails containing invoices, payment requests, billing statements, account statements, payment reminders
4. GENERAL - All other emails including general inquiries, marketing, newsletters, internal communications

CLASSIFICATION RULES:
- Look for specific keywords and patterns in subject, body, and attachment names
- PO indicators: "purchase order", "PO #", "order confirmation", "reorder", "qty", "unit price"
- BOL indicators: "bill of lading", "BOL", "tracking", "shipment", "freight", "carrier", "pro number", "delivery"
- INVOICE indicators: "invoice", "INV #", "payment due", "billing", "amount due", "remittance", "statement"
- Attachment filenames are strong signals (e.g., "PO_12345.pdf" = PO, "BOL_tracking.pdf" = BOL)
- When multiple categories seem applicable, choose the PRIMARY purpose of the email
- If unsure, classify as GENERAL with lower confidence

EMAIL TO CLASSIFY:
Subject: {subject}
From: {sender}
Body Preview: {body_preview}
Attachments: {attachments}

Respond with ONLY a valid JSON object in this exact format (no other text):
{{"category": "PO|BOL|INVOICE|GENERAL", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}
"""


class OllamaClient:
    """Client for Ollama local LLM API.

    Provides async interface to Ollama for text generation.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        """Initialize Ollama client.

        Args:
            base_url: Ollama API base URL. Defaults to settings.ollama_base_url.
            model: Model name to use. Defaults to settings.ollama_model.
            timeout: Request timeout in seconds. Defaults to settings.ollama_timeout.
        """
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 256,
    ) -> str:
        """Generate text completion using Ollama.

        Args:
            prompt: The prompt to send to the model.
            temperature: Sampling temperature (0.0-1.0). Lower = more deterministic.
            max_tokens: Maximum tokens to generate.

        Returns:
            Generated text response.

        Raises:
            OllamaError: If the API call fails.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                data: dict[str, Any] = response.json()
                result: str = data.get("response", "")
                return result

        except httpx.TimeoutException as e:
            logger.error("Ollama request timed out: %s", e)
            raise OllamaError(f"Request timed out after {self.timeout}s") from e
        except httpx.HTTPStatusError as e:
            logger.error("Ollama HTTP error: %s", e)
            raise OllamaError(f"HTTP error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("Ollama request failed: %s", e)
            raise OllamaError(f"Request failed: {e}") from e

    async def is_available(self) -> bool:
        """Check if Ollama service is available.

        Returns:
            True if Ollama is running and responsive.
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except httpx.RequestError:
            return False


def parse_classification_response(response: str) -> dict[str, Any]:
    """Parse JSON response from LLM.

    Handles common response format variations.

    Args:
        response: Raw text response from LLM.

    Returns:
        Parsed JSON dictionary.

    Raises:
        ClassificationError: If response cannot be parsed.
    """
    # Try to find JSON in the response
    response = response.strip()

    # Try direct parse first
    try:
        parsed: dict[str, Any] = json.loads(response)
        return parsed
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            return parsed
        except json.JSONDecodeError:
            pass

    # Try to find any JSON object in the response
    json_match = re.search(r"\{[^{}]*\}", response)
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            return parsed
        except json.JSONDecodeError:
            pass

    raise ClassificationError(f"Could not parse JSON from response: {response[:200]}")


def validate_classification(data: dict[str, Any]) -> ClassificationResult:
    """Validate and convert parsed response to ClassificationResult.

    Args:
        data: Parsed JSON dictionary.

    Returns:
        Validated ClassificationResult.

    Raises:
        ClassificationError: If data is invalid.
    """
    # Validate category
    category_str = data.get("category", "").upper()

    # Map common variations
    category_map = {
        "PO": EmailCategory.PURCHASE_ORDER,
        "PURCHASE_ORDER": EmailCategory.PURCHASE_ORDER,
        "PURCHASE ORDER": EmailCategory.PURCHASE_ORDER,
        "BOL": EmailCategory.BILL_OF_LADING,
        "BILL_OF_LADING": EmailCategory.BILL_OF_LADING,
        "BILL OF LADING": EmailCategory.BILL_OF_LADING,
        "INVOICE": EmailCategory.INVOICE,
        "GENERAL": EmailCategory.GENERAL,
    }

    category = category_map.get(category_str)
    if category is None:
        raise ClassificationError(f"Invalid category: {category_str}")

    # Validate confidence
    try:
        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
    except (TypeError, ValueError) as e:
        raise ClassificationError(f"Invalid confidence value: {data.get('confidence')}") from e

    # Get reasoning
    reasoning = str(data.get("reasoning", ""))

    # Determine if human review is needed
    needs_review = confidence < 0.85

    return ClassificationResult(
        category=category,
        confidence=confidence,
        reasoning=reasoning,
        needs_review=needs_review,
    )


async def classify_email(
    subject: str,
    body_preview: str,
    sender: str,
    attachments: list[str],
    ollama_client: OllamaClient | None = None,
) -> ClassificationResult:
    """Classify an email using Ollama/Mixtral.

    Args:
        subject: Email subject line.
        body_preview: First ~500 chars of email body.
        sender: Sender email address.
        attachments: List of attachment filenames.
        ollama_client: Optional Ollama client instance.

    Returns:
        ClassificationResult with category, confidence, and reasoning.

    Raises:
        ClassificationError: If classification fails.
        OllamaError: If Ollama API call fails.
    """
    if ollama_client is None:
        ollama_client = OllamaClient()

    # Format the prompt
    prompt = CLASSIFICATION_PROMPT.format(
        subject=subject or "(No Subject)",
        sender=sender or "(Unknown)",
        body_preview=(body_preview or "")[:500],
        attachments=", ".join(attachments) if attachments else "(None)",
    )

    # Get classification from LLM
    response = await ollama_client.generate(prompt)

    if not response:
        raise ClassificationError("Empty response from Ollama")

    # Parse and validate response
    parsed = parse_classification_response(response)
    result = validate_classification(parsed)

    logger.info(
        "Classified email '%s' as %s (confidence: %.2f, needs_review: %s)",
        subject[:50] if subject else "(No Subject)",
        result.category.value,
        result.confidence,
        result.needs_review,
    )

    return result


async def classify_email_with_fallback(
    subject: str,
    body_preview: str,
    sender: str,
    attachments: list[str],
    ollama_client: OllamaClient | None = None,
    max_retries: int = 2,
) -> ClassificationResult:
    """Classify email with retry logic and rule-based fallback.

    If Ollama fails after retries, falls back to simple rule-based classification.

    Args:
        subject: Email subject line.
        body_preview: First ~500 chars of email body.
        sender: Sender email address.
        attachments: List of attachment filenames.
        ollama_client: Optional Ollama client instance.
        max_retries: Maximum retry attempts.

    Returns:
        ClassificationResult with category, confidence, and reasoning.
    """
    for attempt in range(max_retries + 1):
        try:
            return await classify_email(
                subject=subject,
                body_preview=body_preview,
                sender=sender,
                attachments=attachments,
                ollama_client=ollama_client,
            )
        except (OllamaError, ClassificationError) as e:
            logger.warning(
                "Classification attempt %d failed: %s",
                attempt + 1,
                e,
            )

    # Fallback to rule-based classification
    logger.warning("Falling back to rule-based classification after %d failures", max_retries + 1)
    return rule_based_classify(subject, body_preview, attachments)


def rule_based_classify(
    subject: str,
    body_preview: str,
    attachments: list[str],
) -> ClassificationResult:
    """Simple rule-based classification fallback.

    Used when Ollama is unavailable.

    Args:
        subject: Email subject line.
        body_preview: Email body preview.
        attachments: List of attachment filenames.

    Returns:
        ClassificationResult based on keyword matching.
    """
    text = f"{subject} {body_preview} {' '.join(attachments)}".lower()

    # Score each category based on keyword matches
    scores: dict[EmailCategory, float] = {
        EmailCategory.PURCHASE_ORDER: 0.0,
        EmailCategory.BILL_OF_LADING: 0.0,
        EmailCategory.INVOICE: 0.0,
        EmailCategory.GENERAL: 0.0,
    }

    # PO keywords
    po_keywords = [
        "purchase order", "po #", "po#", "order confirmation",
        "reorder", "order request", "qty ordered", "unit price",
    ]
    for kw in po_keywords:
        if kw in text:
            scores[EmailCategory.PURCHASE_ORDER] += 0.15

    # BOL keywords
    bol_keywords = [
        "bill of lading", "bol", "tracking", "shipment",
        "freight", "carrier", "pro number", "delivery", "shipped",
    ]
    for kw in bol_keywords:
        if kw in text:
            scores[EmailCategory.BILL_OF_LADING] += 0.15

    # Invoice keywords
    invoice_keywords = [
        "invoice", "inv #", "inv#", "payment due",
        "billing", "amount due", "remittance", "statement",
    ]
    for kw in invoice_keywords:
        if kw in text:
            scores[EmailCategory.INVOICE] += 0.15

    # Check attachment filenames
    for att in attachments:
        att_lower = att.lower()
        if "po" in att_lower or "order" in att_lower:
            scores[EmailCategory.PURCHASE_ORDER] += 0.25
        if "bol" in att_lower or "lading" in att_lower:
            scores[EmailCategory.BILL_OF_LADING] += 0.25
        if "inv" in att_lower or "invoice" in att_lower:
            scores[EmailCategory.INVOICE] += 0.25

    # Find best category
    best_category = max(scores, key=lambda k: scores[k])
    best_score = scores[best_category]

    # If no strong signal, default to GENERAL
    if best_score < 0.15:
        best_category = EmailCategory.GENERAL
        confidence = 0.6
        reasoning = "No strong category indicators found, defaulting to GENERAL"
    else:
        confidence = min(0.75, 0.5 + best_score)  # Cap at 0.75 for rule-based
        reasoning = f"Rule-based classification based on keyword matches (score: {best_score:.2f})"

    return ClassificationResult(
        category=best_category,
        confidence=confidence,
        reasoning=reasoning,
        needs_review=True,  # Always flag rule-based for review
    )
