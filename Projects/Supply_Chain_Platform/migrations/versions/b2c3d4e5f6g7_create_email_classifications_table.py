"""create_email_classifications_table

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-03 23:00:00.000000

Creates the email_classifications table for storing email classification results
from the Celery processing queue. Stores classification decisions, confidence
scores, and human review status.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create email_classifications table for storing classification results."""
    op.create_table(
        "email_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", sa.String(255), nullable=False, unique=True),
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(1000), nullable=False, server_default=""),
        sa.Column("sender", sa.String(500), nullable=False),
        sa.Column("recipient", sa.String(500), nullable=False, server_default=""),
        sa.Column(
            "received_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("reasoning", sa.Text, nullable=False, server_default=""),
        sa.Column("needs_review", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("reviewed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column(
            "reviewed_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column("corrected_category", sa.String(50), nullable=True),
        sa.Column("has_attachments", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("attachment_names", sa.Text, nullable=False, server_default="[]"),
        sa.Column("processing_time_ms", sa.Integer, nullable=True),
        sa.Column("ollama_used", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # Create indexes for common query patterns
    op.create_index(
        "idx_email_classifications_message_id",
        "email_classifications",
        ["message_id"],
        unique=True,
    )
    op.create_index(
        "idx_email_classifications_category",
        "email_classifications",
        ["category"],
    )
    op.create_index(
        "idx_email_classifications_needs_review",
        "email_classifications",
        ["needs_review"],
    )
    op.create_index(
        "idx_email_classifications_received_at",
        "email_classifications",
        ["received_at"],
    )
    # Partial index for pending review queue
    op.create_index(
        "idx_email_classifications_pending_review",
        "email_classifications",
        ["needs_review", "reviewed"],
        postgresql_where=sa.text("needs_review = true AND reviewed = false"),
    )


def downgrade() -> None:
    """Drop email_classifications table and indexes."""
    op.drop_index(
        "idx_email_classifications_pending_review",
        table_name="email_classifications",
    )
    op.drop_index(
        "idx_email_classifications_received_at",
        table_name="email_classifications",
    )
    op.drop_index(
        "idx_email_classifications_needs_review",
        table_name="email_classifications",
    )
    op.drop_index(
        "idx_email_classifications_category",
        table_name="email_classifications",
    )
    op.drop_index(
        "idx_email_classifications_message_id",
        table_name="email_classifications",
    )
    op.drop_table("email_classifications")
