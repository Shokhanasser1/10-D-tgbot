"""Seed a small demo cosmetics catalog for local QA / frontend development.

Usage (from backend/): python -m scripts.seed_demo_data
"""

import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.enums import AttributeValueType, ProductStatus
from app.models.product import Product
from app.models.seller import Seller
from app.schemas.internal import (
    AttributeCreate,
    CategoryCreate,
    ProductCreate,
    ProductImageCreate,
    TranslationUpsert,
    VariantCreate,
)
from app.services import catalog_admin_service, image_service


async def seed_into(db: AsyncSession) -> None:
    """The demo catalog, written through the same services the admin API uses."""
    # Every product belongs to a seller (Spec 9); the demo has a single shop.
    shop = Seller(
        name="Demo shop", phone="+998 90 000 00 00", pickup_address="Tashkent, Amir Temur 1"
    )
    db.add(shop)
    await db.flush()

    lipstick_category = await catalog_admin_service.create_category(
        db, CategoryCreate(slug="lipstick", sort_order=0)
    )
    await catalog_admin_service.create_attribute(
        db,
        AttributeCreate(
            key="shade", category_id=lipstick_category.id, value_type=AttributeValueType.text
        ),
    )

    lipstick = await catalog_admin_service.create_product(
        db,
        ProductCreate(
            category_id=lipstick_category.id,
            seller_id=shop.id,
            base_sku="LIP-VELVET",
            base_price="89000",
            status=ProductStatus.active,
        ),
    )
    for locale, name, description in [
        ("en", "Velvet Matte Lipstick", "Long-lasting matte finish, no dry feel."),
        ("ru", "Матовая помада Velvet", "Стойкое матовое покрытие без ощущения сухости."),
        ("uz", "Velvet Mat Lipstik", "Uzoq muddatli mat effekt, quruqlik hissiz."),
    ]:
        await catalog_admin_service.upsert_translation(
            db,
            TranslationUpsert(
                entity_type="product",
                entity_id=lipstick.id,
                locale=locale,
                field="name",
                value=name,
            ),
        )
        await catalog_admin_service.upsert_translation(
            db,
            TranslationUpsert(
                entity_type="product",
                entity_id=lipstick.id,
                locale=locale,
                field="description",
                value=description,
            ),
        )
    for sku_suffix, shade in [("RED", "red"), ("NUDE", "nude"), ("BERRY", "berry")]:
        await catalog_admin_service.create_variant(
            db,
            VariantCreate(
                product_id=lipstick.id,
                sku=f"LIP-VELVET-{sku_suffix}",
                price="89000",
                stock_qty=25,
                attribute_values={"shade": shade},
            ),
        )
    await image_service.add_image_by_url(
        db,
        lipstick.id,
        ProductImageCreate(url="https://picsum.photos/seed/lipstick/600/600", position=0),
    )

    serum_category = await catalog_admin_service.create_category(
        db, CategoryCreate(slug="serums", sort_order=1)
    )
    serum = await catalog_admin_service.create_product(
        db,
        ProductCreate(
            category_id=serum_category.id,
            seller_id=shop.id,
            base_sku="SERUM-VITC",
            base_price="129000",
            status=ProductStatus.active,
        ),
    )
    for locale, name, description in [
        ("en", "Vitamin C Brightening Serum", "Brightens and evens skin tone."),
        ("ru", "Сыворотка с витамином C", "Осветляет и выравнивает тон кожи."),
        ("uz", "Vitamin C Serumi", "Terini yorqinlashtiradi va tekislaydi."),
    ]:
        await catalog_admin_service.upsert_translation(
            db,
            TranslationUpsert(
                entity_type="product",
                entity_id=serum.id,
                locale=locale,
                field="name",
                value=name,
            ),
        )
        await catalog_admin_service.upsert_translation(
            db,
            TranslationUpsert(
                entity_type="product",
                entity_id=serum.id,
                locale=locale,
                field="description",
                value=description,
            ),
        )
    await catalog_admin_service.create_variant(
        db,
        VariantCreate(product_id=serum.id, sku="SERUM-VITC-30ML", price="129000", stock_qty=40),
    )
    await image_service.add_image_by_url(
        db,
        serum.id,
        ProductImageCreate(url="https://picsum.photos/seed/serum/600/600", position=0),
    )


async def seed() -> None:
    async with async_session_factory() as db:
        if await db.scalar(select(func.count()).select_from(Product)):
            # Running it twice would clash with the slugs and SKUs created the first time.
            print("The catalog already has products; nothing to seed.")
            return
        await seed_into(db)
    print("Seed complete: 1 seller, 2 categories, 2 products, 4 variants.")


if __name__ == "__main__":
    asyncio.run(seed())
