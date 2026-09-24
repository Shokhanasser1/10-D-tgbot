import hmac
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.admin_session import verify_session
from app.core.security import validate_init_data
from app.db.session import get_db
from app.models.courier import Courier
from app.models.enums import AdminRole
from app.models.telegram_user import TelegramUser
from app.services import admin_service

settings = get_settings()

_INIT_DATA_PREFIX = "tma "


def get_init_data_raw(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith(_INIT_DATA_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    return authorization.removeprefix(_INIT_DATA_PREFIX)


async def get_current_telegram_user(
    init_data_raw: str = Depends(get_init_data_raw),
    db: AsyncSession = Depends(get_db),
) -> TelegramUser:
    init_data = validate_init_data(
        init_data_raw, settings.telegram_bot_token, settings.telegram_init_data_max_age_seconds
    )

    telegram_user = await db.get(TelegramUser, init_data.user.id)

    if telegram_user is None:
        resolved_locale = (
            init_data.user.language_code
            if init_data.user.language_code in settings.supported_locales
            else settings.default_locale
        )
        telegram_user = TelegramUser(
            telegram_id=init_data.user.id,
            username=init_data.user.username,
            first_name=init_data.user.first_name,
            last_name=init_data.user.last_name,
            locale=resolved_locale,
        )
        db.add(telegram_user)
    else:
        telegram_user.username = init_data.user.username
        telegram_user.first_name = init_data.user.first_name
        telegram_user.last_name = init_data.user.last_name

    await db.commit()
    await db.refresh(telegram_user)
    return telegram_user


def _check_internal_token(value: str) -> None:
    # Compare bytes: hmac.compare_digest raises TypeError for a non-ASCII str, which would
    # surface as a 500 instead of a 403.
    if not settings.internal_api_token or not hmac.compare_digest(
        value.encode(), settings.internal_api_token.encode()
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid internal token")


@dataclass(frozen=True)
class AdminPrincipal:
    telegram_id: int | None  # None for the internal token (scripts), which acts as an owner
    role: AdminRole
    display_name: str


ADMIN_SESSION_COOKIE = "admin_session"
# Cookies are ambient credentials, so a state-changing request authenticated by one must also
# carry this header. A cross-site form cannot set it; SameSite=Strict is the first line.
ADMIN_CSRF_HEADER = "x-requested-with"
ADMIN_CSRF_VALUE = "admin"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def get_admin_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    x_internal_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> AdminPrincipal:
    """Who is calling /internal/*: the internal token, a Mini App user, or a browser session.

    The admins row is re-read on every request, so a deactivation or role change applies at once.
    """
    if x_internal_token is not None:
        _check_internal_token(x_internal_token)
        return AdminPrincipal(telegram_id=None, role=AdminRole.owner, display_name="Internal")

    if authorization is not None:
        init_data = validate_init_data(
            get_init_data_raw(authorization),
            settings.telegram_bot_token,
            settings.telegram_init_data_max_age_seconds,
        )
        telegram_id = init_data.user.id
    else:
        cookie = request.cookies.get(ADMIN_SESSION_COOKIE)
        session_id = (
            verify_session(
                cookie, settings.admin_session_secret, settings.admin_session_max_age_seconds
            )
            if cookie
            else None
        )
        if session_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
        if (
            request.method not in _SAFE_METHODS
            and request.headers.get(ADMIN_CSRF_HEADER) != ADMIN_CSRF_VALUE
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing CSRF header")
        telegram_id = session_id

    admin = await admin_service.get_active_admin(db, telegram_id)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an admin")
    return AdminPrincipal(
        telegram_id=admin.telegram_id, role=admin.role, display_name=admin.display_name
    )


def require_admin(*roles: AdminRole) -> Callable[..., Awaitable[AdminPrincipal]]:
    allowed = frozenset(roles)

    async def _require(principal: AdminPrincipal = Depends(get_admin_principal)) -> AdminPrincipal:
        if principal.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
        return principal

    return _require


ANY_ADMIN = (AdminRole.owner, AdminRole.catalog_manager, AdminRole.dispatcher)
CATALOG_ROLES = (AdminRole.owner, AdminRole.catalog_manager)
DISPATCH_ROLES = (AdminRole.owner, AdminRole.dispatcher)


async def get_current_courier(
    user: TelegramUser = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
) -> Courier:
    courier = (
        await db.execute(
            select(Courier).where(Courier.telegram_id == user.telegram_id, Courier.is_active)
        )
    ).scalar_one_or_none()
    if courier is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a courier")
    return courier


def verify_telegram_webhook_secret(
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> None:
    if not settings.telegram_webhook_secret:
        # Feature switched off: behave as if the route does not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token.encode(), settings.telegram_webhook_secret.encode()
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")
