"""Warehouse model for storage location management."""

import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Warehouse(Base):
    """Warehouse model representing a storage location.

    Attributes:
        id: Unique identifier (UUID)
        name: Human-readable warehouse name
        code: Short code for the warehouse (e.g., 'WH01')
        created_at: Timestamp when the record was created
    """

    __tablename__ = "warehouses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Warehouse(code={self.code!r}, name={self.name!r})>"
