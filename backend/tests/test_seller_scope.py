"""Spec 9 §4: a seller reaches only their own products, variants, photos and product texts.
Another seller's rows answer 404 (not 403, so ids cannot be probed); categories and attributes
are platform data, readable but not writable."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Product, ProductImage, Variant
from app.models.enums import AdminRole, ProductStatus
from tests.admin_factories import add_admin, admin_tma
from tests.courier_factories import INTERNAL_HEADERS
from tests.factories import add_seller

SELLER_TID = 850_001

Shop = dict[str, int]


async def _shop(db: AsyncSession, name: str, category_id: int) -> Shop:
    seller = await add_seller(db, name)
    product = Product(
        category_id=category_id,
        seller_id=seller.id,
        base_sku=f"SCOPE-{name}",
        base_price=Decimal("10.00"),
        status=ProductStatus.active,
    )
    db.add(product)
    await db.flush()
    variant = Variant(
        product_id=product.id, sku=f"SCOPE-{name}-V", price=Decimal("10.00"), stock_qty=5
    )
    image = ProductImage(product_id=product.id, url=f"https://img.test/{name}.webp", position=0)
    db.add_all([variant, image])
    await db.flush()
    return {"seller": seller.id, "product": product.id, "variant": variant.id, "image": image.id}


@pytest.fixture
async def shops(db_session: AsyncSession) -> tuple[Shop, Shop, int]:
    category = Category(slug="scope-cat", sort_order=0)
    db_session.add(category)
    await db_session.flush()
    mine = await _shop(db_session, "MINE", category.id)
    other = await _shop(db_session, "OTHER", category.id)
    await add_admin(db_session, SELLER_TID, AdminRole.seller, seller_id=mine["seller"])
    await db_session.commit()
    return mine, other, category.id


def as_seller() -> dict[str, str]:
    return admin_tma(SELLER_TID)


# Every catalog write or read that names one product (directly or through a variant, a photo or
# a product text), as (method, path, body), built for a given shop.
def _requests(shop: Shop) -> list[tuple[str, str, dict | None]]:
    return [
        ("GET", f"/internal/products/{shop['product']}", None),
        ("PATCH", f"/internal/products/{shop['product']}", {"base_price": "12.00"}),
        (
            "POST",
            "/internal/variants",
            {"product_id": shop["product"], "sku": f"NEW-{shop['product']}", "price": "1.00"},
        ),  # noqa: E501
        ("PATCH", f"/internal/variants/{shop['variant']}", {"price": "11.00"}),
        (
            "POST",
            f"/internal/products/{shop['product']}/images",
            {"url": "https://img.test/new.webp"},
        ),  # noqa: E501
        ("PATCH", f"/internal/images/{shop['image']}", {"position": 3}),
        ("DELETE", f"/internal/images/{shop['image']}", None),
        (
            "POST",
            "/internal/translations",
            {
                "entity_type": "product",
                "entity_id": shop["product"],
                "locale": "en",
                "field": "name",
                "value": "Renamed",
            },
        ),
    ]


REQUEST_NAMES = [
    "get product",
    "patch product",
    "add variant",
    "patch variant",
    "add image",
    "patch image",
    "delete image",
    "translate product",
]


@pytest.mark.parametrize("index", range(len(REQUEST_NAMES)), ids=REQUEST_NAMES)
async def test_another_sellers_product_is_not_found(
    client: AsyncClient, db_session: AsyncSession, shops: tuple[Shop, Shop, int], index: int
) -> None:
    _, other, _ = shops
    method, path, body = _requests(other)[index]

    response = await client.request(method, path, json=body, headers=as_seller())

    assert response.status_code == 404, response.text
    # Nothing of theirs changed.
    variant = await db_session.get(Variant, other["variant"], populate_existing=True)
    image = await db_session.get(ProductImage, other["image"], populate_existing=True)
    assert variant is not None and variant.price == Decimal("10.00")
    assert image is not None and image.position == 0


@pytest.mark.parametrize("index", range(len(REQUEST_NAMES)), ids=REQUEST_NAMES)
async def test_own_products_work(
    client: AsyncClient, shops: tuple[Shop, Shop, int], index: int
) -> None:
    mine, _, _ = shops
    method, path, body = _requests(mine)[index]

    response = await client.request(method, path, json=body, headers=as_seller())

    assert response.status_code < 300, response.text


async def test_the_list_shows_only_own_products(
    client: AsyncClient, shops: tuple[Shop, Shop, int]
) -> None:
    mine, other, _ = shops

    for params in ({}, {"seller_id": other["seller"]}):
        page = (await client.get("/internal/products", params=params, headers=as_seller())).json()
        assert [item["id"] for item in page["items"]] == [mine["product"]]
        assert page["total"] == 1


async def test_list_and_detail_name_the_seller(
    client: AsyncClient, shops: tuple[Shop, Shop, int]
) -> None:
    mine, _, _ = shops

    (item,) = (await client.get("/internal/products", headers=as_seller())).json()["items"]
    detail = (await client.get(f"/internal/products/{mine['product']}", headers=as_seller())).json()

    assert (item["seller_id"], item["seller_name"]) == (mine["seller"], "MINE")
    assert (detail["seller_id"], detail["seller_name"]) == (mine["seller"], "MINE")


async def test_a_seller_reads_but_does_not_change_platform_data(
    client: AsyncClient, shops: tuple[Shop, Shop, int]
) -> None:
    _, _, category_id = shops

    assert (await client.get("/internal/categories", headers=as_seller())).status_code == 200
    assert (await client.get("/internal/attributes", headers=as_seller())).status_code == 200
    writes = [
        ("POST", "/internal/categories", {"slug": "seller-made", "sort_order": 0}),
        ("PATCH", f"/internal/categories/{category_id}", {"sort_order": 9}),
        (
            "POST",
            "/internal/attributes",
            {"key": "x", "category_id": category_id, "value_type": "text"},
        ),  # noqa: E501
        (
            "POST",
            "/internal/translations",
            {
                "entity_type": "category",
                "entity_id": category_id,
                "locale": "en",
                "field": "name",
                "value": "Mine now",
            },
        ),
    ]
    for method, path, body in writes:
        response = await client.request(method, path, json=body, headers=as_seller())
        assert response.status_code == 403, (path, response.text)


async def test_new_products_go_to_the_sellers_own_shop(
    client: AsyncClient, shops: tuple[Shop, Shop, int]
) -> None:
    mine, other, category_id = shops
    body = {"category_id": category_id, "base_sku": "SELLER-NEW", "base_price": "5.00"}

    created = await client.post("/internal/products", json=body, headers=as_seller())
    elsewhere = await client.post(
        "/internal/products",
        json={**body, "base_sku": "SELLER-NEW-2", "seller_id": other["seller"]},
        headers=as_seller(),
    )

    assert created.status_code == 201
    assert created.json()["seller_id"] == mine["seller"]
    assert elsewhere.status_code == 404


async def test_a_seller_cannot_move_a_product_to_another_shop(
    client: AsyncClient, db_session: AsyncSession, shops: tuple[Shop, Shop, int]
) -> None:
    mine, other, _ = shops

    response = await client.patch(
        f"/internal/products/{mine['product']}",
        json={"seller_id": other["seller"]},
        headers=as_seller(),
    )

    assert response.status_code == 403
    product = await db_session.get(Product, mine["product"], populate_existing=True)
    assert product is not None and product.seller_id == mine["seller"]


# --- platform staff --------------------------------------------------------------------------


async def test_staff_name_the_seller_of_a_new_product(
    client: AsyncClient, db_session: AsyncSession, shops: tuple[Shop, Shop, int]
) -> None:
    _, other, category_id = shops
    body = {"category_id": category_id, "base_sku": "STAFF-NEW", "base_price": "5.00"}

    without = await client.post("/internal/products", json=body, headers=INTERNAL_HEADERS)
    unknown = await client.post(
        "/internal/products", json={**body, "seller_id": 999_999}, headers=INTERNAL_HEADERS
    )
    named = await client.post(
        "/internal/products", json={**body, "seller_id": other["seller"]}, headers=INTERNAL_HEADERS
    )

    assert without.status_code == 400
    assert unknown.status_code == 404
    assert named.status_code == 201 and named.json()["seller_id"] == other["seller"]


async def test_staff_move_products_and_filter_by_seller(
    client: AsyncClient, shops: tuple[Shop, Shop, int]
) -> None:
    mine, other, _ = shops

    moved = await client.patch(
        f"/internal/products/{mine['product']}",
        json={"seller_id": other["seller"]},
        headers=INTERNAL_HEADERS,
    )
    page = (
        await client.get(
            "/internal/products", params={"seller_id": other["seller"]}, headers=INTERNAL_HEADERS
        )
    ).json()

    assert moved.status_code == 200 and moved.json()["seller_id"] == other["seller"]
    assert sorted(item["id"] for item in page["items"]) == sorted(
        [mine["product"], other["product"]]
    )


async def test_staff_reach_every_sellers_products(
    client: AsyncClient, db_session: AsyncSession, shops: tuple[Shop, Shop, int]
) -> None:
    manager_tid = 850_002
    await add_admin(db_session, manager_tid, AdminRole.catalog_manager)
    _, other, _ = shops

    response = await client.patch(
        f"/internal/variants/{other['variant']}",
        json={"price": "11.00"},
        headers=admin_tma(manager_tid),
    )

    assert response.status_code == 200
