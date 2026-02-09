"""QuickBooks Invoice model for storing pulled invoice data."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.product import Product


class QBInvoice(Base):
    """QuickBooks Invoice model for AR tracking.

    Stores invoices pulled from QuickBooks Online for accounts receivable
    tracking and revenue recognition.

    Attributes:
        id: Unique identifier (UUID)
        qb_invoice_id: QuickBooks invoice ID (for deduplication)
        invoice_number: Invoice number/document number
        customer_name: Customer display name
        customer_id: QuickBooks customer ID
        invoice_date: Date the invoice was created
        due_date: Payment due date
        total_amount: Total invoice amount
        balance_due: Remaining balance to be paid
        currency_code: Currency code (e.g., USD)
        status: Invoice status (Open, Paid, Overdue, etc.)
        line_items: JSON array of line items
        qb_created_at: When the invoice was created in QuickBooks
        qb_updated_at: When the invoice was last updated in QuickBooks
        synced_at: When this record was synced from QuickBooks
        created_at: When this record was created locally
    """

    __tablename__ = "qb_invoices"
    __table_args__ = (
        Index(
            "idx_qb_invoices_qb_id",
            "qb_invoice_id",
            unique=True,
        ),
        Index(
            "idx_qb_invoices_customer",
            "customer_id",
        ),
        Index(
            "idx_qb_invoices_date",
            "invoice_date",
        ),
        Index(
            "idx_qb_invoices_due_date",
            "due_date",
        ),
        Index(
            "idx_qb_invoices_status",
            "status",
        ),
        Index(
            "idx_qb_invoices_synced",
            "synced_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    qb_invoice_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )
    invoice_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    customer_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    invoice_date: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    due_date: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    total_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=True,
    )
    balance_due: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=True,
    )
    currency_code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="USD",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Open",
    )
    line_items: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    qb_created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    qb_updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    synced_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<QBInvoice(qb_invoice_id={self.qb_invoice_id!r}, "
            f"invoice_number={self.invoice_number!r}, "
            f"total_amount={self.total_amount!r})>"
        )


class QBInvoiceLineItem(Base):
    """QuickBooks Invoice Line Item model.

    Stores individual line items from QuickBooks invoices, with optional
    links to local products for tracking Une Femme product sales.

    Attributes:
        id: Unique identifier (UUID)
        invoice_id: Foreign key to qb_invoices
        line_number: Line number within the invoice
        description: Line item description
        quantity: Quantity sold
        unit_price: Unit price
        amount: Total line amount (quantity * unit_price)
        qb_item_id: QuickBooks item ID
        qb_item_name: QuickBooks item name (may match SKU)
        sku_id: Optional foreign key to products (for Une Femme products)
        created_at: When this record was created
    """

    __tablename__ = "qb_invoice_line_items"
    __table_args__ = (
        Index(
            "idx_qb_line_items_invoice",
            "invoice_id",
        ),
        Index(
            "idx_qb_line_items_sku",
            "sku_id",
        ),
        Index(
            "idx_qb_line_items_qb_item",
            "qb_item_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("qb_invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    quantity: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
    )
    amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=True,
    )
    qb_item_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    qb_item_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    sku_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    invoice = relationship("QBInvoice", backref="line_items_rel")
    product: Mapped["Product | None"] = relationship("Product", backref="qb_line_items")

    def __repr__(self) -> str:
        return (
            f"<QBInvoiceLineItem(invoice_id={self.invoice_id!r}, "
            f"qb_item_name={self.qb_item_name!r}, "
            f"quantity={self.quantity!r})>"
        )
