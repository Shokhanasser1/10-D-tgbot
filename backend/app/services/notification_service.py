"""Putting Telegram messages into the outbox (Spec 5). No network, no commit.

Callers enqueue inside the transaction of the change being reported, so the message exists
exactly when the change does. The background sender (notification_sender) delivers it later.
"""

from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.notification import Notification


def web_app_button(text: str, path: str) -> dict[str, Any] | None:
    """An inline keyboard opening the Mini App at `path`, or None without an https WEBAPP_URL."""
    base = get_settings().webapp_url.strip()
    if not base.startswith("https://"):
        return None  # Telegram only opens Mini Apps from https:// addresses
    url = base.rstrip("/") + "/" + path.lstrip("/")
    return {"inline_keyboard": [[{"text": text, "web_app": {"url": url}}]]}


async def enqueue(
    db: AsyncSession,
    *,
    chat_id: int,
    kind: str,
    dedupe_key: str,
    text: str,
    reply_markup: dict[str, Any] | None = None,
) -> None:
    await db.execute(
        pg_insert(Notification)
        .values(
            chat_id=chat_id,
            kind=kind,
            dedupe_key=dedupe_key[:120],
            text=text,
            reply_markup=reply_markup,
        )
        .on_conflict_do_nothing(index_elements=[Notification.dedupe_key])
    )
