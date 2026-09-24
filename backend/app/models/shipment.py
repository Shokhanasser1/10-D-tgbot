from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ShipmentStatus
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.courier import Courier
    from app.models.order import Order


class Shipment(TimestampMixin, Base):
    """Delivery of one order by the business's own couriers.

    Created `processing` (in the courier pool) when payment is confirmed; the dispatch service
    moves it through assigned -> shipped -> delivered and keeps Order.status in step.
    """

    __tablename__ = "shipments"
    __table_args__ = (
        Index("ix_shipments_status", "status"),
        Index("ix_shipments_courier_id_status", "courier_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[ShipmentStatus] = mapped_column(
        Enum(ShipmentStatus, native_enum=False, length=20),
        nullable=False,
        default=ShipmentStatus.processing,
    )
    courier_id: Mapped[int | None] = mapped_column(
        ForeignKey("couriers.id", ondelete="RESTRICT"), nullable=True
    )
    tracking_status: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="shipment")
    courier: Mapped["Courier | None"] = relationship("Courier")
