"""Create qb_invoices and qb_invoice_line_items tables.

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-02-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e5f6g7h8i9j0"
down_revision: str | None = "d4e5f6g7h8i9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create qb_invoices and qb_invoice_line_items tables."""
    # Create qb_invoices table
    op.create_table(
        "qb_invoices",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # QuickBooks identifiers
        sa.Column("qb_invoice_id", sa.String(100), nullable=False, unique=True),
        sa.Column("invoice_number", sa.String(100), nullable=True),
        # Customer info
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("customer_id", sa.String(100), nullable=True),
        # Dates
        sa.Column("invoice_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        # Amounts
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("balance_due", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency_code", sa.String(10), nullable=False, server_default="USD"),
        # Status
        sa.Column("status", sa.String(50), nullable=False, server_default="Open"),
        # Line items stored as JSON for flexibility
        sa.Column("line_items", postgresql.JSON, nullable=True),
        # QuickBooks timestamps
        sa.Column("qb_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qb_updated_at", sa.DateTime(timezone=True), nullable=True),
        # Sync tracking
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        # Local timestamp
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create indexes for qb_invoices
    op.create_index(
        "idx_qb_invoices_qb_id",
        "qb_invoices",
        ["qb_invoice_id"],
        unique=True,
    )
    op.create_index(
        "idx_qb_invoices_customer",
        "qb_invoices",
        ["customer_id"],
    )
    op.create_index(
        "idx_qb_invoices_date",
        "qb_invoices",
        ["invoice_date"],
    )
    op.create_index(
        "idx_qb_invoices_due_date",
        "qb_invoices",
        ["due_date"],
    )
    op.create_index(
        "idx_qb_invoices_status",
        "qb_invoices",
        ["status"],
    )
    op.create_index(
        "idx_qb_invoices_synced",
        "qb_invoices",
        ["synced_at"],
    )

    # Create qb_invoice_line_items table
    op.create_table(
        "qb_invoice_line_items",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Foreign key to invoice
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("qb_invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Line item details
        sa.Column("line_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("quantity", sa.Float, nullable=True),
        sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=True),
        # QuickBooks item reference
        sa.Column("qb_item_id", sa.String(100), nullable=True),
        sa.Column("qb_item_name", sa.String(255), nullable=True),
        # Optional link to local product
        sa.Column(
            "sku_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Local timestamp
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create indexes for qb_invoice_line_items
    op.create_index(
        "idx_qb_line_items_invoice",
        "qb_invoice_line_items",
        ["invoice_id"],
    )
    op.create_index(
        "idx_qb_line_items_sku",
        "qb_invoice_line_items",
        ["sku_id"],
    )
    op.create_index(
        "idx_qb_line_items_qb_item",
        "qb_invoice_line_items",
        ["qb_item_id"],
    )


def downgrade() -> None:
    """Drop qb_invoices and qb_invoice_line_items tables."""
    # Drop line items table first (has FK to invoices)
    op.drop_index("idx_qb_line_items_qb_item", table_name="qb_invoice_line_items")
    op.drop_index("idx_qb_line_items_sku", table_name="qb_invoice_line_items")
    op.drop_index("idx_qb_line_items_invoice", table_name="qb_invoice_line_items")
    op.drop_table("qb_invoice_line_items")

    # Drop invoices table
    op.drop_index("idx_qb_invoices_synced", table_name="qb_invoices")
    op.drop_index("idx_qb_invoices_status", table_name="qb_invoices")
    op.drop_index("idx_qb_invoices_due_date", table_name="qb_invoices")
    op.drop_index("idx_qb_invoices_date", table_name="qb_invoices")
    op.drop_index("idx_qb_invoices_customer", table_name="qb_invoices")
    op.drop_index("idx_qb_invoices_qb_id", table_name="qb_invoices")
    op.drop_table("qb_invoices")
