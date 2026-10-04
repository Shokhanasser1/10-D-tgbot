from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Seller(TimestampMixin, Base):
    """A shop selling on the platform (Spec 9). Added by the owner; deactivated, never deleted."""

    __tablename__ = "sellers"
    __table_args__ = (
        CheckConstraint("commission_percent BETWEEN 0 AND 100", name="commission_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Where couriers collect this seller's orders. The API requires it; only the "Main shop"
    # the migration creates for products that existed before sellers may have none.
    pickup_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    # The platform's share of the goods (Spec 11); copied onto each order at checkout.
    commission_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("10"), server_default="10"
    )
