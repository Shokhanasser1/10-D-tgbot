from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_telegram_user
from app.api.locale import resolve_locale
from app.config import get_settings
from app.db.session import get_db
from app.models.telegram_user import TelegramUser
from app.schemas.catalog import CategoryOut, ProductDetailOut, ProductListItemOut
from app.services import catalog_service

router = APIRouter(prefix="/catalog", tags=["catalog"])
settings = get_settings()


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    locale: str | None = Query(default=None),
    user: TelegramUser = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
):
    return await catalog_service.list_categories(
        db, resolve_locale(locale, user), settings.default_locale
    )


@router.get("/products", response_model=list[ProductListItemOut])
async def list_products(
    category: int | None = Query(default=None),
    seller: int | None = Query(default=None),
    locale: str | None = Query(default=None),
    user: TelegramUser = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
):
    return await catalog_service.list_products(
        db,
        resolve_locale(locale, user),
        settings.default_locale,
        category_id=category,
        seller_id=seller,
    )


@router.get("/products/{product_id}", response_model=ProductDetailOut)
async def get_product(
    product_id: int,
    locale: str | None = Query(default=None),
    user: TelegramUser = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
):
    product = await catalog_service.get_product(
        db, product_id, resolve_locale(locale, user), settings.default_locale
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product
