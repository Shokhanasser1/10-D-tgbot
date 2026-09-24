from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.courier import Courier, CourierLocation
from app.models.enums import ACTIVE_SHIPMENT_STATUSES, ShipmentStatus
from app.models.shipment import Shipment
from app.schemas.courier_admin import (
    CourierAdminListItem,
    CourierAdminOut,
    CourierCreate,
    CourierLocationAdminOut,
    CourierUpdate,
    ShipmentAdminOut,
)

settings = get_settings()

_DUPLICATE = "A courier with this Telegram ID already exists"


async def create_courier(db: AsyncSession, data: CourierCreate) -> Courier:
    if await db.scalar(select(Courier.id).where(Courier.telegram_id == data.telegram_id)):
        raise ConflictError(_DUPLICATE)

    courier = Courier(**data.model_dump())
    db.add(courier)
    try:
        await db.commit()
    except IntegrityError as exc:  # lost a race with a concurrent registration
        await db.rollback()
        raise ConflictError(_DUPLICATE) from exc
    await db.refresh(courier)
    return courier


async def update_courier(db: AsyncSession, courier_id: int, data: CourierUpdate) -> Courier:
    courier = await db.get(Courier, courier_id)
    if courier is None:
        raise NotFoundError("Courier not found")

    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(courier, field, value)

    if changes.get("is_active") is False:
        # A deactivated courier must not leave a frozen position behind.
        await db.execute(delete(CourierLocation).where(CourierLocation.courier_id == courier_id))

    await db.commit()
    await db.refresh(courier)
    return courier


def _active_counts() -> Select:
    return (
        select(Shipment.courier_id, func.count().label("active"))
        .where(Shipment.status.in_(ACTIVE_SHIPMENT_STATUSES))
        .group_by(Shipment.courier_id)
        .subquery()
    )


async def list_couriers(db: AsyncSession) -> list[CourierAdminListItem]:
    active = _active_counts()
    rows = await db.execute(
        select(Courier, func.coalesce(active.c.active, 0))
        .outerjoin(active, active.c.courier_id == Courier.id)
        .order_by(Courier.id)
        .execution_options(populate_existing=True)
    )
    return [
        CourierAdminListItem(
            **CourierAdminOut.model_validate(courier).model_dump(), active_deliveries=count
        )
        for courier, count in rows
    ]


async def list_locations(db: AsyncSession) -> list[CourierLocationAdminOut]:
    """Latest positions of couriers who are working now. A stored position exists only for a
    courier with an active delivery (see courier_state), and the join enforces it again."""
    active = _active_counts()
    rows = await db.execute(
        select(
            CourierLocation.courier_id,
            Courier.name,
            CourierLocation.latitude,
            CourierLocation.longitude,
            CourierLocation.updated_at,
            active.c.active,
        )
        .join(Courier, Courier.id == CourierLocation.courier_id)
        .join(active, active.c.courier_id == CourierLocation.courier_id)
        .order_by(Courier.name, Courier.id)
    )
    now = datetime.now(UTC)
    stale_after = timedelta(seconds=settings.location_stale_seconds)
    return [
        CourierLocationAdminOut(
            courier_id=r.courier_id,
            name=r.name,
            latitude=r.latitude,
            longitude=r.longitude,
            updated_at=r.updated_at,
            is_stale=now - r.updated_at > stale_after,
            active_deliveries=r.active,
        )
        for r in rows
    ]


async def list_shipments(
    db: AsyncSession, statuses: Sequence[ShipmentStatus]
) -> list[ShipmentAdminOut]:
    rows = (
        await db.execute(
            select(Shipment, Courier.name)
            .outerjoin(Courier, Courier.id == Shipment.courier_id)
            .where(Shipment.status.in_(statuses))
            .order_by(Shipment.id)
        )
    ).all()
    return [
        ShipmentAdminOut(
            id=shipment.id,
            order_id=shipment.order_id,
            status=shipment.status,
            courier_id=shipment.courier_id,
            courier_name=courier_name,
            assigned_at=shipment.assigned_at,
            picked_up_at=shipment.picked_up_at,
        )
        for shipment, courier_name in rows
    ]
