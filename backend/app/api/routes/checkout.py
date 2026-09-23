from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_telegram_user
from app.api.locale import resolve_locale
from app.config import get_settings
from app.db.session import get_db
from app.models.telegram_user import TelegramUser
from app.schemas.checkout import CheckoutRequest, CheckoutResponse
from app.services import checkout_service

router = APIRouter(tags=["checkout"])
settings = get_settings()


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    data: CheckoutRequest,
    locale: str | None = Query(default=None),
    user: TelegramUser = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
):
    return await checkout_service.create_order_from_cart(
        db,
        user.telegram_id,
        data.delivery_address,
        settings.default_currency,
        resolve_locale(locale, user),
        settings.default_locale,
    )
