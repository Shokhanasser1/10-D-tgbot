from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    false,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AdminRole


class Admin(Base):
    """A person allowed into the admin panel. Deactivated, never deleted."""

    __tablename__ = "admins"
    __table_args__ = (
        # A seller account works for exactly one seller; staff accounts for none (Spec 9 §3).
        CheckConstraint("(role = 'seller') = (seller_id IS NOT NULL)", name="seller_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # No FK to telegram_users, as with couriers: admins are added before their first login.
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    role: Mapped[AdminRole] = mapped_column(
        Enum(AdminRole, native_enum=False, length=20), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    seller_id: Mapped[int | None] = mapped_column(
        ForeignKey("sellers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # telegram_id of the owner who added them; null for admins created from the bootstrap list.
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Password sign-in (Spec 7). Null until the admin sets one in their profile.
    login: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Set by an owner's reset: the temporary password must be replaced before anything else.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Part of every session cookie; bumping it signs out all of this admin's sessions.
    session_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    failed_logins: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None
