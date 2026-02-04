# Spec: Document OCR & Data Extraction

## Job to Be Done
As an operations coordinator, I need POs, BOLs, and invoices automatically extracted into structured data so that order information flows into the system without manual transcription, reducing errors and processing time.

## Requirements
- Integrate with Azure Document Intelligence for OCR
- Define extraction schemas for PO, BOL, and Invoice documents
- Validate extracted fields against business rules
- Link extracted data to source documents
- Handle multi-page documents
- Queue failed extractions for human review
- Support PDF and image formats (JPEG, PNG)

## Acceptance Criteria
- [ ] Azure Document Intelligence connected and authenticated
- [ ] PO extraction: PO#, vendor, items, quantities, dates
- [ ] BOL extraction: shipper, consignee, tracking#, cargo details
- [ ] Invoice extraction: invoice#, amounts, line items, dates
- [ ] Field extraction accuracy >93%
- [ ] Processing time <3 seconds per document
- [ ] Failed extractions queued for human review
- [ ] Extracted data stored with document reference

## Test Cases
| Input | Expected Output |
|-------|-----------------|
| Standard PO PDF | All fields extracted, >95% confidence |
| Handwritten BOL | Fields extracted with accuracy flags |
| Multi-page invoice | All pages processed, line items combined |
| Corrupted PDF | Error logged, queued for manual processing |
| Image-based invoice (scan) | OCR applied, fields extracted |

## Technical Notes
- Azure Document Intelligence: 93% field accuracy, 87% table accuracy
- Fallback to GPT-4o for edge cases (98% accuracy but 33s/page)
- Cost: ~$1.50 per 1000 pages (Azure), $30+ (GPT-4o fallback)
- Pre-built models for invoices; custom models for PO/BOL
- Store both raw OCR output and structured extraction

## Extraction Schemas

```python
from pydantic import BaseModel
from datetime import date
from typing import Optional

class LineItem(BaseModel):
    sku: str
    description: str
    quantity: int
    unit_price: Optional[float]
    total: Optional[float]

class PurchaseOrderExtraction(BaseModel):
    po_number: str
    vendor_name: str
    order_date: date
    delivery_date: Optional[date]
    line_items: list[LineItem]
    subtotal: Optional[float]
    tax: Optional[float]
    total: float
    confidence: float

class BOLExtraction(BaseModel):
    bol_number: str
    shipper_name: str
    shipper_address: str
    consignee_name: str
    consignee_address: str
    carrier: str
    tracking_number: Optional[str]
    ship_date: date
    cargo_description: str
    weight: Optional[float]
    confidence: float

class InvoiceExtraction(BaseModel):
    invoice_number: str
    vendor_name: str
    invoice_date: date
    due_date: Optional[date]
    line_items: list[LineItem]
    subtotal: float
    tax: Optional[float]
    total: float
    confidence: float
```

## Processing Pipeline

```python
from azure.ai.documentintelligence import DocumentIntelligenceClient

async def extract_document(
    document_bytes: bytes,
    document_type: str  # 'PO', 'BOL', 'INVOICE'
) -> dict:
    """
    Extract structured data from document using Azure DI.
    Falls back to GPT-4o for low-confidence extractions.
    """
    client = DocumentIntelligenceClient(endpoint, credential)

    model_id = {
        'PO': 'custom-po-model',
        'BOL': 'custom-bol-model',
        'INVOICE': 'prebuilt-invoice'
    }[document_type]

    result = await client.analyze_document(
        model_id=model_id,
        document=document_bytes
    )

    if result.confidence < 0.85:
        # Fallback to GPT-4o for edge cases
        result = await gpt4o_extraction(document_bytes, document_type)

    return result
```

## Source Reference
- [[ocr-document-ai]] - Azure Document Intelligence implementation
- [[bol-ocr]] - BOL-specific extraction patterns
