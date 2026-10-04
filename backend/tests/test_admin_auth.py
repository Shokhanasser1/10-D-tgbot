import time
from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.internal_auth import login_limiter
from app.config import get_settings
from app.core.admin_session import sign_session, verify_session
from app.models.admin import Admin
from app.models.enums import AdminRole
from app.services import admin_service
from tests.admin_factories import (
    SESSION_SECRET,
    add_admin,
    admin_cookie,
    admin_tma,
    login_payload,
)
from tests.courier_factories import INTERNAL_HEADERS

settings = get_settings()


@pytest.fixture(autouse=True)
def _reset_login_limiter() -> Iterator[None]:
    login_limiter.reset()
    yield
    login_limiter.reset()


# --- session tokens -------------------------------------------------------------------------


def test_session_round_trip() -> None:
    assert verify_session(sign_session(42, "s"), "s", 60) == 42


@pytest.mark.parametrize(
    "value",
    ["", "42", "42.1", "x.1.abc", "42.x.abc", "42.1.deadbeef"],
)
def test_malformed_or_forged_session_is_rejected(value: str) -> None:
    assert verify_session(value, "s", 60) is None


def test_session_signed_with_another_secret_is_rejected() -> None:
    assert verify_session(sign_session(42, "other"), "s", 60) is None


def test_expired_session_is_rejected() -> None:
    assert verify_session(sign_session(42, "s", now=time.time() - 120), "s", 60) is None


def test_tampered_session_id_is_rejected() -> None:
    _, version, issued, sig = sign_session(42, "s").split(".")
    assert verify_session(f"43.{version}.{issued}.{sig}", "s", 60) is None


def test_a_confirmation_cookie_is_not_a_session() -> None:
    from app.core import admin_session

    confirm = admin_session.sign(42, 1, "s", kind=admin_session.CONFIRM)
    assert verify_session(confirm, "s", 60) is None


def test_an_old_three_part_session_is_rejected() -> None:
    assert verify_session("42.1790000000.deadbeef", "s", 60) is None


def test_no_secret_means_no_sessions() -> None:
    assert verify_session(sign_session(42, ""), "", 60) is None


# --- browser login --------------------------------------------------------------------------


async def test_login_sets_session_cookie_for_an_active_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_admin(db_session, 700_001, AdminRole.dispatcher, display_name="Dilnoza")

    response = await client.post("/internal/auth/telegram", json=login_payload(700_001))

    assert response.status_code == 200
    assert response.json() | {"permissions": None} == {
        "telegram_id": 700_001,
        "display_name": "Dilnoza",
        "role": "dispatcher",
        "permissions": None,
        "login": None,
        "has_password": False,
        "must_change_password": False,
        "seller_id": None,
        "seller_name": None,
    }
    assert "orders.cancel_paid" not in response.json()["permissions"]
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("admin_session=")
    for attribute in ("HttpOnly", "Secure", "SameSite=strict", "Path=/", "Max-Age=43200"):
        assert attribute in cookie
    value = cookie.split(";")[0].removeprefix("admin_session=")
    assert verify_session(value, SESSION_SECRET, 60) == 700_001


async def test_login_with_forged_hash_is_401(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_admin(db_session, 700_002)
    payload = login_payload(700_002)
    payload["id"] = 700_003  # hash no longer matches

    response = await client.post("/internal/auth/telegram", json=payload)

    assert response.status_code == 401
    assert "set-cookie" not in response.headers


async def test_login_signed_with_another_bot_is_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_admin(db_session, 700_004)
    payload = login_payload(700_004, bot_token="999:other-bot")

    response = await client.post("/internal/auth/telegram", json=payload)

    assert response.status_code == 401


async def test_expired_login_is_401(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_admin(db_session, 700_005)
    payload = login_payload(700_005, auth_date=int(time.time()) - 2 * 86400)

    response = await client.post("/internal/auth/telegram", json=payload)

    assert response.status_code == 401


async def test_login_by_non_admin_is_403(client: AsyncClient) -> None:
    response = await client.post("/internal/auth/telegram", json=login_payload(700_006))

    assert response.status_code == 403
    assert "set-cookie" not in response.headers


async def test_login_by_deactivated_admin_is_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_admin(db_session, 700_007, is_active=False)

    response = await client.post("/internal/auth/telegram", json=login_payload(700_007))

    assert response.status_code == 403


async def test_login_is_rate_limited(client: AsyncClient) -> None:
    statuses = [
        (await client.post("/internal/auth/telegram", json=login_payload(700_008))).status_code
        for _ in range(settings.admin_login_rate_limit_per_minute + 1)
    ]

    assert statuses[-1] == 429
    assert set(statuses[:-1]) == {403}


async def test_login_without_session_secret_is_503(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await add_admin(db_session, 700_009)
    monkeypatch.setattr(settings, "admin_session_secret", "")

    response = await client.post("/internal/auth/telegram", json=login_payload(700_009))

    assert response.status_code == 503


async def test_logout_clears_the_cookie(client: AsyncClient) -> None:
    response = await client.post("/internal/auth/logout")

    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert cookie.startswith('admin_session=""') and "Max-Age=0" in cookie


# --- resolving the caller -------------------------------------------------------------------


async def test_me_with_mini_app_init_data(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_admin(db_session, 700_010, AdminRole.catalog_manager, display_name="Kamola")

    response = await client.get("/internal/me", headers=admin_tma(700_010))

    assert response.status_code == 200
    body = response.json()
    assert (body["telegram_id"], body["display_name"], body["role"]) == (
        700_010,
        "Kamola",
        "catalog_manager",
    )
    assert body["permissions"] == ["catalog.edit", "catalog.view", "taxonomy.edit"]


async def test_me_with_session_cookie(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_admin(db_session, 700_011)

    response = await client.get("/internal/me", headers=admin_cookie(700_011, csrf=False))

    assert response.status_code == 200
    assert response.json()["role"] == "owner"


async def test_me_with_internal_token_is_an_owner(client: AsyncClient) -> None:
    response = await client.get("/internal/me", headers=INTERNAL_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert (body["telegram_id"], body["display_name"], body["role"]) == (None, "Internal", "owner")
    assert "admins.manage" in body["permissions"]


async def test_no_credentials_is_401(client: AsyncClient) -> None:
    assert (await client.get("/internal/me")).status_code == 401


async def test_wrong_internal_token_is_403(client: AsyncClient) -> None:
    response = await client.get("/internal/me", headers={"X-Internal-Token": "nope"})
    assert response.status_code == 403


async def test_invalid_init_data_is_401(client: AsyncClient) -> None:
    response = await client.get("/internal/me", headers={"Authorization": "tma hash=forged"})
    assert response.status_code == 401


async def test_expired_session_cookie_is_401(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_admin(db_session, 700_012)
    headers = admin_cookie(700_012, issued_at=time.time() - 13 * 3600)

    assert (await client.get("/internal/me", headers=headers)).status_code == 401


async def test_mini_app_user_who_is_not_an_admin_is_403(client: AsyncClient) -> None:
    response = await client.get("/internal/me", headers=admin_tma(700_013))
    assert response.status_code == 403


async def test_deactivation_ends_an_existing_session_at_once(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await add_admin(db_session, 700_014, AdminRole.dispatcher)
    headers = admin_cookie(700_014)
    assert (await client.get("/internal/me", headers=headers)).status_code == 200

    admin.is_active = False
    await db_session.commit()

    assert (await client.get("/internal/me", headers=headers)).status_code == 403


async def test_role_change_applies_to_an_existing_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await add_admin(db_session, 700_015, AdminRole.catalog_manager)
    headers = admin_cookie(700_015)
    assert (await client.get("/internal/couriers", headers=headers)).status_code == 403

    admin.role = AdminRole.dispatcher
    await db_session.commit()

    assert (await client.get("/internal/couriers", headers=headers)).status_code == 200


async def test_cookie_mutation_without_csrf_header_is_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_admin(db_session, 700_016)

    response = await client.post(
        "/internal/categories",
        json={"slug": "csrf-probe"},
        headers=admin_cookie(700_016, csrf=False),
    )

    assert response.status_code == 403


async def test_cookie_mutation_with_csrf_header_succeeds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_admin(db_session, 700_017)

    response = await client.post(
        "/internal/categories", json={"slug": "csrf-ok"}, headers=admin_cookie(700_017)
    )

    assert response.status_code == 201


async def test_init_data_mutation_needs_no_csrf_header(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_admin(db_session, 700_018, AdminRole.catalog_manager)

    response = await client.post(
        "/internal/categories", json={"slug": "tma-ok"}, headers=admin_tma(700_018)
    )

    assert response.status_code == 201


# --- bootstrap ------------------------------------------------------------------------------


async def test_bootstrap_creates_owners_and_never_changes_existing_rows(
    db_session: AsyncSession,
) -> None:
    await add_admin(db_session, 700_020, AdminRole.dispatcher, is_active=False)

    await admin_service.bootstrap_owners(db_session, [700_019, 700_020, 700_019])
    await admin_service.bootstrap_owners(db_session, [700_019])

    rows = {
        a.telegram_id: (a.role, a.is_active)
        for a in (
            await db_session.execute(
                select(Admin)
                .where(Admin.telegram_id.in_([700_019, 700_020]))
                .execution_options(populate_existing=True)
            )
        ).scalars()
    }
    assert rows == {
        700_019: (AdminRole.owner, True),
        700_020: (AdminRole.dispatcher, False),
    }


async def test_bootstrap_with_no_ids_does_nothing(db_session: AsyncSession) -> None:
    await admin_service.bootstrap_owners(db_session, [])
