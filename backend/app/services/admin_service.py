from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.admin import Admin
from app.models.enums import AdminRole
from app.schemas.admin import AdminCreate, AdminUpdate

_DUPLICATE = "An admin with this Telegram ID already exists"


async def bootstrap_owners(db: AsyncSession, telegram_ids: Iterable[int]) -> None:
    """Give each listed telegram_id an owner account unless it already has a row.

    Existing rows are never touched: dropping an ID from the list demotes nobody, and listing a
    deactivated admin does not bring them back.
    """
    rows = [
        {"telegram_id": tid, "role": AdminRole.owner, "display_name": "Owner"}
        for tid in dict.fromkeys(telegram_ids)
    ]
    if not rows:
        return
    await db.execute(
        pg_insert(Admin).values(rows).on_conflict_do_nothing(index_elements=[Admin.telegram_id])
    )
    await db.commit()


async def get_active_admin(db: AsyncSession, telegram_id: int) -> Admin | None:
    return (
        await db.execute(
            select(Admin)
            .where(Admin.telegram_id == telegram_id, Admin.is_active)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


async def list_admins(db: AsyncSession) -> list[Admin]:
    return list((await db.execute(select(Admin).order_by(Admin.id))).scalars().all())


async def create_admin(db: AsyncSession, data: AdminCreate, created_by: int | None) -> Admin:
    if await db.scalar(select(Admin.id).where(Admin.telegram_id == data.telegram_id)):
        raise ConflictError(_DUPLICATE, code="already_exists")

    admin = Admin(**data.model_dump(), created_by=created_by)
    db.add(admin)
    try:
        await db.commit()
    except IntegrityError as exc:  # lost a race with a concurrent create
        await db.rollback()
        raise ConflictError(_DUPLICATE, code="already_exists") from exc
    await db.refresh(admin)
    return admin


async def update_admin(
    db: AsyncSession, admin_id: int, data: AdminUpdate, actor_telegram_id: int | None
) -> Admin:
    # Lock every active owner first, so two owners demoting each other at the same moment
    # serialise here and the second one sees that it would remove the last owner.
    active_owner_ids = set(
        (
            await db.execute(
                select(Admin.id)
                .where(Admin.role == AdminRole.owner, Admin.is_active)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )

    admin = (
        await db.execute(
            select(Admin)
            .where(Admin.id == admin_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if admin is None:
        raise NotFoundError("Admin not found")

    changes = data.model_dump(exclude_unset=True)

    if changes.get("is_active") is False and admin.telegram_id == actor_telegram_id:
        await db.rollback()
        raise ConflictError("You cannot deactivate yourself", code="self_deactivation")

    stops_being_owner = admin.id in active_owner_ids and (
        changes.get("is_active") is False or changes.get("role", AdminRole.owner) != AdminRole.owner
    )
    if stops_being_owner and len(active_owner_ids) == 1:
        await db.rollback()
        raise ConflictError("There must be at least one active owner", code="last_owner")

    for field, value in changes.items():
        setattr(admin, field, value)
    await db.commit()
    await db.refresh(admin)
    return admin
