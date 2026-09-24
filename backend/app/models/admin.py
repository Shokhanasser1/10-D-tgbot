from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Integer, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AdminRole


class Admin(Base):
    """A person allowed into the admin panel. Deactivated, never deleted."""

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # No FK to telegram_users, as with couriers: admins are added before their first login.
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    role: Mapped[AdminRole] = mapped_column(
        Enum(AdminRole, native_enum=False, length=20), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # telegram_id of the owner who added them; null for admins created from the bootstrap list.
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
