from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.enums import ProductStatus
from app.models.product import Product
from app.models.translation import Translation
from app.models.variant import Variant
from tests.factories import make_init_data


def _auth_headers(telegram_id: int) -> dict[str, str]:
    return {"Authorization": f"tma {make_init_data(telegram_id=telegram_id)}"}


async def test_list_products_only_returns_active(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    category = Category(slug="serums", sort_order=0)
    db_session.add(category)
    await db_session.flush()

    active = Product(
        category_id=category.id,
        base_sku="SER-ACTIVE",
        base_price=Decimal("10.00"),
        status=ProductStatus.active,
    )
    draft = Product(
        category_id=category.id,
        base_sku="SER-DRAFT",
        base_price=Decimal("10.00"),
        status=ProductStatus.draft,
    )
    db_session.add_all([active, draft])
    await db_session.commit()

    response = await client.get("/catalog/products", headers=_auth_headers(1001))
    assert response.status_code == 200
    skus = {item["base_sku"] for item in response.json()}
    assert "SER-ACTIVE" in skus
    assert "SER-DRAFT" not in skus


async def test_list_products_filters_by_category(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    cat_a = Category(slug="cat-a", sort_order=0)
    cat_b = Category(slug="cat-b", sort_order=1)
    db_session.add_all([cat_a, cat_b])
    await db_session.flush()

    prod_a = Product(
        category_id=cat_a.id,
        base_sku="A-1",
        base_price=Decimal("5.00"),
        status=ProductStatus.active,
    )
    prod_b = Product(
        category_id=cat_b.id,
        base_sku="B-1",
        base_price=Decimal("5.00"),
        status=ProductStatus.active,
    )
    db_session.add_all([prod_a, prod_b])
    await db_session.commit()

    response = await client.get(
        "/catalog/products", params={"category": cat_a.id}, headers=_auth_headers(1002)
    )
    skus = {item["base_sku"] for item in response.json()}
    assert skus == {"A-1"}


async def test_locale_falls_back_to_default_when_translation_missing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    category = Category(slug="toner", sort_order=0)
    db_session.add(category)
    await db_session.flush()

    product = Product(
        category_id=category.id,
        base_sku="TONER-1",
        base_price=Decimal("8.00"),
        status=ProductStatus.active,
    )
    db_session.add(product)
    await db_session.flush()

    db_session.add(
        Translation(
            entity_type="product",
            entity_id=product.id,
            locale="en",
            field="name",
            value="Toner",
        )
    )
    await db_session.commit()

    response = await client.get(
        "/catalog/products", params={"locale": "uz"}, headers=_auth_headers(1003)
    )
    item = next(i for i in response.json() if i["base_sku"] == "TONER-1")
    assert item["name"] == "Toner"


async def test_get_product_detail_includes_variants_and_translated_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    category = Category(slug="lip-gloss", sort_order=0)
    db_session.add(category)
    await db_session.flush()

    product = Product(
        category_id=category.id,
        base_sku="GLOSS-1",
        base_price=Decimal("12.00"),
        status=ProductStatus.active,
    )
    db_session.add(product)
    await db_session.flush()

    db_session.add(
        Variant(
            product_id=product.id,
            sku="GLOSS-1-PINK",
            price=Decimal("12.00"),
            stock_qty=3,
            attribute_values={"shade": "pink"},
        )
    )
    db_session.add(
        Translation(
            entity_type="product", entity_id=product.id, locale="ru", field="name", value="Блеск"
        )
    )
    await db_session.commit()

    response = await client.get(
        f"/catalog/products/{product.id}", params={"locale": "ru"}, headers=_auth_headers(1004)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Блеск"
    assert len(body["variants"]) == 1
    assert body["variants"][0]["attribute_values"] == {"shade": "pink"}


async def test_get_nonexistent_product_returns_404(client: AsyncClient) -> None:
    response = await client.get("/catalog/products/999999", headers=_auth_headers(1005))
    assert response.status_code == 404
