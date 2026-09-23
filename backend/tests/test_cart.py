from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.enums import ProductStatus
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.variant import Variant
from tests.factories import make_init_data


def _auth_headers(telegram_id: int) -> dict[str, str]:
    return {"Authorization": f"tma {make_init_data(telegram_id=telegram_id)}"}


async def _make_variant(db_session: AsyncSession, *, sku: str, price: str, stock: int) -> Variant:
    category = Category(slug=f"cat-{sku}", sort_order=0)
    db_session.add(category)
    await db_session.flush()
    product = Product(
        category_id=category.id,
        base_sku=f"PROD-{sku}",
        base_price=Decimal(price),
        status=ProductStatus.active,
    )
    db_session.add(product)
    await db_session.flush()
    variant = Variant(product_id=product.id, sku=sku, price=Decimal(price), stock_qty=stock)
    db_session.add(variant)
    await db_session.commit()
    await db_session.refresh(variant)
    return variant


async def test_add_item_creates_cart_and_item(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    variant = await _make_variant(db_session, sku="V1", price="10.00", stock=5)

    response = await client.post(
        "/cart/items",
        json={"variant_id": variant.id, "qty": 2},
        headers=_auth_headers(2001),
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["qty"] == 2
    assert body["subtotal"] == "20.00"


async def test_adding_same_variant_twice_increments_qty(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    variant = await _make_variant(db_session, sku="V2", price="5.00", stock=10)
    headers = _auth_headers(2002)

    await client.post("/cart/items", json={"variant_id": variant.id, "qty": 2}, headers=headers)
    response = await client.post(
        "/cart/items", json={"variant_id": variant.id, "qty": 3}, headers=headers
    )

    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["qty"] == 5


async def test_update_qty_to_zero_removes_item(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    variant = await _make_variant(db_session, sku="V3", price="7.50", stock=10)
    headers = _auth_headers(2003)

    add_resp = await client.post(
        "/cart/items", json={"variant_id": variant.id, "qty": 1}, headers=headers
    )
    item_id = add_resp.json()["items"][0]["id"]

    response = await client.patch(f"/cart/items/{item_id}", json={"qty": 0}, headers=headers)
    assert response.json()["items"] == []


async def test_cart_isolated_per_telegram_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    variant = await _make_variant(db_session, sku="V4", price="3.00", stock=10)

    await client.post(
        "/cart/items", json={"variant_id": variant.id, "qty": 1}, headers=_auth_headers(2004)
    )
    response = await client.get("/cart/items", headers=_auth_headers(2005))
    assert response.json()["items"] == []


async def test_insufficient_stock_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    variant = await _make_variant(db_session, sku="V5", price="3.00", stock=1)

    response = await client.post(
        "/cart/items", json={"variant_id": variant.id, "qty": 5}, headers=_auth_headers(2006)
    )
    assert response.status_code == 409


async def test_nonexistent_variant_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/cart/items", json={"variant_id": 999999, "qty": 1}, headers=_auth_headers(2007)
    )
    assert response.status_code == 404


async def test_cart_item_prefers_variant_image_over_product_image(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    variant = await _make_variant(db_session, sku="V6", price="9.00", stock=5)
    db_session.add_all(
        [
            ProductImage(
                product_id=variant.product_id, variant_id=None, url="https://example.com/p.jpg"
            ),
            ProductImage(
                product_id=variant.product_id,
                variant_id=variant.id,
                url="https://example.com/v.jpg",
            ),
        ]
    )
    await db_session.commit()

    response = await client.post(
        "/cart/items", json={"variant_id": variant.id, "qty": 1}, headers=_auth_headers(2008)
    )
    assert response.json()["items"][0]["thumbnail_url"] == "https://example.com/v.jpg"
