"""SQLAlchemy model for agent audit log persistence.

This module provides a normalized table for storing agent decisions
with full searchability and filtering capabilities.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class AgentAuditLog(Base):
    """Model for storing agent audit trail entries.

    This table provides a normalized, searchable storage for all agent
    decisions in the procurement workflow. Each entry records:
    - Which agent made the decision
    - What action was taken
    - The reasoning behind the decision
    - Input/output data for reproducibility
    - Confidence score (when applicable)

    The table supports efficient querying by:
    - Workflow ID (to see all decisions for a workflow)
    - Agent name (to analyze specific agent behavior)
    - Action type (to find specific decision types)
    - Time range (to audit decisions over time)
    - Confidence threshold (to find low-confidence decisions)

    Attributes:
        id: Unique audit entry UUID
        workflow_id: Foreign key to procurement_workflows (optional for standalone logging)
        thread_id: LangGraph thread ID for correlation
        timestamp: When the decision was made
        agent: Which agent made the decision (e.g., "demand_forecaster")
        action: What action was taken (e.g., "generate_forecast")
        reasoning: Human-readable explanation of the decision
        inputs: JSON blob of input data for the decision
        outputs: JSON blob of output data from the decision
        confidence: Confidence score (0.0-1.0) if applicable
        sku_id: Product SKU UUID (for quick filtering by product)
        sku: Product SKU code (for quick display)
        created_at: When the record was created (for indexing)
    """

    __tablename__ = "agent_audit_logs"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Workflow correlation
    workflow_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
        index=True,
    )
    thread_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Decision metadata
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    agent: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    # Decision content
    reasoning: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    inputs: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    outputs: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Confidence score (optional)
    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        index=True,
    )

    # Product context (for easy filtering)
    sku_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
        index=True,
    )
    sku: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Record creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Indexes for common query patterns
    __table_args__ = (
        # Composite index for workflow audit queries
        Index(
            "ix_agent_audit_logs_workflow_timestamp",
            "workflow_id",
            "timestamp",
        ),
        # Composite index for agent analysis queries
        Index(
            "ix_agent_audit_logs_agent_action",
            "agent",
            "action",
        ),
        # Composite index for SKU audit queries
        Index(
            "ix_agent_audit_logs_sku_timestamp",
            "sku_id",
            "timestamp",
        ),
        # Partial index for low-confidence decisions (for review)
        Index(
            "ix_agent_audit_logs_low_confidence",
            "confidence",
            "timestamp",
            postgresql_where=(confidence < 0.85),
        ),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<AgentAuditLog(id={self.id}, agent={self.agent}, "
            f"action={self.action}, confidence={self.confidence})>"
        )

    @classmethod
    def from_dict(
        cls,
        entry: dict,
        workflow_id: str | None = None,
        thread_id: str | None = None,
        sku_id: str | None = None,
        sku: str | None = None,
    ) -> "AgentAuditLog":
        """Create an AgentAuditLog from a dictionary audit entry.

        This is a convenience method for converting the dict-based audit
        entries from the workflow state into normalized database records.

        Args:
            entry: Dictionary with audit entry data
            workflow_id: Optional workflow UUID
            thread_id: Optional LangGraph thread ID
            sku_id: Optional SKU UUID
            sku: Optional SKU code

        Returns:
            AgentAuditLog instance ready for insertion
        """
        # Parse timestamp from ISO format string
        timestamp_str = entry.get("timestamp", "")
        if timestamp_str:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        else:
            timestamp = datetime.now(UTC)

        return cls(
            workflow_id=workflow_id,
            thread_id=thread_id,
            timestamp=timestamp,
            agent=entry.get("agent", "unknown"),
            action=entry.get("action", "unknown"),
            reasoning=entry.get("reasoning", ""),
            inputs=entry.get("inputs"),
            outputs=entry.get("outputs"),
            confidence=entry.get("confidence"),
            sku_id=sku_id or entry.get("inputs", {}).get("sku_id"),
            sku=sku or entry.get("inputs", {}).get("sku"),
        )
