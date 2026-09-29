from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PaymentMethod, PaymentStatus, RefundStatus
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False, length=20),
        nullable=False,
        default=PaymentMethod.stripe,
        server_default=PaymentMethod.stripe.value,
    )
    # Stripe payments only.
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    # Telegram Payments only: what the owner needs to find the payment in the provider's cabinet.
    telegram_payment_charge_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_payment_charge_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, length=32),
        nullable=False,
        default=PaymentStatus.requires_payment_method,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    # Null until the order is cancelled after payment; refunds are always for the full amount.
    refund_status: Mapped[RefundStatus | None] = mapped_column(
        Enum(RefundStatus, native_enum=False, length=20), nullable=True
    )
    stripe_refund_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="payment")
