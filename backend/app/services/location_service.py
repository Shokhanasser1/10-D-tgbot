import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.models.courier import Courier
from app.schemas.telegram_update import TelegramUpdate
from app.services import courier_state


def _valid(latitude: float, longitude: float) -> bool:
    return (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


async def handle_update(db: AsyncSession, update: TelegramUpdate) -> None:
    """Store a courier's position from a Telegram update, or quietly ignore the update.

    Ignoring is the normal outcome for most updates and never raises or writes: Telegram retries
    anything that is not answered with 200, so an update we simply do not care about must not fail.
    """
    message = update.message or update.edited_message
    if message is None or message.location is None or message.sender is None:
        return
    if message.chat is None or message.chat.type != "private" or message.sender.is_bot:
        return
    if not _valid(message.location.latitude, message.location.longitude):
        return

    courier_id = await db.scalar(
        select(Courier.id).where(Courier.telegram_id == message.sender.id, Courier.is_active)
    )
    if courier_id is None:
        return

    # Serialise with the courier's own delivery actions: a position must never be stored for a
    # courier whose last delivery is ending in a concurrent request.
    try:
        await courier_state.lock_courier(db, courier_id)
    except ForbiddenError:
        return
    if await courier_state.count_active(db, courier_id) == 0:
        await db.rollback()  # nothing to store for an idle courier; release the lock
        return

    await courier_state.record_location(
        db, courier_id, message.location.latitude, message.location.longitude
    )
    await db.commit()
