from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import NotificationStatus


class Notification(Base):
    """A Telegram message waiting to be sent, or the record of one (the outbox, Spec 5).

    Rows are inserted in the same transaction as the change they report and sent later by the
    background sender, so a rolled-back change never notifies and a crash never loses a message.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notifications_pending_next_attempt_at",
            "next_attempt_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    # The same event reported twice (a replayed webhook) inserts nothing the second time.
    dedupe_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # none_as_null: a message without buttons stores SQL NULL, not the JSON value null.
    reply_markup: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, native_enum=False, length=20),
        nullable=False,
        default=NotificationStatus.pending,
        server_default=NotificationStatus.pending.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # When the sender may pick the row up next; also serves as the lease while it is being sent.
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Telegram's own description of a failure; never the request URL, which holds the bot token.
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
