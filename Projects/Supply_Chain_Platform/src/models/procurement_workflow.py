"""SQLAlchemy model for procurement workflow state persistence."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class ProcurementWorkflow(Base):
    """Model for storing procurement workflow state.

    This table persists the state of procurement workflows to enable:
    - Workflow interrupt/resume for human-in-the-loop approvals
    - Audit trail of all workflow executions
    - Dashboard visibility into pending and completed orders

    Attributes:
        id: Unique workflow UUID
        thread_id: LangGraph thread ID for checkpointing
        sku_id: Product SKU UUID being procured
        sku: Product SKU code (e.g., "UFBub250")
        current_inventory: Inventory level when workflow started
        order_value: Calculated order value (quantity × unit_price)
        recommended_quantity: Recommended order quantity
        safety_stock: Calculated safety stock level
        reorder_point: Inventory level that triggers reorder
        forecast_confidence: Confidence score from demand forecaster
        selected_vendor: JSON blob with vendor details
        approval_status: Current approval status (pending, approved, rejected, auto_approved)
        approval_required_level: Required approval level (auto, manager, executive)
        reviewer_id: ID/email of the human reviewer (if reviewed)
        human_feedback: Feedback from human reviewer (if any)
        workflow_status: Current workflow status
        error_message: Error message if workflow failed
        audit_log: JSON array of audit log entries
        created_at: Workflow creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "procurement_workflows"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # LangGraph thread ID for checkpointing
    thread_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    # Product being procured
    sku_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(50), nullable=False)

    # Inventory and forecast data
    current_inventory: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    forecast_confidence: Mapped[float] = mapped_column(Float, nullable=True)

    # Optimization outputs
    safety_stock: Mapped[int] = mapped_column(Integer, nullable=True)
    reorder_point: Mapped[int] = mapped_column(Integer, nullable=True)
    recommended_quantity: Mapped[int] = mapped_column(Integer, nullable=True)

    # Vendor and order data
    selected_vendor: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    order_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Approval state
    approval_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    approval_required_level: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    reviewer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    human_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Workflow state
    workflow_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="initialized",
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit trail (JSON array of AuditLogEntry-like dicts)
    audit_log: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Indexes for common queries
    __table_args__ = (
        # Composite index for approval queue queries
        Index(
            "ix_procurement_workflows_approval_queue",
            "approval_status",
            "workflow_status",
            "created_at",
        ),
        # Index for finding workflows by SKU
        Index(
            "ix_procurement_workflows_sku_status",
            "sku_id",
            "workflow_status",
        ),
        # Partial index for pending approvals (most common query)
        Index(
            "ix_procurement_workflows_pending",
            "created_at",
            postgresql_where=approval_status == "pending",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<ProcurementWorkflow(id={self.id}, sku={self.sku}, "
            f"status={self.workflow_status}, approval={self.approval_status})>"
        )
