"""Admin sign-in and profile. The only /internal routes that do not require an admin already."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ADMIN_CONFIRM_COOKIE,
    ADMIN_CSRF_HEADER,
    ADMIN_CSRF_VALUE,
    ADMIN_SESSION_COOKIE,
    CONFIRMATION_MAX_AGE_SECONDS,
    AdminPrincipal,
    get_admin_even_if_password_must_change,
)
from app.config import get_settings
from app.core import admin_session
from app.core.exceptions import ForbiddenError
from app.core.permissions import permissions_of
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import validate_login_widget
from app.db.session import get_db
from app.models.admin import Admin
from app.schemas.admin import (
    AdminMeOut,
    PasswordChangeIn,
    PasswordConfirmIn,
    PasswordLoginIn,
    TelegramLoginIn,
)
from app.services import admin_service

settings = get_settings()

router = APIRouter(prefix="/internal", tags=["internal"])

login_limiter = SlidingWindowLimiter(settings.admin_login_rate_limit_per_minute)

_WRONG_CREDENTIALS = "Wrong login or password"


def _client_ip(request: Request) -> str:
    # nginx sets X-Real-IP; the API port itself is bound to loopback, so it cannot be spoofed
    # from outside.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "")


def _throttle(request: Request) -> None:
    if not login_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Slow down")
    if not settings.admin_session_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Browser sign-in is off"
        )


def _set_cookie(response: Response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        secure=settings.admin_cookie_secure,
        samesite="strict",
        path="/",
    )


def _start_session(response: Response, admin: Admin) -> None:
    _set_cookie(
        response,
        ADMIN_SESSION_COOKIE,
        admin_session.sign(admin.telegram_id, admin.session_version, settings.admin_session_secret),
        settings.admin_session_max_age_seconds,
    )


async def _me(db: AsyncSession, admin: Admin) -> AdminMeOut:
    seller = await admin_service.seller_of(db, admin)
    return AdminMeOut(
        telegram_id=admin.telegram_id,
        display_name=admin.display_name,
        role=admin.role,
        permissions=sorted(permissions_of(admin.role)),
        login=admin.login,
        has_password=admin.password_hash is not None,
        must_change_password=admin.must_change_password,
        seller_id=seller.id if seller else None,
        seller_name=seller.name if seller else None,
    )


@router.post("/auth/telegram", response_model=AdminMeOut)
async def login_with_telegram(
    data: TelegramLoginIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    _throttle(request)
    # The hash covers exactly the fields the widget sent, as strings.
    fields = {k: str(v) for k, v in data.model_dump(exclude_none=True).items()}
    telegram_id = validate_login_widget(
        fields, settings.telegram_bot_token, settings.telegram_login_max_age_seconds
    )

    admin = await admin_service.get_active_admin(db, telegram_id)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an admin")
    await admin_service.ensure_seller_active(db, admin)
    _start_session(response, admin)
    return await _me(db, admin)


@router.post("/auth/password", response_model=AdminMeOut)
async def login_with_password(
    data: PasswordLoginIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Sign in with a login and password (Spec 7 section 4). Every failure answers the same."""
    _throttle(request)
    admin = await admin_service.authenticate(db, data.login, data.password)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_WRONG_CREDENTIALS)
    await admin_service.ensure_seller_active(db, admin)
    _start_session(response, admin)
    return await _me(db, admin)


@router.post("/auth/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_with_password(
    data: PasswordConfirmIn,
    request: Request,
    response: Response,
    principal: AdminPrincipal = Depends(get_admin_even_if_password_must_change),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Re-enter the password to unlock dangerous actions for a few minutes (Spec 7 section 5)."""
    _throttle(request)
    response.status_code = status.HTTP_204_NO_CONTENT
    if principal.telegram_id is None:  # the internal token needs no confirmation
        return response
    # The cookie also authorises writes made from inside the Mini App, so ask for the header a
    # cookie-authenticated write needs, whichever way this request itself was authenticated.
    if request.headers.get(ADMIN_CSRF_HEADER) != ADMIN_CSRF_VALUE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing CSRF header")
    if not principal.has_password:
        raise ForbiddenError("Set a password in your profile first", code="password_not_set")
    if not await admin_service.confirm_password(db, principal.telegram_id, data.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong password")
    _set_cookie(
        response,
        ADMIN_CONFIRM_COOKIE,
        admin_session.sign(
            principal.telegram_id,
            principal.session_version,
            settings.admin_session_secret,
            kind=admin_session.CONFIRM,
        ),
        CONFIRMATION_MAX_AGE_SECONDS,
    )
    return response


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    for name in (ADMIN_SESSION_COOKIE, ADMIN_CONFIRM_COOKIE):
        response.delete_cookie(
            name,
            path="/",
            httponly=True,
            secure=settings.admin_cookie_secure,
            samesite="strict",
        )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=AdminMeOut)
async def me(
    principal: AdminPrincipal = Depends(get_admin_even_if_password_must_change),
    db: AsyncSession = Depends(get_db),
):
    if principal.telegram_id is None:
        return AdminMeOut(
            telegram_id=None,
            display_name=principal.display_name,
            role=principal.role,
            permissions=sorted(principal.permissions),
        )
    admin = await admin_service.get_active_admin(db, principal.telegram_id)
    if admin is None:  # deactivated between the dependency and here
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an admin")
    return await _me(db, admin)


@router.post("/me/password", response_model=AdminMeOut)
async def change_my_password(
    data: PasswordChangeIn,
    request: Request,
    response: Response,
    principal: AdminPrincipal = Depends(get_admin_even_if_password_must_change),
    db: AsyncSession = Depends(get_db),
):
    """Set a first password (with a login) or change it. Signs out every other session."""
    _throttle(request)
    if principal.telegram_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not for scripts")
    admin = await admin_service.set_own_password(
        db,
        principal.telegram_id,
        login=data.login,
        current_password=data.current_password,
        new_password=data.new_password,
    )
    # This browser stays signed in, with the new session version.
    if request.cookies.get(ADMIN_SESSION_COOKIE):
        _start_session(response, admin)
    return await _me(db, admin)
