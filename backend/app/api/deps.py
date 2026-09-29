import hmac
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import admin_session
from app.core.exceptions import ForbiddenError
from app.core.permissions import CONFIRMATION_REQUIRED, permissions_of
from app.core.security import validate_init_data
from app.db.session import get_db
from app.models.courier import Courier
from app.models.enums import AdminRole, Permission
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
    permissions: frozenset[Permission] = field(default_factory=frozenset)
    has_password: bool = False
    must_change_password: bool = False
    # Password re-entered recently (Spec 7 §5); always true for the internal token.
    confirmed: bool = False
    session_version: int = 1

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions


ADMIN_SESSION_COOKIE = "admin_session"
ADMIN_CONFIRM_COOKIE = "admin_confirm"
CONFIRMATION_MAX_AGE_SECONDS = 15 * 60
# Cookies are ambient credentials, so a state-changing request authenticated by one must also
# carry this header. A cross-site form cannot set it; SameSite=Strict is the first line.
ADMIN_CSRF_HEADER = "x-requested-with"
ADMIN_CSRF_VALUE = "admin"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _not_signed_in() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")


async def _resolve_admin(
    request: Request, authorization: str | None, x_internal_token: str | None, db: AsyncSession
) -> AdminPrincipal:
    """Who is calling /internal/*: the internal token, a Mini App user, or a browser session.

    The admins row is re-read on every request, so a deactivation, role change or password
    change applies at once.
    """
    if x_internal_token is not None:
        _check_internal_token(x_internal_token)
        return AdminPrincipal(
            telegram_id=None,
            role=AdminRole.owner,
            display_name="Internal",
            permissions=permissions_of(AdminRole.owner),
            confirmed=True,
        )

    session_version: int | None = None
    if authorization is not None:
        init_data = validate_init_data(
            get_init_data_raw(authorization),
            settings.telegram_bot_token,
            settings.telegram_init_data_max_age_seconds,
        )
        telegram_id = init_data.user.id
    else:
        cookie = request.cookies.get(ADMIN_SESSION_COOKIE)
        signed = (
            admin_session.verify(
                cookie, settings.admin_session_secret, settings.admin_session_max_age_seconds
            )
            if cookie
            else None
        )
        if signed is None:
            raise _not_signed_in()
        if (
            request.method not in _SAFE_METHODS
            and request.headers.get(ADMIN_CSRF_HEADER) != ADMIN_CSRF_VALUE
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing CSRF header")
        telegram_id, session_version = signed.telegram_id, signed.version

    admin = await admin_service.get_active_admin(db, telegram_id)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an admin")
    if session_version is not None and session_version != admin.session_version:
        raise _not_signed_in()  # signed out by a password change or reset

    return AdminPrincipal(
        telegram_id=admin.telegram_id,
        role=admin.role,
        display_name=admin.display_name,
        permissions=permissions_of(admin.role),
        has_password=admin.password_hash is not None,
        must_change_password=admin.must_change_password,
        confirmed=_confirmed(request, admin.telegram_id, admin.session_version),
        session_version=admin.session_version,
    )


def _confirmed(request: Request, telegram_id: int, version: int) -> bool:
    cookie = request.cookies.get(ADMIN_CONFIRM_COOKIE)
    if not cookie:
        return False
    signed = admin_session.verify(
        cookie,
        settings.admin_session_secret,
        CONFIRMATION_MAX_AGE_SECONDS,
        kind=admin_session.CONFIRM,
    )
    return signed is not None and signed.telegram_id == telegram_id and signed.version == version


async def get_admin_even_if_password_must_change(
    request: Request,
    authorization: str | None = Header(default=None),
    x_internal_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> AdminPrincipal:
    """Only for "who am I" and "change my password": the way out of a forced change."""
    return await _resolve_admin(request, authorization, x_internal_token, db)


async def get_admin_principal(
    principal: AdminPrincipal = Depends(get_admin_even_if_password_must_change),
) -> AdminPrincipal:
    if principal.must_change_password:
        raise ForbiddenError(
            "Set a new password in your profile first", code="password_change_required"
        )
    return principal


def ensure_confirmed(principal: AdminPrincipal) -> None:
    """Dangerous actions need the password re-entered recently (Spec 7 §5)."""
    if principal.confirmed:
        return
    if not principal.has_password:
        raise ForbiddenError("Set a password in your profile to do this", code="password_not_set")
    raise ForbiddenError("Confirm with your password", code="password_confirmation_required")


def check_permission(
    principal: AdminPrincipal, permission: Permission, *, confirm: bool = True
) -> None:
    if not principal.can(permission):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    if confirm and permission in CONFIRMATION_REQUIRED:
        ensure_confirmed(principal)


def require_permission(
    permission: Permission, *, confirm: bool = True
) -> Callable[..., Awaitable[AdminPrincipal]]:
    """`confirm=False` for reading behind a 🔒 permission (e.g. listing admins)."""

    async def _require(principal: AdminPrincipal = Depends(get_admin_principal)) -> AdminPrincipal:
        check_permission(principal, permission, confirm=confirm)
        return principal

    return _require


def require_view_or_edit(
    view: Permission, edit: Permission
) -> Callable[..., Awaitable[AdminPrincipal]]:
    """For a router: reads need `view`, every other method `edit`."""

    async def _require(
        request: Request, principal: AdminPrincipal = Depends(get_admin_principal)
    ) -> AdminPrincipal:
        check_permission(principal, view if request.method in _SAFE_METHODS else edit)
        return principal

    return _require


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
