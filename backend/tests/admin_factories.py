import hashlib
import hmac
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import admin_session
from app.core.admin_session import sign_session
from app.models.admin import Admin
from app.models.enums import AdminRole
from tests.factories import TEST_BOT_TOKEN, add_seller, make_init_data

SESSION_SECRET = "test-admin-session-secret"


async def add_admin(
    db: AsyncSession,
    telegram_id: int,
    role: AdminRole = AdminRole.owner,
    *,
    display_name: str = "Admin",
    is_active: bool = True,
    seller_id: int | None = None,
) -> Admin:
    # A seller account always works for a seller (Spec 9); give it its own when none is named.
    if role == AdminRole.seller and seller_id is None:
        seller_id = (await add_seller(db, f"Shop of {telegram_id}")).id
    admin = Admin(
        telegram_id=telegram_id,
        role=role,
        display_name=display_name,
        is_active=is_active,
        seller_id=seller_id,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


def admin_tma(telegram_id: int) -> dict[str, str]:
    return {"Authorization": f"tma {make_init_data(telegram_id=telegram_id)}"}


def admin_confirmed(telegram_id: int, *, version: int = 1) -> dict[str, str]:
    """Mini App headers of an admin who re-entered their password a moment ago (Spec 7)."""
    confirm = admin_session.sign(telegram_id, version, SESSION_SECRET, kind=admin_session.CONFIRM)
    return {
        **admin_tma(telegram_id),
        "Cookie": f"admin_confirm={confirm}",
        "X-Requested-With": "admin",
    }


def admin_cookie(telegram_id: int, *, csrf: bool = True, issued_at: float | None = None) -> dict:
    headers = {
        "Cookie": f"admin_session={sign_session(telegram_id, SESSION_SECRET, now=issued_at)}"
    }
    if csrf:
        headers["X-Requested-With"] = "admin"
    return headers


def login_payload(
    telegram_id: int, *, auth_date: int | None = None, bot_token: str = TEST_BOT_TOKEN
) -> dict[str, str | int]:
    """A Telegram Login Widget payload signed the way Telegram signs it."""
    data: dict[str, str | int] = {
        "id": telegram_id,
        "first_name": "Owner",
        "username": "owner",
        "auth_date": auth_date if auth_date is not None else int(time.time()),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    key = hashlib.sha256(bot_token.encode()).digest()
    data["hash"] = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
    return data
