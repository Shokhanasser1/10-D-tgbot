"""Seed a small demo cosmetics catalog for local QA / frontend development.

Usage (from backend/): python -m scripts.seed_demo_data
"""

import asyncio

from app.db.session import async_session_factory
from app.models.enums import AttributeValueType, ProductStatus
from app.schemas.internal import (
    AttributeCreate,
    CategoryCreate,
    ProductCreate,
    ProductImageCreate,
    TranslationUpsert,
    VariantCreate,
)
from app.services import catalog_admin_service


async def seed() -> None:
    async with async_session_factory() as db:
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
                base_sku="LIP-VELVET",
                base_price="19.99",
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
                    price="19.99",
                    stock_qty=25,
                    attribute_values={"shade": shade},
                ),
            )
        await catalog_admin_service.create_product_image(
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
                base_sku="SERUM-VITC",
                base_price="24.50",
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
            VariantCreate(
                product_id=serum.id, sku="SERUM-VITC-30ML", price="24.50", stock_qty=40
            ),
        )
        await catalog_admin_service.create_product_image(
            db,
            serum.id,
            ProductImageCreate(url="https://picsum.photos/seed/serum/600/600", position=0),
        )

    print("Seed complete: 2 categories, 2 products, 4 variants.")


if __name__ == "__main__":
    asyncio.run(seed())
