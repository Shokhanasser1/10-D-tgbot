"""Spec 9 §6: customers see whose product it is, can list one seller's products, and never see
the products of a deactivated seller."""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Product, Variant
from app.models.enums import ProductStatus
from tests.factories import add_seller, make_init_data

HEADERS = {"Authorization": f"tma {make_init_data(telegram_id=870_001)}"}


async def _product(db: AsyncSession, seller_id: int, sku: str) -> int:
    category = Category(slug=f"cs-{sku}", sort_order=0)
    db.add(category)
    await db.flush()
    product = Product(
        category_id=category.id,
        seller_id=seller_id,
        base_sku=sku,
        base_price=Decimal("10.00"),
        status=ProductStatus.active,
    )
    db.add(product)
    await db.flush()
    db.add(Variant(product_id=product.id, sku=f"{sku}-V", price=Decimal("10.00"), stock_qty=3))
    await db.commit()
    return product.id


async def test_list_and_detail_name_the_seller(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    lola = await add_seller(db_session, "Lola Beauty")
    product_id = await _product(db_session, lola.id, "CS-LOLA")

    listed = (await client.get("/catalog/products", headers=HEADERS)).json()
    detail = (await client.get(f"/catalog/products/{product_id}", headers=HEADERS)).json()

    (item,) = [p for p in listed if p["id"] == product_id]
    assert item["seller"] == {"id": lola.id, "name": "Lola Beauty"}
    assert detail["seller"] == {"id": lola.id, "name": "Lola Beauty"}


async def test_the_list_filters_by_seller(client: AsyncClient, db_session: AsyncSession) -> None:
    lola = await add_seller(db_session, "Lola Beauty")
    anor = await add_seller(db_session, "Anor")
    lolas = await _product(db_session, lola.id, "CS-L1")
    await _product(db_session, anor.id, "CS-A1")

    listed = (
        await client.get("/catalog/products", params={"seller": lola.id}, headers=HEADERS)
    ).json()

    assert [p["id"] for p in listed] == [lolas]


async def test_a_deactivated_sellers_products_are_hidden(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    closed = await add_seller(db_session, "Closed", is_active=False)
    product_id = await _product(db_session, closed.id, "CS-CLOSED")

    listed = (await client.get("/catalog/products", headers=HEADERS)).json()
    detail = await client.get(f"/catalog/products/{product_id}", headers=HEADERS)

    assert product_id not in [p["id"] for p in listed]
    assert detail.status_code == 404
