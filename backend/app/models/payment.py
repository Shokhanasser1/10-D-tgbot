from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PaymentStatus, RefundStatus
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, length=32),
        nullable=False,
        default=PaymentStatus.requires_payment_method,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    # Null until an admin cancels the order; refunds are always for the full amount.
    refund_status: Mapped[RefundStatus | None] = mapped_column(
        Enum(RefundStatus, native_enum=False, length=20), nullable=True
    )
    stripe_refund_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="payment")
