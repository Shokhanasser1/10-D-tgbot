"""Spec 9 §4: a seller account signs in like any admin, knows its seller, and stops working
the moment that seller is deactivated."""

from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.internal_auth import login_limiter
from app.models.enums import AdminRole
from app.services import admin_service
from tests.admin_factories import add_admin, admin_tma, login_payload
from tests.factories import add_seller

PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def _reset_login_limiter() -> Iterator[None]:
    login_limiter.reset()
    yield
    login_limiter.reset()


async def test_me_names_the_seller(client: AsyncClient, db_session: AsyncSession) -> None:
    seller = await add_seller(db_session, "Lola Beauty")
    await add_admin(db_session, 840_001, AdminRole.seller, seller_id=seller.id)

    me = (await client.get("/internal/me", headers=admin_tma(840_001))).json()

    assert (me["role"], me["seller_id"], me["seller_name"]) == ("seller", seller.id, "Lola Beauty")


async def test_staff_have_no_seller(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_admin(db_session, 840_002, AdminRole.manager)

    me = (await client.get("/internal/me", headers=admin_tma(840_002))).json()

    assert (me["seller_id"], me["seller_name"]) == (None, None)


async def _closed_seller_account(db: AsyncSession, telegram_id: int) -> None:
    seller = await add_seller(db, "Closed shop", is_active=False)
    await add_admin(db, telegram_id, AdminRole.seller, seller_id=seller.id)


async def test_a_deactivated_sellers_account_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _closed_seller_account(db_session, 840_003)

    response = await client.get("/internal/me", headers=admin_tma(840_003))

    assert response.status_code == 403
    assert response.json()["code"] == "seller_inactive"


async def test_a_deactivated_seller_cannot_sign_in_with_a_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _closed_seller_account(db_session, 840_004)
    await admin_service.set_password_from_terminal(db_session, 840_004, "closedshop", PASSWORD)

    response = await client.post(
        "/internal/auth/password", json={"login": "closedshop", "password": PASSWORD}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "seller_inactive"
    assert "admin_session" not in response.cookies


async def test_a_deactivated_seller_cannot_sign_in_with_telegram(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _closed_seller_account(db_session, 840_005)

    response = await client.post("/internal/auth/telegram", json=login_payload(840_005))

    assert response.status_code == 403
    assert response.json()["code"] == "seller_inactive"
    assert "admin_session" not in response.cookies
