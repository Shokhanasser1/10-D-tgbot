from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CATALOG_ROLES, require_admin
from app.config import get_settings
from app.db.session import get_db
from app.models.enums import ProductStatus
from app.schemas.internal import (
    AttributeAdminListItem,
    AttributeAdminOut,
    AttributeCreate,
    AttributeUpdate,
    CategoryAdminListItem,
    CategoryAdminOut,
    CategoryCreate,
    CategoryUpdate,
    ProductAdminDetailOut,
    ProductAdminOut,
    ProductAdminPage,
    ProductCreate,
    ProductImageCreate,
    ProductImageOut,
    ProductUpdate,
    TranslationOut,
    TranslationUpsert,
    VariantAdminOut,
    VariantCreate,
    VariantUpdate,
)
from app.services import catalog_admin_query_service, catalog_admin_service

settings = get_settings()

router = APIRouter(
    prefix="/internal", tags=["internal"], dependencies=[Depends(require_admin(*CATALOG_ROLES))]
)


def _locale(locale: str | None = Query(default=None)) -> str:
    return locale if locale in settings.supported_locales else settings.default_locale


@router.get("/categories", response_model=list[CategoryAdminListItem])
async def list_categories(locale: str = Depends(_locale), db: AsyncSession = Depends(get_db)):
    return await catalog_admin_query_service.list_categories(db, locale, settings.default_locale)


@router.get("/attributes", response_model=list[AttributeAdminListItem])
async def list_attributes(db: AsyncSession = Depends(get_db)):
    return await catalog_admin_query_service.list_attributes(db)


@router.get("/products", response_model=ProductAdminPage)
async def list_products(
    product_status: ProductStatus | None = Query(default=None, alias="status"),
    category_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    locale: str = Depends(_locale),
    db: AsyncSession = Depends(get_db),
):
    return await catalog_admin_query_service.list_products(
        db,
        locale,
        settings.default_locale,
        status=product_status,
        category_id=category_id,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/products/{product_id}", response_model=ProductAdminDetailOut)
async def get_product(
    product_id: int, locale: str = Depends(_locale), db: AsyncSession = Depends(get_db)
):
    product = await catalog_admin_query_service.get_product(
        db, product_id, locale, settings.default_locale
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.post("/categories", response_model=CategoryAdminOut, status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryCreate, db: AsyncSession = Depends(get_db)):
    return await catalog_admin_service.create_category(db, data)


@router.patch("/categories/{category_id}", response_model=CategoryAdminOut)
async def update_category(
    category_id: int, data: CategoryUpdate, db: AsyncSession = Depends(get_db)
):
    category = await catalog_admin_service.update_category(db, category_id, data)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


@router.post("/attributes", response_model=AttributeAdminOut, status_code=status.HTTP_201_CREATED)
async def create_attribute(data: AttributeCreate, db: AsyncSession = Depends(get_db)):
    return await catalog_admin_service.create_attribute(db, data)


@router.patch("/attributes/{attribute_id}", response_model=AttributeAdminOut)
async def update_attribute(
    attribute_id: int, data: AttributeUpdate, db: AsyncSession = Depends(get_db)
):
    attribute = await catalog_admin_service.update_attribute(db, attribute_id, data)
    if attribute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found")
    return attribute


@router.post("/products", response_model=ProductAdminOut, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, db: AsyncSession = Depends(get_db)):
    return await catalog_admin_service.create_product(db, data)


@router.patch("/products/{product_id}", response_model=ProductAdminOut)
async def update_product(product_id: int, data: ProductUpdate, db: AsyncSession = Depends(get_db)):
    product = await catalog_admin_service.update_product(db, product_id, data)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.post("/variants", response_model=VariantAdminOut, status_code=status.HTTP_201_CREATED)
async def create_variant(data: VariantCreate, db: AsyncSession = Depends(get_db)):
    return await catalog_admin_service.create_variant(db, data)


@router.patch("/variants/{variant_id}", response_model=VariantAdminOut)
async def update_variant(variant_id: int, data: VariantUpdate, db: AsyncSession = Depends(get_db)):
    variant = await catalog_admin_service.update_variant(db, variant_id, data)
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    return variant


@router.post(
    "/products/{product_id}/images",
    response_model=ProductImageOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_image(
    product_id: int, data: ProductImageCreate, db: AsyncSession = Depends(get_db)
):
    image = await catalog_admin_service.create_product_image(db, product_id, data)
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return image


@router.post("/translations", response_model=TranslationOut, status_code=status.HTTP_201_CREATED)
async def upsert_translation(data: TranslationUpsert, db: AsyncSession = Depends(get_db)):
    return await catalog_admin_service.upsert_translation(db, data)
