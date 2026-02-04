"""Product model for SKU management."""

import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Product(Base):
    """Product model representing a wine SKU.

    Attributes:
        id: Unique identifier (UUID)
        sku: Stock keeping unit code (e.g., UFBub250)
        name: Human-readable product name
        category: Product category (e.g., 'sparkling', 'rose')
        created_at: Timestamp when the record was created
    """

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    sku: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Product(sku={self.sku!r}, name={self.name!r})>"
