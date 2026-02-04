"""InventoryEvent model for time-series inventory tracking."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class InventoryEvent(Base):
    """InventoryEvent model for tracking inventory changes over time.

    This is the core time-series table that tracks all inventory movements
    including shipments, depletions, and adjustments.

    Attributes:
        id: Unique identifier (UUID)
        time: Timestamp of the inventory event
        sku_id: Foreign key to the product
        warehouse_id: Foreign key to the warehouse
        distributor_id: Foreign key to the distributor (optional)
        event_type: Type of event ('shipment', 'depletion', 'adjustment')
        quantity: Number of units (positive for additions, can track depletions)
        created_at: Timestamp when the record was created
    """

    __tablename__ = "inventory_events"
    __table_args__ = (
        Index(
            "idx_inventory_events_time_brin",
            "time",
            postgresql_using="brin",
        ),
        Index(
            "idx_inventory_events_sku_time",
            "sku_id",
            "time",
        ),
        Index(
            "idx_inventory_events_warehouse_time",
            "warehouse_id",
            "time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        index=False,  # Using BRIN index instead
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
    )
    distributor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("distributors.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    product = relationship("Product", backref="inventory_events")
    warehouse = relationship("Warehouse", backref="inventory_events")
    distributor = relationship("Distributor", backref="inventory_events")

    def __repr__(self) -> str:
        return (
            f"<InventoryEvent(time={self.time!r}, "
            f"event_type={self.event_type!r}, "
            f"quantity={self.quantity!r})>"
        )
