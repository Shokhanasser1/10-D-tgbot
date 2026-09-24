"""Admin sign-in. The only /internal routes that do not require an admin already."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ADMIN_SESSION_COOKIE,
    ANY_ADMIN,
    AdminPrincipal,
    require_admin,
)
from app.config import get_settings
from app.core.admin_session import sign_session
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import validate_login_widget
from app.db.session import get_db
from app.schemas.admin import AdminMeOut, TelegramLoginIn
from app.services import admin_service

settings = get_settings()

router = APIRouter(prefix="/internal", tags=["internal"])

_any_admin = require_admin(*ANY_ADMIN)

login_limiter = SlidingWindowLimiter(settings.admin_login_rate_limit_per_minute)


def _client_ip(request: Request) -> str:
    # nginx sets X-Real-IP; the API port itself is bound to loopback, so it cannot be spoofed
    # from outside.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "")


@router.post("/auth/telegram", response_model=AdminMeOut)
async def login_with_telegram(
    data: TelegramLoginIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    if not login_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Slow down")
    if not settings.admin_session_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Browser sign-in is off"
        )

    # The hash covers exactly the fields the widget sent, as strings.
    fields = {k: str(v) for k, v in data.model_dump(exclude_none=True).items()}
    telegram_id = validate_login_widget(
        fields, settings.telegram_bot_token, settings.telegram_login_max_age_seconds
    )

    admin = await admin_service.get_active_admin(db, telegram_id)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an admin")

    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        sign_session(telegram_id, settings.admin_session_secret),
        max_age=settings.admin_session_max_age_seconds,
        httponly=True,
        secure=settings.admin_cookie_secure,
        samesite="strict",
        path="/",
    )
    return AdminMeOut(
        telegram_id=admin.telegram_id, display_name=admin.display_name, role=admin.role
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    response.delete_cookie(
        ADMIN_SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=settings.admin_cookie_secure,
        samesite="strict",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=AdminMeOut)
async def me(principal: AdminPrincipal = Depends(_any_admin)):
    return AdminMeOut(
        telegram_id=principal.telegram_id,
        display_name=principal.display_name,
        role=principal.role,
    )
