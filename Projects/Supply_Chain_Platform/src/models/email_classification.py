"""EmailClassification model for storing email classification results."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class EmailClassification(Base):
    """Model for storing email classification results.

    Stores classification results from the email processing pipeline,
    including confidence scores and human review status.

    Attributes:
        id: Unique identifier (UUID)
        message_id: Gmail message ID (unique)
        thread_id: Gmail thread ID
        subject: Email subject line
        sender: Sender email address
        recipient: Recipient email address
        received_at: When the email was received
        category: Classification category (PO, BOL, INVOICE, GENERAL)
        confidence: Classification confidence score (0.0-1.0)
        reasoning: LLM's reasoning for the classification
        needs_review: Whether human review is required (confidence < 0.85)
        reviewed: Whether a human has reviewed this classification
        reviewed_by: Who reviewed the classification (if applicable)
        reviewed_at: When the classification was reviewed
        corrected_category: The corrected category if changed during review
        has_attachments: Whether the email has attachments
        attachment_names: JSON list of attachment filenames
        processing_time_ms: Time taken to classify in milliseconds
        ollama_used: Whether Ollama was used (vs rule-based fallback)
        created_at: When the record was created
        updated_at: When the record was last updated
    """

    __tablename__ = "email_classifications"
    __table_args__ = (
        Index("idx_email_classifications_message_id", "message_id", unique=True),
        Index("idx_email_classifications_category", "category"),
        Index("idx_email_classifications_needs_review", "needs_review"),
        Index("idx_email_classifications_received_at", "received_at"),
        Index(
            "idx_email_classifications_pending_review",
            "needs_review",
            "reviewed",
            postgresql_where="needs_review = true AND reviewed = false",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    message_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )
    thread_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        default="",
    )
    sender: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    recipient: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="",
    )
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    reasoning: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    reviewed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    corrected_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    has_attachments: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    attachment_names: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )
    processing_time_ms: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    ollama_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<EmailClassification(message_id={self.message_id!r}, "
            f"category={self.category!r}, "
            f"confidence={self.confidence!r})>"
        )
