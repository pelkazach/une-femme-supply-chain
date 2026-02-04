"""create_inventory_events_table

Revision ID: 69b388f315fc
Revises:
Create Date: 2026-02-03 20:14:12.276921

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "69b388f315fc"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create inventory_events table with BRIN index for time-series queries."""
    # Create the products table first (if not exists)
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku", sa.String(20), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)

    # Create the warehouses table
    op.create_table(
        "warehouses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(10), unique=True, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_warehouses_code", "warehouses", ["code"], unique=True)

    # Create the distributors table
    op.create_table(
        "distributors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("segment", sa.String(50), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # Create the inventory_events table
    op.create_table(
        "inventory_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("time", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "sku_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "distributor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("distributors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # Create BRIN index on time column for efficient time-range queries
    # BRIN indexes are ideal for time-series data where values are naturally ordered
    op.create_index(
        "idx_inventory_events_time_brin",
        "inventory_events",
        ["time"],
        postgresql_using="brin",
    )

    # Create composite indexes for common query patterns
    op.create_index(
        "idx_inventory_events_sku_time",
        "inventory_events",
        ["sku_id", "time"],
    )
    op.create_index(
        "idx_inventory_events_warehouse_time",
        "inventory_events",
        ["warehouse_id", "time"],
    )


def downgrade() -> None:
    """Drop all tables in reverse order."""
    # Drop indexes first
    op.drop_index("idx_inventory_events_warehouse_time", table_name="inventory_events")
    op.drop_index("idx_inventory_events_sku_time", table_name="inventory_events")
    op.drop_index("idx_inventory_events_time_brin", table_name="inventory_events")

    # Drop tables in reverse order of creation (due to foreign keys)
    op.drop_table("inventory_events")
    op.drop_table("distributors")
    op.drop_index("ix_warehouses_code", table_name="warehouses")
    op.drop_table("warehouses")
    op.drop_index("ix_products_sku", table_name="products")
    op.drop_table("products")
