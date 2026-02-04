"""seed_product_skus

Revision ID: 52fa8d4129df
Revises: 69b388f315fc
Create Date: 2026-02-03 20:16:56.866857

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "52fa8d4129df"
down_revision: str | Sequence[str] | None = "69b388f315fc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The 4 core Une Femme product SKUs
PRODUCT_SKUS = [
    {
        "sku": "UFBub250",
        "name": "Une Femme Bubbles 250ml",
        "category": "sparkling",
    },
    {
        "sku": "UFRos250",
        "name": "Une Femme Rosé 250ml",
        "category": "rose",
    },
    {
        "sku": "UFRed250",
        "name": "Une Femme Red 250ml",
        "category": "red",
    },
    {
        "sku": "UFCha250",
        "name": "Une Femme Chardonnay 250ml",
        "category": "white",
    },
]


def upgrade() -> None:
    """Seed the 4 core product SKUs into the products table."""
    connection = op.get_bind()

    for product in PRODUCT_SKUS:
        # Use INSERT ... ON CONFLICT to make migration idempotent
        connection.execute(
            text("""
                INSERT INTO products (id, sku, name, category)
                VALUES (gen_random_uuid(), :sku, :name, :category)
                ON CONFLICT (sku) DO NOTHING
            """),
            product,
        )


def downgrade() -> None:
    """Remove the seeded product SKUs."""
    connection = op.get_bind()

    skus = [p["sku"] for p in PRODUCT_SKUS]
    connection.execute(
        text("DELETE FROM products WHERE sku = ANY(:skus)"),
        {"skus": skus},
    )
