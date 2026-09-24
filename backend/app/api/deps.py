import hmac

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import validate_init_data
from app.db.session import get_db
from app.models.courier import Courier
from app.models.telegram_user import TelegramUser

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


def verify_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    # Compare bytes: hmac.compare_digest raises TypeError for a non-ASCII str, which would
    # surface as a 500 instead of a 403.
    if not x_internal_token or not hmac.compare_digest(
        x_internal_token.encode(), settings.internal_api_token.encode()
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid internal token")


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
