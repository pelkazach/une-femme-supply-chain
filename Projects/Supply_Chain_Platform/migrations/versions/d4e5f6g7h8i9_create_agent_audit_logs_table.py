"""Create agent_audit_logs table.

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-02-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"
down_revision: str | None = "c3d4e5f6g7h8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create agent_audit_logs table for normalized audit trail storage."""
    op.create_table(
        "agent_audit_logs",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        # Workflow correlation
        sa.Column("workflow_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("thread_id", sa.String(255), nullable=True),
        # Decision metadata
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        # Decision content
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column("inputs", postgresql.JSON, nullable=True),
        sa.Column("outputs", postgresql.JSON, nullable=True),
        # Confidence score
        sa.Column("confidence", sa.Float, nullable=True),
        # Product context
        sa.Column("sku_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("sku", sa.String(50), nullable=True),
        # Record creation timestamp
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create indexes
    op.create_index(
        "ix_agent_audit_logs_workflow_id",
        "agent_audit_logs",
        ["workflow_id"],
    )
    op.create_index(
        "ix_agent_audit_logs_thread_id",
        "agent_audit_logs",
        ["thread_id"],
    )
    op.create_index(
        "ix_agent_audit_logs_timestamp",
        "agent_audit_logs",
        ["timestamp"],
    )
    op.create_index(
        "ix_agent_audit_logs_agent",
        "agent_audit_logs",
        ["agent"],
    )
    op.create_index(
        "ix_agent_audit_logs_action",
        "agent_audit_logs",
        ["action"],
    )
    op.create_index(
        "ix_agent_audit_logs_confidence",
        "agent_audit_logs",
        ["confidence"],
    )
    op.create_index(
        "ix_agent_audit_logs_sku_id",
        "agent_audit_logs",
        ["sku_id"],
    )
    # Composite index for workflow audit queries
    op.create_index(
        "ix_agent_audit_logs_workflow_timestamp",
        "agent_audit_logs",
        ["workflow_id", "timestamp"],
    )
    # Composite index for agent analysis queries
    op.create_index(
        "ix_agent_audit_logs_agent_action",
        "agent_audit_logs",
        ["agent", "action"],
    )
    # Composite index for SKU audit queries
    op.create_index(
        "ix_agent_audit_logs_sku_timestamp",
        "agent_audit_logs",
        ["sku_id", "timestamp"],
    )
    # Partial index for low-confidence decisions (for review)
    op.create_index(
        "ix_agent_audit_logs_low_confidence",
        "agent_audit_logs",
        ["confidence", "timestamp"],
        postgresql_where=sa.text("confidence < 0.85"),
    )


def downgrade() -> None:
    """Drop agent_audit_logs table."""
    op.drop_index("ix_agent_audit_logs_low_confidence", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_sku_timestamp", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_agent_action", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_workflow_timestamp", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_sku_id", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_confidence", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_action", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_agent", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_timestamp", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_thread_id", table_name="agent_audit_logs")
    op.drop_index("ix_agent_audit_logs_workflow_id", table_name="agent_audit_logs")
    op.drop_table("agent_audit_logs")
