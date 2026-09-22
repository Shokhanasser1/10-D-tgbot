from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ShipmentStatus
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order


class Shipment(TimestampMixin, Base):
    """Minimal placeholder — the integration seam for the future logistics/GPS spec (Spec 2)."""

    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[ShipmentStatus] = mapped_column(
        Enum(ShipmentStatus, native_enum=False, length=20),
        nullable=False,
        default=ShipmentStatus.processing,
    )
    courier_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tracking_status: Mapped[str | None] = mapped_column(String(255), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="shipment")
