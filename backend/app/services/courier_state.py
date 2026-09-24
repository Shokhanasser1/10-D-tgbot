"""Shared primitives for everything that changes a courier's deliveries or stored position.

Lock order, everywhere: courier row -> shipment -> order -> courier location. Taking the
courier row first serialises a courier's own actions (the concurrent-delivery limit, and the
"only a working courier has a stored position" rule) and keeps the owner's release path from
deadlocking against a courier's own actions.
"""

from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.models.courier import Courier, CourierLocation
from app.models.enums import ACTIVE_SHIPMENT_STATUSES
from app.models.shipment import Shipment


async def lock_courier(db: AsyncSession, courier_id: int, *, require_active: bool = True) -> None:
    # Select the column, not the entity: the lock is what matters, and a fresh read avoids
    # trusting a possibly stale object in the session's identity map.
    is_active = await db.scalar(
        select(Courier.is_active).where(Courier.id == courier_id).with_for_update()
    )
    if is_active is None or (require_active and not is_active):
        raise ForbiddenError("Not a courier")


async def count_active(db: AsyncSession, courier_id: int) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(Shipment)
        .where(Shipment.courier_id == courier_id, Shipment.status.in_(ACTIVE_SHIPMENT_STATUSES))
    )
    return count or 0


async def clear_location(db: AsyncSession, courier_id: int) -> None:
    await db.execute(delete(CourierLocation).where(CourierLocation.courier_id == courier_id))


async def purge_location_if_idle(db: AsyncSession, courier_id: int) -> None:
    """Delete the courier's stored position unless they still hold an active delivery."""
    still_working = exists().where(
        Shipment.courier_id == courier_id, Shipment.status.in_(ACTIVE_SHIPMENT_STATUSES)
    )
    await db.execute(
        delete(CourierLocation).where(CourierLocation.courier_id == courier_id, ~still_working)
    )
