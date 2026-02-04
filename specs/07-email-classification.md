# Spec: Email Classification & Routing

## Job to Be Done
As an operations coordinator, I need incoming emails automatically classified and routed so that POs, BOLs, and invoices are processed without manual sorting, reducing response time and data entry burden.

## Requirements
- Connect to Gmail API for inbox monitoring
- Classify emails into categories: PO, BOL, Invoice, General
- Use local Ollama/Mixtral LLM for cost-effective classification
- Route classified emails to appropriate processing queues
- Extract and forward attachments to document OCR pipeline
- Flag low-confidence classifications (<85%) for human review
- Log all classification decisions with confidence scores

## Acceptance Criteria
- [ ] Gmail API OAuth connection established
- [ ] Email classifier achieves >94% accuracy on test set
- [ ] Processing latency <15 seconds per email
- [ ] Attachments extracted and queued for OCR
- [ ] Human review queue accessible via dashboard
- [ ] Classification decisions logged with confidence scores
- [ ] System handles 100+ emails/day throughput

## Test Cases
| Input | Expected Output |
|-------|-----------------|
| Email with "Purchase Order" in subject, PDF attached | Classified as PO, attachment queued |
| Email with BOL tracking number pattern | Classified as BOL |
| Email with "Invoice #12345" in body | Classified as Invoice |
| Ambiguous email (confidence 70%) | Flagged for human review |
| Email without attachments | Classified, no OCR queue action |

## Technical Notes
- Use Ollama with Mixtral for local inference (~50ms latency)
- RabbitMQ + Celery for distributed queue processing
- Gmail API: Watch endpoint for push notifications vs polling
- Store email metadata, not full content (privacy compliance)
- Retry failed classifications with exponential backoff

## Classification Pipeline

```python
from enum import Enum
from pydantic import BaseModel

class EmailCategory(Enum):
    PURCHASE_ORDER = "PO"
    BILL_OF_LADING = "BOL"
    INVOICE = "INVOICE"
    GENERAL = "GENERAL"

class ClassificationResult(BaseModel):
    category: EmailCategory
    confidence: float
    reasoning: str
    needs_review: bool

async def classify_email(
    subject: str,
    body_preview: str,
    sender: str,
    attachments: list[str]
) -> ClassificationResult:
    """
    Classify email using Ollama/Mixtral.
    Returns category with confidence score.
    """
    prompt = f"""Classify this email into one of: PO, BOL, INVOICE, GENERAL

Subject: {subject}
From: {sender}
Preview: {body_preview[:500]}
Attachments: {', '.join(attachments)}

Return JSON: {{"category": "...", "confidence": 0.0-1.0, "reasoning": "..."}}
"""
    # Ollama inference
    result = await ollama_client.generate(prompt)
    return ClassificationResult(**result)
```

## Source Reference
- [[email-classification]] - LLM classification patterns and accuracy benchmarks
- [[hitl-patterns]] - Human-in-the-loop review queue design
