from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import passwords
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.admin import Admin
from app.models.enums import AdminRole
from app.models.seller import Seller
from app.schemas.admin import AdminCreate, AdminUpdate

_DUPLICATE = "An admin with this Telegram ID already exists"
# Seller accounts are created and tied to their seller in /internal/sellers (Spec 9 section 5).
_SELLER_ROLE_FIXED = "Seller accounts are managed under Sellers"


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


async def seller_of(db: AsyncSession, admin: Admin) -> Seller | None:
    if admin.seller_id is None:
        return None
    return await db.get(Seller, admin.seller_id, populate_existing=True)


async def ensure_seller_active(db: AsyncSession, admin: Admin) -> Seller | None:
    """A seller's account works only while its seller is active (Spec 9 section 4)."""
    seller = await seller_of(db, admin)
    if seller is not None and not seller.is_active:
        raise ForbiddenError("This seller is deactivated", code="seller_inactive")
    return seller


async def list_admins(db: AsyncSession) -> list[Admin]:
    return list((await db.execute(select(Admin).order_by(Admin.id))).scalars().all())


async def create_admin(db: AsyncSession, data: AdminCreate, created_by: int | None) -> Admin:
    if data.role == AdminRole.seller:
        raise ConflictError(_SELLER_ROLE_FIXED, code="seller_role_fixed")
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

    if "role" in changes and (changes["role"] == AdminRole.seller) != (
        admin.role == AdminRole.seller
    ):
        await db.rollback()
        raise ConflictError(_SELLER_ROLE_FIXED, code="seller_role_fixed")

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


# --- passwords (Spec 7 §4) -------------------------------------------------------------------

MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)
_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    # Checked when the login is unknown, so both cases take about as long.
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = passwords.hash_password(passwords.temporary_password())
    return _DUMMY_HASH


async def _check_password_locked(db: AsyncSession, admin: Admin, password: str) -> bool:
    """Verify under the row lock, counting failures; commits. False when locked or wrong."""
    now = datetime.now(UTC)
    if admin.locked_until is not None and admin.locked_until > now:
        await db.rollback()
        return False
    if passwords.verify_password(password, admin.password_hash):
        admin.failed_logins = 0
        admin.locked_until = None
        await db.commit()
        return True
    admin.failed_logins += 1
    if admin.failed_logins >= MAX_FAILED_LOGINS:
        admin.failed_logins = 0
        admin.locked_until = now + LOCKOUT
    await db.commit()
    return False


async def _locked_admin(db: AsyncSession, *where) -> Admin | None:
    return (
        await db.execute(
            select(Admin).where(*where).with_for_update().execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


async def authenticate(db: AsyncSession, login: str, password: str) -> Admin | None:
    """The active admin with this login and password, or None for any kind of failure."""
    admin = await _locked_admin(db, Admin.login == passwords.normalize_login(login))
    if admin is None or not admin.is_active or admin.password_hash is None:
        await db.rollback()
        passwords.verify_password(password, _dummy_hash())
        return None
    return admin if await _check_password_locked(db, admin, password) else None


async def confirm_password(db: AsyncSession, telegram_id: int, password: str) -> bool:
    admin = await _locked_admin(db, Admin.telegram_id == telegram_id, Admin.is_active)
    if admin is None or admin.password_hash is None:
        await db.rollback()
        return False
    return await _check_password_locked(db, admin, password)


def _validated(login: str | None, password: str) -> None:
    problem = (passwords.login_problem(login) if login is not None else None) or (
        passwords.password_problem(password, login)
    )
    if problem:
        raise BadRequestError(problem)


def _store_password(admin: Admin, password: str, *, temporary: bool) -> None:
    admin.password_hash = passwords.hash_password(password)
    admin.must_change_password = temporary
    admin.password_changed_at = datetime.now(UTC)
    admin.failed_logins = 0
    admin.locked_until = None
    admin.session_version += 1  # every other session of this admin ends here


async def _commit_login_change(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("This login is taken", code="login_taken") from exc


async def set_own_password(
    db: AsyncSession,
    telegram_id: int,
    *,
    login: str | None,
    current_password: str | None,
    new_password: str,
) -> Admin:
    """Profile: set a first password (and login), or change it knowing the current one."""
    admin = await _locked_admin(db, Admin.telegram_id == telegram_id, Admin.is_active)
    if admin is None:
        raise NotFoundError("Admin not found")
    new_login = passwords.normalize_login(login) if login else admin.login
    if new_login is None:
        await db.rollback()
        raise BadRequestError("Choose a login")
    _validated(new_login, new_password)
    # A forced change (temporary password) or a first password needs no current password:
    # the admin is already signed in. Otherwise prove you know it.
    if admin.password_hash is not None and not admin.must_change_password:
        if not passwords.verify_password(current_password or "", admin.password_hash):
            await db.rollback()
            raise ForbiddenError("The current password is wrong", code="wrong_password")
    admin.login = new_login
    _store_password(admin, new_password, temporary=False)
    await _commit_login_change(db)
    await db.refresh(admin)
    return admin


async def reset_password(
    db: AsyncSession, admin_id: int, actor_telegram_id: int | None
) -> tuple[Admin, str]:
    """An owner's reset: a temporary password, shown once, that must be changed at sign-in."""
    admin = await _locked_admin(db, Admin.id == admin_id)
    if admin is None:
        raise NotFoundError("Admin not found")
    if admin.telegram_id == actor_telegram_id:
        await db.rollback()
        raise ConflictError("Change your own password in your profile", code="self_reset")
    temporary = passwords.temporary_password()
    if admin.login is None:
        admin.login = f"admin{admin.telegram_id}"[:32]
    _store_password(admin, temporary, temporary=True)
    await _commit_login_change(db)
    await db.refresh(admin)
    return admin, temporary


async def set_password_from_terminal(
    db: AsyncSession, telegram_id: int, login: str | None, password: str
) -> Admin:
    """scripts.set_admin_password: for the first owner on a machine without Telegram."""
    admin = await _locked_admin(db, Admin.telegram_id == telegram_id)
    if admin is None:
        raise NotFoundError(f"No admin with Telegram ID {telegram_id}")
    new_login = passwords.normalize_login(login) if login else admin.login or "owner"
    _validated(new_login, password)
    admin.login = new_login
    _store_password(admin, password, temporary=False)
    await _commit_login_change(db)
    await db.refresh(admin)
    return admin
