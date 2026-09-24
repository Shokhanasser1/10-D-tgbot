from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attribute import Attribute
from app.models.category import Category
from app.models.product import Product
from app.models.translation import Translation
from app.models.variant import Variant
from app.schemas.internal import (
    AttributeCreate,
    AttributeUpdate,
    CategoryCreate,
    CategoryUpdate,
    ProductCreate,
    ProductUpdate,
    TranslationUpsert,
    VariantCreate,
    VariantUpdate,
)


async def create_category(db: AsyncSession, data: CategoryCreate) -> Category:
    category = Category(**data.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def update_category(
    db: AsyncSession, category_id: int, data: CategoryUpdate
) -> Category | None:
    category = await db.get(Category, category_id)
    if category is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    await db.commit()
    await db.refresh(category)
    return category


async def create_attribute(db: AsyncSession, data: AttributeCreate) -> Attribute:
    attribute = Attribute(**data.model_dump())
    db.add(attribute)
    await db.commit()
    await db.refresh(attribute)
    return attribute


async def update_attribute(
    db: AsyncSession, attribute_id: int, data: AttributeUpdate
) -> Attribute | None:
    attribute = await db.get(Attribute, attribute_id)
    if attribute is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(attribute, field, value)
    await db.commit()
    await db.refresh(attribute)
    return attribute


async def create_product(db: AsyncSession, data: ProductCreate) -> Product:
    product = Product(**data.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def update_product(db: AsyncSession, product_id: int, data: ProductUpdate) -> Product | None:
    product = await db.get(Product, product_id)
    if product is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return product


async def create_variant(db: AsyncSession, data: VariantCreate) -> Variant:
    variant = Variant(**data.model_dump())
    db.add(variant)
    await db.commit()
    await db.refresh(variant)
    return variant


async def update_variant(db: AsyncSession, variant_id: int, data: VariantUpdate) -> Variant | None:
    variant = await db.get(Variant, variant_id)
    if variant is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)
    await db.commit()
    await db.refresh(variant)
    return variant


async def upsert_translation(db: AsyncSession, data: TranslationUpsert) -> Translation:
    stmt = select(Translation).where(
        Translation.entity_type == data.entity_type,
        Translation.entity_id == data.entity_id,
        Translation.locale == data.locale,
        Translation.field == data.field,
    )
    translation = (await db.execute(stmt)).scalar_one_or_none()
    if translation is None:
        translation = Translation(**data.model_dump())
        db.add(translation)
    else:
        translation.value = data.value
    await db.commit()
    await db.refresh(translation)
    return translation
