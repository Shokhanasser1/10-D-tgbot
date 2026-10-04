from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import default_seller_id

INTERNAL_HEADERS = {"X-Internal-Token": "test-internal-token"}


async def test_missing_internal_token_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/internal/categories", json={"slug": "skincare"})
    assert response.status_code == 401


async def test_wrong_internal_token_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/categories",
        json={"slug": "skincare"},
        headers={"X-Internal-Token": "wrong-token"},
    )
    assert response.status_code == 403


async def test_create_full_catalog_entity_chain(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    category_resp = await client.post(
        "/internal/categories", json={"slug": "lipstick", "sort_order": 0}, headers=INTERNAL_HEADERS
    )
    assert category_resp.status_code == 201
    category_id = category_resp.json()["id"]

    attribute_resp = await client.post(
        "/internal/attributes",
        json={"key": "shade", "category_id": category_id, "value_type": "text"},
        headers=INTERNAL_HEADERS,
    )
    assert attribute_resp.status_code == 201

    product_resp = await client.post(
        "/internal/products",
        json={
            "category_id": category_id,
            "seller_id": await default_seller_id(db_session),
            "base_sku": "LIP-100",
            "base_price": "19.99",
            "status": "active",
        },
        headers=INTERNAL_HEADERS,
    )
    assert product_resp.status_code == 201
    product_id = product_resp.json()["id"]

    variant_resp = await client.post(
        "/internal/variants",
        json={
            "product_id": product_id,
            "sku": "LIP-100-RED",
            "price": "19.99",
            "stock_qty": 5,
            "attribute_values": {"shade": "red"},
        },
        headers=INTERNAL_HEADERS,
    )
    assert variant_resp.status_code == 201

    image_resp = await client.post(
        f"/internal/products/{product_id}/images",
        json={"url": "https://example.com/lipstick.jpg", "position": 0},
        headers=INTERNAL_HEADERS,
    )
    assert image_resp.status_code == 201

    translation_resp = await client.post(
        "/internal/translations",
        json={
            "entity_type": "product",
            "entity_id": product_id,
            "locale": "ru",
            "field": "name",
            "value": "Помада",
        },
        headers=INTERNAL_HEADERS,
    )
    assert translation_resp.status_code == 201
    assert translation_resp.json()["value"] == "Помада"


async def test_create_product_with_nonexistent_category_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        "/internal/products",
        json={
            "category_id": 999999,
            "seller_id": await default_seller_id(db_session),
            "base_sku": "X-1",
            "base_price": "1.00",
        },
        headers=INTERNAL_HEADERS,
    )
    assert response.status_code == 400


async def test_update_nonexistent_product_returns_404(client: AsyncClient) -> None:
    response = await client.patch(
        "/internal/products/999999", json={"base_price": "9.99"}, headers=INTERNAL_HEADERS
    )
    assert response.status_code == 404


async def test_patch_endpoints_update_existing_entities(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    category = (
        await client.post(
            "/internal/categories", json={"slug": "old-slug"}, headers=INTERNAL_HEADERS
        )
    ).json()
    attribute = (
        await client.post(
            "/internal/attributes",
            json={"key": "shade", "category_id": category["id"], "value_type": "text"},
            headers=INTERNAL_HEADERS,
        )
    ).json()
    product = (
        await client.post(
            "/internal/products",
            json={
                "category_id": category["id"],
                "seller_id": await default_seller_id(db_session),
                "base_sku": "P-1",
                "base_price": "5.00",
            },
            headers=INTERNAL_HEADERS,
        )
    ).json()
    variant = (
        await client.post(
            "/internal/variants",
            json={"product_id": product["id"], "sku": "P-1-A", "price": "5.00", "stock_qty": 1},
            headers=INTERNAL_HEADERS,
        )
    ).json()

    patched_category = await client.patch(
        f"/internal/categories/{category['id']}",
        json={"slug": "new-slug"},
        headers=INTERNAL_HEADERS,
    )
    patched_attribute = await client.patch(
        f"/internal/attributes/{attribute['id']}",
        json={"value_type": "color"},
        headers=INTERNAL_HEADERS,
    )
    patched_product = await client.patch(
        f"/internal/products/{product['id']}",
        json={"status": "active"},
        headers=INTERNAL_HEADERS,
    )
    patched_variant = await client.patch(
        f"/internal/variants/{variant['id']}",
        json={"stock_qty": 42},
        headers=INTERNAL_HEADERS,
    )

    assert patched_category.json()["slug"] == "new-slug"
    assert patched_attribute.json()["value_type"] == "color"
    assert patched_product.json()["status"] == "active"
    assert patched_variant.json()["stock_qty"] == 42


async def test_patch_nonexistent_entities_return_404(client: AsyncClient) -> None:
    for path, body in [
        ("/internal/categories/999999", {"slug": "x"}),
        ("/internal/attributes/999999", {"key": "x"}),
        ("/internal/variants/999999", {"stock_qty": 1}),
    ]:
        response = await client.patch(path, json=body, headers=INTERNAL_HEADERS)
        assert response.status_code == 404, path


async def test_translation_upsert_updates_existing_value(client: AsyncClient) -> None:
    payload = {"entity_type": "product", "entity_id": 1, "locale": "en", "field": "name"}

    first = await client.post(
        "/internal/translations", json={**payload, "value": "Old"}, headers=INTERNAL_HEADERS
    )
    second = await client.post(
        "/internal/translations", json={**payload, "value": "New"}, headers=INTERNAL_HEADERS
    )

    assert first.json()["id"] == second.json()["id"]
    assert second.json()["value"] == "New"


async def test_add_image_to_nonexistent_product_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/products/999999/images",
        json={"url": "https://example.com/x.jpg"},
        headers=INTERNAL_HEADERS,
    )
    assert response.status_code == 404


async def test_non_ascii_internal_token_is_forbidden_not_a_server_error(
    client: AsyncClient,
) -> None:
    # hmac.compare_digest raises TypeError on a non-ASCII str, which used to become a 500.
    response = await client.post(
        "/internal/categories",
        json={"slug": "x"},
        headers={"X-Internal-Token": "t\u00f6k\u00e9n".encode("latin-1")},
    )

    assert response.status_code == 403
