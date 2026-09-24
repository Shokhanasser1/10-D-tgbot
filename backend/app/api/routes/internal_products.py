from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CATALOG_ROLES, require_admin
from app.db.session import get_db
from app.schemas.internal import (
    AttributeAdminOut,
    AttributeCreate,
    AttributeUpdate,
    CategoryAdminOut,
    CategoryCreate,
    CategoryUpdate,
    ProductAdminOut,
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
from app.services import catalog_admin_service

router = APIRouter(
    prefix="/internal", tags=["internal"], dependencies=[Depends(require_admin(*CATALOG_ROLES))]
)


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
