"""Distributor model for distribution partner management."""

import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Distributor(Base):
    """Distributor model representing a distribution partner.

    Attributes:
        id: Unique identifier (UUID)
        name: Human-readable distributor name
        segment: Distributor segment (e.g., 'RNDC', 'Reyes', 'Non-RNDC')
        state: Two-letter state code where distributor operates
        created_at: Timestamp when the record was created
    """

    __tablename__ = "distributors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    segment: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    state: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Distributor(name={self.name!r}, segment={self.segment!r})>"
