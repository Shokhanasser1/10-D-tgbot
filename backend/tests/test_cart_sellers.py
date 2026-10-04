"""Spec 9 §6: a cart holds one seller's products. Adding another seller's product is refused
unless the customer agrees to empty the cart first."""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Product, Variant
from app.models.enums import ProductStatus
from tests.factories import add_seller, make_init_data


def _headers(telegram_id: int) -> dict[str, str]:
    return {"Authorization": f"tma {make_init_data(telegram_id=telegram_id)}"}


async def _variant(db: AsyncSession, seller_id: int, sku: str) -> int:
    category = Category(slug=f"cart-s-{sku}", sort_order=0)
    db.add(category)
    await db.flush()
    product = Product(
        category_id=category.id,
        seller_id=seller_id,
        base_sku=f"P-{sku}",
        base_price=Decimal("10.00"),
        status=ProductStatus.active,
    )
    db.add(product)
    await db.flush()
    variant = Variant(product_id=product.id, sku=sku, price=Decimal("10.00"), stock_qty=9)
    db.add(variant)
    await db.commit()
    return variant.id


async def _add(client: AsyncClient, telegram_id: int, variant_id: int, **extra):
    return await client.post(
        "/cart/items",
        json={"variant_id": variant_id, "qty": 1, **extra},
        headers=_headers(telegram_id),
    )


async def test_another_sellers_product_is_refused_and_the_cart_kept(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    lola = await add_seller(db_session, "Lola")
    anor = await add_seller(db_session, "Anor")
    lolas = await _variant(db_session, lola.id, "CS1-L")
    anors = await _variant(db_session, anor.id, "CS1-A")
    await _add(client, 880_001, lolas)

    refused = await _add(client, 880_001, anors)
    cart = (await client.get("/cart/items", headers=_headers(880_001))).json()

    assert refused.status_code == 409
    assert refused.json()["code"] == "cart_other_seller"
    assert [item["variant_id"] for item in cart["items"]] == [lolas]


async def test_replace_cart_empties_it_for_the_new_seller(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    lola = await add_seller(db_session, "Lola")
    anor = await add_seller(db_session, "Anor")
    await _add(client, 880_002, await _variant(db_session, lola.id, "CS2-L1"))
    await _add(client, 880_002, await _variant(db_session, lola.id, "CS2-L2"))
    anors = await _variant(db_session, anor.id, "CS2-A")

    response = await _add(client, 880_002, anors, replace_cart=True)

    assert response.status_code == 201
    body = response.json()
    assert [item["variant_id"] for item in body["items"]] == [anors]
    assert body["seller"] == {"id": anor.id, "name": "Anor"}


async def test_products_of_the_same_seller_add_up(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    lola = await add_seller(db_session, "Lola")
    first = await _variant(db_session, lola.id, "CS3-1")
    second = await _variant(db_session, lola.id, "CS3-2")
    await _add(client, 880_003, first)

    response = await _add(client, 880_003, second, replace_cart=True)

    assert response.status_code == 201
    assert sorted(item["variant_id"] for item in response.json()["items"]) == [first, second]


async def test_the_cart_names_its_seller(client: AsyncClient, db_session: AsyncSession) -> None:
    lola = await add_seller(db_session, "Lola")
    empty = (await client.get("/cart/items", headers=_headers(880_004))).json()

    filled = (await _add(client, 880_004, await _variant(db_session, lola.id, "CS4"))).json()

    assert empty["seller"] is None
    assert filled["seller"] == {"id": lola.id, "name": "Lola"}


async def test_a_deactivated_sellers_product_cannot_be_added(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    closed = await add_seller(db_session, "Closed", is_active=False)

    response = await _add(client, 880_005, await _variant(db_session, closed.id, "CS5"))

    assert response.status_code == 404
