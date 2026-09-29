from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import OrderStatus, PaymentMethod

if TYPE_CHECKING:
    from app.models.payment import Payment
    from app.models.shipment import Shipment
    from app.models.variant import Variant


class Order(Base):
    __tablename__ = "orders"
    # The expiry sweeper looks only at unpaid orders past their hold.
    __table_args__ = (
        Index(
            "ix_orders_pending_reserved_until",
            "reserved_until",
            postgresql_where=text("status = 'pending_payment'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("telegram_users.telegram_id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=20),
        nullable=False,
        default=OrderStatus.pending_payment,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False, length=20),
        nullable=False,
        default=PaymentMethod.stripe,
        server_default=PaymentMethod.stripe.value,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    delivery_address: Mapped[dict[str, str | float | None]] = mapped_column(JSONB, nullable=False)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Set when payment pushed a variant's stock below zero: paid for, but not all on the shelf.
    stock_shortfall: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Until when checkout holds the stock of an unpaid order. NULL: placed before reservations
    # existed, so its stock is taken at payment instead (the legacy path in mark_order_paid).
    reserved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Admin telegram_id; null when cancelled through the internal token (scripts).
    cancelled_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    payment: Mapped["Payment | None"] = relationship(
        "Payment", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )
    shipment: Mapped["Shipment | None"] = relationship(
        "Shipment", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.id", ondelete="RESTRICT"), nullable=False
    )
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    variant: Mapped["Variant"] = relationship("Variant")
