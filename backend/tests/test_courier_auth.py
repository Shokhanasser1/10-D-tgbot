import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from tests.courier_factories import add_courier, tma_headers


async def test_courier_endpoint_requires_telegram_auth(client: AsyncClient) -> None:
    assert (await client.get("/courier/me")).status_code == 401


async def test_a_customer_who_is_not_a_courier_is_forbidden(client: AsyncClient) -> None:
    response = await client.get("/courier/me", headers=tma_headers(555_001))

    assert response.status_code == 403


async def test_an_inactive_courier_is_forbidden(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, 555_002, is_active=False)

    response = await client.get("/courier/me", headers=tma_headers(555_002))

    assert response.status_code == 403


async def test_an_active_courier_gets_their_profile(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_username", "shopbot")
    monkeypatch.setattr(settings, "max_active_deliveries_per_courier", 4)
    courier = await add_courier(db_session, 555_003, name="Ali")

    response = await client.get("/courier/me", headers=tma_headers(555_003))

    assert response.status_code == 200
    assert response.json() == {
        "id": courier.id,
        "name": "Ali",
        "bot_username": "shopbot",
        "max_active_deliveries": 4,
    }


async def test_bot_username_is_null_when_not_configured(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "telegram_bot_username", "")
    await add_courier(db_session, 555_004)

    response = await client.get("/courier/me", headers=tma_headers(555_004))

    assert response.json()["bot_username"] is None
