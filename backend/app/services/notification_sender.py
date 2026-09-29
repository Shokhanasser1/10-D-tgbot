"""Delivering queued Telegram messages (Spec 5 §6).

Each tick leases a batch of due rows (pushing their next_attempt_at a minute ahead and
committing), sends them one by one outside any transaction, and records each outcome. Two API
processes never lease the same row; a process that dies mid-send leaves the lease to expire, so
the message goes out again rather than never.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationStatus
from app.models.notification import Notification

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
BATCH = 25
LEASE = timedelta(seconds=60)
SEND_GAP_SECONDS = 0.04  # Telegram allows about 30 messages per second per bot
MAX_ATTEMPTS = 8
RETENTION = timedelta(days=30)
CLEANUP_EVERY_SECONDS = 24 * 3600


@dataclass(frozen=True)
class Outcome:
    """What to do with a message after one attempt."""

    kind: str  # sent | undeliverable | failed | retry | rate_limited
    error: str | None = None
    retry_after: int | None = None


def classify(status_code: int, body: dict[str, Any]) -> Outcome:
    """Turn Telegram's answer into an outcome. `body` is its JSON (`ok`, `description`, ...)."""
    description = str(body.get("description") or f"HTTP {status_code}")[:500]
    if status_code == 200 and body.get("ok"):
        return Outcome("sent")
    if status_code == 429:
        retry_after = (body.get("parameters") or {}).get("retry_after")
        return Outcome("rate_limited", description, int(retry_after or 5))
    if status_code == 403 or (status_code == 400 and "chat not found" in description.lower()):
        return Outcome("undeliverable", description)
    if 400 <= status_code < 500:
        return Outcome("failed", description)  # the message itself is wrong; retrying won't help
    return Outcome("retry", description)


def backoff(attempts: int) -> timedelta:
    """5 s, 15 s, 45 s, ... after the 1st, 2nd, 3rd failed attempt."""
    return timedelta(seconds=5 * 3 ** max(attempts - 1, 0))


class TelegramClient:
    """sendMessage over HTTP. Errors never carry the URL, which contains the bot token."""

    def __init__(self, token: str, http: httpx.AsyncClient) -> None:
        self._url = f"{TELEGRAM_API}/bot{token}/sendMessage"
        self._http = http

    async def send(self, chat_id: int, text: str, reply_markup: dict | None) -> Outcome:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            response = await self._http.post(self._url, json=payload, timeout=10)
        except httpx.HTTPError as exc:
            return Outcome("retry", f"network error: {type(exc).__name__}")
        try:
            body = response.json()
        except ValueError:
            body = {}
        return classify(response.status_code, body if isinstance(body, dict) else {})


async def lease_due(db: AsyncSession, limit: int = BATCH) -> list[Notification]:
    due = (
        select(Notification.id)
        .where(
            Notification.status == NotificationStatus.pending,
            Notification.next_attempt_at <= func.now(),
        )
        .order_by(Notification.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    rows = (
        await db.execute(
            update(Notification)
            .where(Notification.id.in_(due.scalar_subquery()))
            .values(next_attempt_at=func.now() + LEASE)
            .returning(
                Notification.id,
                Notification.chat_id,
                Notification.text,
                Notification.reply_markup,
                Notification.attempts,
            )
            .execution_options(synchronize_session=False)
        )
    ).all()
    await db.commit()
    return sorted(rows, key=lambda row: row.id)


async def record(db: AsyncSession, notification_id: int, attempts: int, outcome: Outcome) -> None:
    values: dict[str, Any] = {"last_error": outcome.error}
    if outcome.kind == "sent":
        values |= {"status": NotificationStatus.sent, "sent_at": func.now(), "last_error": None}
    elif outcome.kind == "undeliverable":
        values["status"] = NotificationStatus.undeliverable
    elif outcome.kind == "failed":
        values |= {"status": NotificationStatus.failed, "attempts": attempts + 1}
    elif outcome.kind == "rate_limited":
        values["next_attempt_at"] = func.now() + timedelta(seconds=outcome.retry_after or 5)
    else:  # retry
        tries = attempts + 1
        values["attempts"] = tries
        if tries >= MAX_ATTEMPTS:
            values["status"] = NotificationStatus.failed
        else:
            values["next_attempt_at"] = func.now() + backoff(tries)
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    await db.commit()


async def release_leases(db: AsyncSession, notification_ids: list[int]) -> None:
    """Give leased but unsent rows back, e.g. when Telegram asks us to slow down."""
    if not notification_ids:
        return
    await db.execute(
        update(Notification)
        .where(
            Notification.id.in_(notification_ids),
            Notification.status == NotificationStatus.pending,
        )
        .values(next_attempt_at=func.now())
        .execution_options(synchronize_session=False)
    )
    await db.commit()


async def send_batch(
    session_factory: Callable[[], AsyncSession],
    client: TelegramClient,
    gap: float = SEND_GAP_SECONDS,
) -> int:
    """Send one leased batch. Returns how many messages were delivered."""
    async with session_factory() as db:
        batch = await lease_due(db)
    sent = 0
    for index, row in enumerate(batch):
        try:
            outcome = await client.send(row.chat_id, row.text, row.reply_markup)
            async with session_factory() as db:
                await record(db, row.id, row.attempts, outcome)
        except Exception:
            logger.exception("sending notification %s failed", row.id)
            continue
        if outcome.kind == "sent":
            sent += 1
        if outcome.kind == "rate_limited":
            async with session_factory() as db:
                await release_leases(db, [r.id for r in batch[index + 1 :]])
            logger.warning("Telegram rate limit; pausing for %s s", outcome.retry_after)
            break
        if gap:
            await asyncio.sleep(gap)
    return sent


async def cleanup(db: AsyncSession) -> int:
    """Delete delivered (or undeliverable) messages older than the retention period."""
    result = await db.execute(
        delete(Notification).where(
            Notification.status.in_((NotificationStatus.sent, NotificationStatus.undeliverable)),
            Notification.created_at < func.now() - RETENTION,
        )
    )
    await db.commit()
    return result.rowcount or 0


async def run_sender(
    session_factory: Callable[[], AsyncSession], token: str, interval_seconds: float
) -> None:
    """Background loop started with the app; cancelled on shutdown."""
    loop = asyncio.get_running_loop()
    last_cleanup = loop.time()
    async with httpx.AsyncClient() as http:
        client = TelegramClient(token, http)
        while True:
            try:
                await send_batch(session_factory, client)
                if loop.time() - last_cleanup >= CLEANUP_EVERY_SECONDS:
                    async with session_factory() as db:
                        await cleanup(db)
                    last_cleanup = loop.time()
            except Exception:
                logger.exception("notification sender tick failed")
            await asyncio.sleep(interval_seconds)
