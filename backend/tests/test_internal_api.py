from httpx import AsyncClient

INTERNAL_HEADERS = {"X-Internal-Token": "test-internal-token"}


async def test_missing_internal_token_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/internal/categories", json={"slug": "skincare"})
    assert response.status_code == 403


async def test_wrong_internal_token_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/categories",
        json={"slug": "skincare"},
        headers={"X-Internal-Token": "wrong-token"},
    )
    assert response.status_code == 403


async def test_create_full_catalog_entity_chain(client: AsyncClient) -> None:
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


async def test_create_product_with_nonexistent_category_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/products",
        json={"category_id": 999999, "base_sku": "X-1", "base_price": "1.00"},
        headers=INTERNAL_HEADERS,
    )
    assert response.status_code == 400


async def test_update_nonexistent_product_returns_404(client: AsyncClient) -> None:
    response = await client.patch(
        "/internal/products/999999", json={"base_price": "9.99"}, headers=INTERNAL_HEADERS
    )
    assert response.status_code == 404
