from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_telegram_user
from app.api.locale import resolve_locale
from app.config import get_settings
from app.db.session import get_db
from app.models.telegram_user import TelegramUser
from app.schemas.cart import CartItemIn, CartItemQtyUpdate, CartOut
from app.services import cart_service

router = APIRouter(prefix="/cart", tags=["cart"])
settings = get_settings()


@router.get("/items", response_model=CartOut)
async def get_cart(
    locale: str | None = Query(default=None),
    user: TelegramUser = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
):
    return await cart_service.get_cart(
        db, user.telegram_id, resolve_locale(locale, user), settings.default_locale
    )


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
async def add_item(
    data: CartItemIn,
    locale: str | None = Query(default=None),
    user: TelegramUser = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
):
    await cart_service.add_item(
        db, user.telegram_id, data.variant_id, data.qty, replace_cart=data.replace_cart
    )
    return await cart_service.get_cart(
        db, user.telegram_id, resolve_locale(locale, user), settings.default_locale
    )


@router.patch("/items/{item_id}", response_model=CartOut)
async def update_item(
    item_id: int,
    data: CartItemQtyUpdate,
    locale: str | None = Query(default=None),
    user: TelegramUser = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
):
    await cart_service.update_item_qty(db, user.telegram_id, item_id, data.qty)
    return await cart_service.get_cart(
        db, user.telegram_id, resolve_locale(locale, user), settings.default_locale
    )


@router.delete("/items/{item_id}", response_model=CartOut)
async def remove_item(
    item_id: int,
    locale: str | None = Query(default=None),
    user: TelegramUser = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
):
    await cart_service.remove_item(db, user.telegram_id, item_id)
    return await cart_service.get_cart(
        db, user.telegram_id, resolve_locale(locale, user), settings.default_locale
    )
