from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.courier import Courier, CourierLocation
from app.schemas.courier_admin import CourierCreate, CourierUpdate

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


async def list_couriers(db: AsyncSession) -> list[Courier]:
    return list((await db.execute(select(Courier).order_by(Courier.id))).scalars().all())
