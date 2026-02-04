"""create_forecasts_table

Revision ID: a1b2c3d4e5f6
Revises: e00126dfbb34
Create Date: 2026-02-03 22:00:00.000000

Creates the forecasts table for storing Prophet forecast results.
Forecasts are generated weekly and store 26-week forward projections
with confidence intervals.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "e00126dfbb34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create forecasts table for storing Prophet forecast results."""
    op.create_table(
        "forecasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sku_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "forecast_date",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column("yhat", sa.Float, nullable=False),
        sa.Column("yhat_lower", sa.Float, nullable=False),
        sa.Column("yhat_upper", sa.Float, nullable=False),
        sa.Column("interval_width", sa.Float, nullable=False, server_default="0.80"),
        sa.Column(
            "model_trained_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "training_data_start",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "training_data_end",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column("training_data_points", sa.Integer, nullable=False),
        sa.Column("mape", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # Create indexes for common query patterns
    op.create_index(
        "idx_forecasts_sku_date",
        "forecasts",
        ["sku_id", "forecast_date"],
    )
    op.create_index(
        "idx_forecasts_model_trained",
        "forecasts",
        ["model_trained_at"],
    )


def downgrade() -> None:
    """Drop forecasts table and indexes."""
    op.drop_index("idx_forecasts_model_trained", table_name="forecasts")
    op.drop_index("idx_forecasts_sku_date", table_name="forecasts")
    op.drop_table("forecasts")
