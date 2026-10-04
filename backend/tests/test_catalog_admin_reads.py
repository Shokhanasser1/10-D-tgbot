from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attribute import Attribute
from app.models.category import Category
from app.models.enums import AdminRole, AttributeValueType, ProductStatus
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.translation import Translation
from app.models.variant import Variant
from tests.admin_factories import add_admin, admin_tma
from tests.courier_factories import INTERNAL_HEADERS
from tests.factories import default_seller_id


async def _catalog(db: AsyncSession, prefix: str) -> dict[str, int]:
    category = Category(slug=f"{prefix}-lips", sort_order=1)
    db.add(category)
    await db.flush()
    lipstick = Product(
        seller_id=await default_seller_id(db),
        category_id=category.id,
        base_sku=f"{prefix}-LIP",
        base_price=Decimal("20.00"),
        status=ProductStatus.active,
    )
    draft = Product(
        seller_id=await default_seller_id(db),
        category_id=category.id,
        base_sku=f"{prefix}-GLOSS",
        base_price=Decimal("9.00"),
        status=ProductStatus.draft,
    )
    db.add_all([lipstick, draft])
    await db.flush()
    red = Variant(
        product_id=lipstick.id, sku=f"{prefix}-LIP-RED", price=Decimal("21.00"), stock_qty=3
    )
    nude = Variant(
        product_id=lipstick.id, sku=f"{prefix}-LIP-NUDE", price=Decimal("19.50"), stock_qty=4
    )
    attribute = Attribute(key="shade", category_id=category.id, value_type=AttributeValueType.text)
    db.add_all([red, nude, attribute])
    await db.flush()
    db.add_all(
        [
            ProductImage(product_id=lipstick.id, variant_id=red.id, url="/v.webp", position=0),
            ProductImage(product_id=lipstick.id, url="/second.webp", position=2),
            ProductImage(product_id=lipstick.id, url="/first.webp", position=1),
            Translation(
                entity_type="product",
                entity_id=lipstick.id,
                locale="en",
                field="name",
                value="Velvet Lipstick",
            ),
            Translation(
                entity_type="product",
                entity_id=lipstick.id,
                locale="ru",
                field="name",
                value="Бархатная помада",
            ),
            Translation(
                entity_type="product",
                entity_id=lipstick.id,
                locale="ru",
                field="description",
                value="Матовая",
            ),
            Translation(
                entity_type="category",
                entity_id=category.id,
                locale="ru",
                field="name",
                value="Губы",
            ),
            Translation(
                entity_type="attribute",
                entity_id=attribute.id,
                locale="en",
                field="name",
                value="Shade",
            ),
        ]
    )
    await db.commit()
    return {
        "category": category.id,
        "lipstick": lipstick.id,
        "draft": draft.id,
        "attribute": attribute.id,
        "red": red.id,
    }


async def test_list_categories_includes_all_translations(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ids = await _catalog(db_session, "rc1")

    response = await client.get("/internal/categories?locale=ru", headers=INTERNAL_HEADERS)

    assert response.status_code == 200
    item = next(c for c in response.json() if c["id"] == ids["category"])
    assert item["name"] == "Губы"
    assert item["translations"] == {"ru": {"name": "Губы"}}


async def test_category_name_falls_back_to_slug(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ids = await _catalog(db_session, "rc2")

    response = await client.get("/internal/categories?locale=xx", headers=INTERNAL_HEADERS)

    item = next(c for c in response.json() if c["id"] == ids["category"])
    assert item["name"] == "rc2-lips"


async def test_list_attributes(client: AsyncClient, db_session: AsyncSession) -> None:
    ids = await _catalog(db_session, "ra1")

    response = await client.get("/internal/attributes", headers=INTERNAL_HEADERS)

    item = next(a for a in response.json() if a["id"] == ids["attribute"])
    assert item == {
        "id": ids["attribute"],
        "key": "shade",
        "category_id": ids["category"],
        "value_type": "text",
        "translations": {"en": {"name": "Shade"}},
    }


async def test_list_products_includes_every_status_with_stats(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ids = await _catalog(db_session, "rp1")

    response = await client.get(
        f"/internal/products?category_id={ids['category']}", headers=INTERNAL_HEADERS
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    by_id = {p["id"]: p for p in body["items"]}
    assert by_id[ids["lipstick"]] == {
        "id": ids["lipstick"],
        "category_id": ids["category"],
        "seller_id": by_id[ids["lipstick"]]["seller_id"],
        "seller_name": "Test shop",
        "base_sku": "rp1-LIP",
        "base_price": "20.00",
        "status": "active",
        "name": "Velvet Lipstick",
        "thumbnail_url": "/first.webp",
        "variant_count": 2,
        "min_price": "19.50",
        "total_stock": 7,
    }
    assert by_id[ids["draft"]]["variant_count"] == 0
    assert by_id[ids["draft"]]["min_price"] is None
    assert by_id[ids["draft"]]["thumbnail_url"] is None
    assert by_id[ids["draft"]]["name"] == "rp1-GLOSS"


async def test_list_products_filters_by_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ids = await _catalog(db_session, "rp2")

    response = await client.get(
        f"/internal/products?category_id={ids['category']}&status=draft", headers=INTERNAL_HEADERS
    )

    assert [p["id"] for p in response.json()["items"]] == [ids["draft"]]


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("бархат", "lipstick"),  # a translated name, any language
        ("rp3-lip-nude", "lipstick"),  # a variant SKU, case-insensitive
        ("rp3-GLO", "draft"),  # the base SKU
    ],
)
async def test_search_products(
    client: AsyncClient, db_session: AsyncSession, q: str, expected: str
) -> None:
    ids = await _catalog(db_session, "rp3")

    response = await client.get(
        "/internal/products",
        params={"q": q, "category_id": ids["category"]},
        headers=INTERNAL_HEADERS,
    )

    assert [p["id"] for p in response.json()["items"]] == [ids[expected]]


async def test_search_treats_like_wildcards_literally(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ids = await _catalog(db_session, "rp4")

    response = await client.get(
        "/internal/products",
        params={"q": "%", "category_id": ids["category"]},
        headers=INTERNAL_HEADERS,
    )

    assert response.json() == {"items": [], "total": 0}


async def test_products_are_paginated(client: AsyncClient, db_session: AsyncSession) -> None:
    ids = await _catalog(db_session, "rp5")
    base = f"/internal/products?category_id={ids['category']}&limit=1"

    first = (await client.get(base, headers=INTERNAL_HEADERS)).json()
    second = (await client.get(f"{base}&offset=1", headers=INTERNAL_HEADERS)).json()

    assert first["total"] == second["total"] == 2
    assert [p["id"] for p in first["items"]] == [ids["draft"]]  # newest first
    assert [p["id"] for p in second["items"]] == [ids["lipstick"]]


async def test_product_detail_has_everything_the_editor_needs(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ids = await _catalog(db_session, "rd1")

    response = await client.get(
        f"/internal/products/{ids['lipstick']}?locale=ru", headers=INTERNAL_HEADERS
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Бархатная помада"
    assert body["status"] == "active"
    assert body["translations"] == {
        "en": {"name": "Velvet Lipstick"},
        "ru": {"name": "Бархатная помада", "description": "Матовая"},
    }
    assert [v["sku"] for v in body["variants"]] == ["rd1-LIP-RED", "rd1-LIP-NUDE"]
    assert [i["url"] for i in body["images"]] == ["/v.webp", "/first.webp", "/second.webp"]
    assert body["images"][0]["variant_id"] == ids["red"]


async def test_unknown_product_is_404(client: AsyncClient) -> None:
    response = await client.get("/internal/products/999999", headers=INTERNAL_HEADERS)
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (AdminRole.owner, 200),
        (AdminRole.catalog_manager, 200),
        (AdminRole.dispatcher, 403),
    ],
)
async def test_catalog_reads_are_for_catalog_roles(
    client: AsyncClient, db_session: AsyncSession, role: AdminRole, expected: int
) -> None:
    telegram_id = 720_000 + list(AdminRole).index(role)
    await add_admin(db_session, telegram_id, role)

    for path in ("/internal/categories", "/internal/attributes", "/internal/products"):
        response = await client.get(path, headers=admin_tma(telegram_id))
        assert response.status_code == expected, path
