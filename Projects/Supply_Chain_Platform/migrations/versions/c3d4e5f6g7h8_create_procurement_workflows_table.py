"""Create procurement_workflows table.

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-02-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h8"
down_revision: str | None = "b2c3d4e5f6g7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create procurement_workflows table for workflow state persistence."""
    op.create_table(
        "procurement_workflows",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        # LangGraph thread ID
        sa.Column("thread_id", sa.String(255), unique=True, nullable=False),
        # Product being procured
        sa.Column("sku_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("sku", sa.String(50), nullable=False),
        # Inventory and forecast data
        sa.Column("current_inventory", sa.Integer, nullable=False, default=0),
        sa.Column("forecast_confidence", sa.Float, nullable=True),
        # Optimization outputs
        sa.Column("safety_stock", sa.Integer, nullable=True),
        sa.Column("reorder_point", sa.Integer, nullable=True),
        sa.Column("recommended_quantity", sa.Integer, nullable=True),
        # Vendor and order data
        sa.Column("selected_vendor", postgresql.JSON, nullable=True),
        sa.Column("order_value", sa.Float, nullable=True),
        # Approval state
        sa.Column(
            "approval_status",
            sa.String(50),
            nullable=False,
            default="pending",
        ),
        sa.Column("approval_required_level", sa.String(50), nullable=True),
        sa.Column("reviewer_id", sa.String(255), nullable=True),
        sa.Column("human_feedback", sa.Text, nullable=True),
        # Workflow state
        sa.Column(
            "workflow_status",
            sa.String(50),
            nullable=False,
            default="initialized",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        # Audit trail
        sa.Column("audit_log", postgresql.JSON, nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create indexes
    op.create_index(
        "ix_procurement_workflows_thread_id",
        "procurement_workflows",
        ["thread_id"],
    )
    op.create_index(
        "ix_procurement_workflows_sku_id",
        "procurement_workflows",
        ["sku_id"],
    )
    op.create_index(
        "ix_procurement_workflows_approval_status",
        "procurement_workflows",
        ["approval_status"],
    )
    op.create_index(
        "ix_procurement_workflows_workflow_status",
        "procurement_workflows",
        ["workflow_status"],
    )
    # Composite index for approval queue queries
    op.create_index(
        "ix_procurement_workflows_approval_queue",
        "procurement_workflows",
        ["approval_status", "workflow_status", "created_at"],
    )
    # Index for finding workflows by SKU
    op.create_index(
        "ix_procurement_workflows_sku_status",
        "procurement_workflows",
        ["sku_id", "workflow_status"],
    )
    # Partial index for pending approvals (most common query)
    op.create_index(
        "ix_procurement_workflows_pending",
        "procurement_workflows",
        ["created_at"],
        postgresql_where=sa.text("approval_status = 'pending'"),
    )


def downgrade() -> None:
    """Drop procurement_workflows table."""
    op.drop_index("ix_procurement_workflows_pending", table_name="procurement_workflows")
    op.drop_index("ix_procurement_workflows_sku_status", table_name="procurement_workflows")
    op.drop_index("ix_procurement_workflows_approval_queue", table_name="procurement_workflows")
    op.drop_index("ix_procurement_workflows_workflow_status", table_name="procurement_workflows")
    op.drop_index("ix_procurement_workflows_approval_status", table_name="procurement_workflows")
    op.drop_index("ix_procurement_workflows_sku_id", table_name="procurement_workflows")
    op.drop_index("ix_procurement_workflows_thread_id", table_name="procurement_workflows")
    op.drop_table("procurement_workflows")
