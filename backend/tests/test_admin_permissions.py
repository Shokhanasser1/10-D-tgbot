"""Spec 7: roles, permissions, password sign-in and the password confirmation for 🔒 actions."""

import itertools
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.internal_auth import login_limiter
from app.core import admin_session, passwords
from app.core.permissions import CONFIRMATION_REQUIRED, ROLE_PERMISSIONS
from app.models.admin import Admin
from app.models.enums import AdminRole, PaymentMethod, Permission
from app.models.payment import Payment
from app.services import admin_service, stripe_service
from scripts import set_admin_password
from tests.admin_factories import SESSION_SECRET, add_admin, admin_confirmed, admin_tma
from tests.courier_factories import INTERNAL_HEADERS, add_paid_order

_ids = itertools.count(720_001)
PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def _reset_login_limiter() -> Iterator[None]:
    login_limiter.reset()
    yield
    login_limiter.reset()


async def _admin_with_password(
    db: AsyncSession, role: AdminRole = AdminRole.owner, login: str | None = None
) -> Admin:
    tid = next(_ids)
    await add_admin(db, tid, role)
    return await admin_service.set_password_from_terminal(db, tid, login or f"user{tid}", PASSWORD)


def _cookie_headers(response_cookies: dict[str, str], *, csrf: bool = True) -> dict[str, str]:
    headers = {"Cookie": "; ".join(f"{k}={v}" for k, v in response_cookies.items())}
    if csrf:
        headers["X-Requested-With"] = "admin"
    return headers


# --- the matrix ------------------------------------------------------------------------------


def _no_body(n: int) -> None:
    return None


ENDPOINTS: list[tuple[str, str, object, Permission]] = [
    ("GET", "/internal/stats/summary", _no_body, Permission.summary_view),
    ("GET", "/internal/products", _no_body, Permission.catalog_view),
    (
        "POST",
        "/internal/categories",
        lambda n: {"slug": f"perm-{n}", "sort_order": 0},
        Permission.taxonomy_edit,
    ),
    ("GET", "/internal/orders", _no_body, Permission.orders_view),
    ("GET", "/internal/couriers", _no_body, Permission.couriers_view),
    (
        "POST",
        "/internal/couriers",
        lambda n: {"telegram_id": n, "name": "Ali"},
        Permission.couriers_manage,
    ),
    ("GET", "/internal/admins", _no_body, Permission.admins_manage),
]


@pytest.mark.parametrize("role", list(AdminRole))
@pytest.mark.parametrize(("method", "path", "make_body", "permission"), ENDPOINTS)
async def test_every_role_gets_exactly_its_permissions(
    client: AsyncClient,
    db_session: AsyncSession,
    role: AdminRole,
    method: str,
    path: str,
    make_body,
    permission: Permission,
) -> None:
    tid = next(_ids)
    await add_admin(db_session, tid, role)

    response = await client.request(method, path, json=make_body(tid), headers=admin_confirmed(tid))

    if permission in ROLE_PERMISSIONS[role]:
        assert response.status_code != 403, (role, path, response.text)
    else:
        assert response.status_code == 403, (role, path, response.text)


def test_the_matrix_matches_the_spec() -> None:
    P = Permission
    assert ROLE_PERMISSIONS[AdminRole.viewer] == {
        P.summary_view,
        P.catalog_view,
        P.orders_view,
        P.couriers_view,
    }
    assert P.orders_cancel_paid not in ROLE_PERMISSIONS[AdminRole.dispatcher]
    assert P.refunds_manage not in ROLE_PERMISSIONS[AdminRole.manager]
    assert P.admins_manage not in ROLE_PERMISSIONS[AdminRole.manager]
    assert ROLE_PERMISSIONS[AdminRole.accountant] == {
        P.summary_view,
        P.orders_view,
        P.orders_cancel_paid,
        P.refunds_manage,
        P.payouts_manage,  # Spec 11
    }
    assert CONFIRMATION_REQUIRED == {
        P.orders_cancel_paid,
        P.refunds_manage,
        P.admins_manage,
        P.payouts_manage,
    }
    # Spec 11: sellers' money is the owner's and the accountant's.
    assert P.payouts_manage not in ROLE_PERMISSIONS[AdminRole.manager]
    # Spec 9: categories and attributes are platform data; sellers are managed by the top two.
    assert ROLE_PERMISSIONS[AdminRole.catalog_manager] == {
        P.catalog_view,
        P.catalog_edit,
        P.taxonomy_edit,
    }
    assert {P.taxonomy_edit, P.sellers_manage} <= ROLE_PERMISSIONS[AdminRole.manager]
    assert P.sellers_manage not in ROLE_PERMISSIONS[AdminRole.catalog_manager]
    # Spec 10: sellers prepare their orders; the platform may mark any order ready.
    assert ROLE_PERMISSIONS[AdminRole.seller] == {
        P.catalog_view,
        P.catalog_edit,
        P.orders_prepare,
    }
    assert P.orders_prepare in ROLE_PERMISSIONS[AdminRole.dispatcher]
    assert P.orders_prepare not in ROLE_PERMISSIONS[AdminRole.catalog_manager]


# --- cancelling: paid vs unpaid --------------------------------------------------------------


@pytest.fixture
def no_refunds(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _refund(payment_intent_id: str, idempotency_key: str, metadata: dict):
        from types import SimpleNamespace

        return SimpleNamespace(id="re_x", status="pending")

    monkeypatch.setattr(stripe_service, "create_refund", _refund)


async def _cash_order(db: AsyncSession, customer: int):
    order, _ = await add_paid_order(db, customer_id=customer)
    await db.execute(
        update(Payment)
        .where(Payment.order_id == order.id)
        .values(method=PaymentMethod.cash, status="requires_payment_method")
    )
    await db.commit()
    return order


async def test_a_dispatcher_cancels_a_cash_order_but_not_a_paid_one(
    client: AsyncClient, db_session: AsyncSession, no_refunds
) -> None:
    tid = next(_ids)
    await add_admin(db_session, tid, AdminRole.dispatcher)
    cash = await _cash_order(db_session, 730_001)
    paid, _ = await add_paid_order(db_session, customer_id=730_002)

    ok = await client.post(
        f"/internal/orders/{cash.id}/cancel", json={"reason": "x"}, headers=admin_tma(tid)
    )
    refused = await client.post(
        f"/internal/orders/{paid.id}/cancel", json={"reason": "x"}, headers=admin_confirmed(tid)
    )

    assert ok.status_code == 200, ok.text
    assert refused.status_code == 403


async def test_even_the_owner_confirms_before_refunding(
    client: AsyncClient, db_session: AsyncSession, no_refunds
) -> None:
    owner = await _admin_with_password(db_session)
    paid, _ = await add_paid_order(db_session, customer_id=730_003)

    unconfirmed = await client.post(
        f"/internal/orders/{paid.id}/cancel",
        json={"reason": "x"},
        headers=admin_tma(owner.telegram_id),
    )
    assert unconfirmed.status_code == 403
    assert unconfirmed.json()["code"] == "password_confirmation_required"

    confirmed = await client.post(
        f"/internal/orders/{paid.id}/cancel",
        json={"reason": "x"},
        headers=admin_confirmed(owner.telegram_id, version=owner.session_version),
    )
    assert confirmed.status_code == 200, confirmed.text


async def test_without_a_password_the_admin_is_sent_to_set_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tid = next(_ids)
    await add_admin(db_session, tid)

    response = await client.post(
        "/internal/admins",
        json={"telegram_id": 9, "role": "viewer", "display_name": "V"},
        headers=admin_tma(tid),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "password_not_set"


async def test_the_internal_token_needs_no_confirmation(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/admins",
        json={"telegram_id": 733_001, "role": "viewer", "display_name": "V"},
        headers=INTERNAL_HEADERS,
    )
    assert response.status_code == 201


# --- confirming ------------------------------------------------------------------------------


async def test_confirm_sets_a_short_lived_cookie_that_unlocks_actions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _admin_with_password(db_session)
    headers = {**admin_tma(owner.telegram_id), "X-Requested-With": "admin"}

    wrong = await client.post("/internal/auth/confirm", json={"password": "nope"}, headers=headers)
    assert wrong.status_code == 401

    right = await client.post(
        "/internal/auth/confirm", json={"password": PASSWORD}, headers=headers
    )
    assert right.status_code == 204
    cookie = right.headers["set-cookie"]
    assert cookie.startswith("admin_confirm=") and "Max-Age=900" in cookie
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie

    value = cookie.split(";")[0].removeprefix("admin_confirm=")
    response = await client.post(
        "/internal/admins",
        json={"telegram_id": 733_002, "role": "viewer", "display_name": "V"},
        headers={**headers, "Cookie": f"admin_confirm={value}"},
    )
    assert response.status_code == 201, response.text


async def test_confirm_needs_the_csrf_header(client: AsyncClient, db_session: AsyncSession) -> None:
    owner = await _admin_with_password(db_session)

    response = await client.post(
        "/internal/auth/confirm", json={"password": PASSWORD}, headers=admin_tma(owner.telegram_id)
    )

    assert response.status_code == 403


async def test_an_expired_or_foreign_confirmation_does_not_count(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _admin_with_password(db_session)
    other = await _admin_with_password(db_session)
    old = admin_session.sign(
        owner.telegram_id,
        owner.session_version,
        SESSION_SECRET,
        kind=admin_session.CONFIRM,
        now=time.time() - 16 * 60,
    )
    foreign = admin_session.sign(
        other.telegram_id, other.session_version, SESSION_SECRET, kind=admin_session.CONFIRM
    )
    body = {"telegram_id": 733_003, "role": "viewer", "display_name": "V"}

    for value in (old, foreign):
        response = await client.post(
            "/internal/admins",
            json=body,
            headers={
                **admin_tma(owner.telegram_id),
                "Cookie": f"admin_confirm={value}",
                "X-Requested-With": "admin",
            },
        )
        assert response.json().get("code") == "password_confirmation_required"


# --- password sign-in ------------------------------------------------------------------------


async def test_sign_in_with_login_and_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _admin_with_password(db_session, AdminRole.viewer, login="Viewer.One")

    response = await client.post(
        "/internal/auth/password", json={"login": "  viewer.one ", "password": PASSWORD}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["telegram_id"], body["login"], body["has_password"]) == (
        admin.telegram_id,
        "viewer.one",
        True,
    )
    me = await client.get("/internal/me", headers=_cookie_headers(dict(response.cookies)))
    assert me.status_code == 200
    orders = await client.get("/internal/orders", headers=_cookie_headers(dict(response.cookies)))
    assert orders.status_code == 200


@pytest.mark.parametrize("case", ["wrong_password", "unknown_login", "inactive", "no_password"])
async def test_every_failure_answers_the_same(
    client: AsyncClient, db_session: AsyncSession, case: str
) -> None:
    admin = await _admin_with_password(db_session, login=f"case-{case}")
    login, password = admin.login, PASSWORD
    if case == "wrong_password":
        password = "not the password"
    elif case == "unknown_login":
        login = "nobody-here"
    elif case == "inactive":
        await db_session.execute(update(Admin).where(Admin.id == admin.id).values(is_active=False))
        await db_session.commit()
    else:
        await db_session.execute(
            update(Admin).where(Admin.id == admin.id).values(password_hash=None)
        )
        await db_session.commit()

    response = await client.post(
        "/internal/auth/password", json={"login": login, "password": password}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Wrong login or password"}
    assert "set-cookie" not in response.headers


async def test_five_wrong_passwords_lock_the_account_for_a_while(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_id = (await _admin_with_password(db_session, login="lock-me")).id

    for _ in range(admin_service.MAX_FAILED_LOGINS):
        await client.post("/internal/auth/password", json={"login": "lock-me", "password": "bad"})
    locked = await client.post(
        "/internal/auth/password", json={"login": "lock-me", "password": PASSWORD}
    )
    assert locked.status_code == 401  # even the right password, while locked

    await db_session.execute(
        update(Admin)
        .where(Admin.id == admin_id)
        .values(locked_until=datetime.now(UTC) - timedelta(seconds=1))
    )
    await db_session.commit()
    unlocked = await client.post(
        "/internal/auth/password", json={"login": "lock-me", "password": PASSWORD}
    )
    assert unlocked.status_code == 200


# --- profile ---------------------------------------------------------------------------------


async def test_an_admin_sets_a_first_password_then_needs_it_to_change_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tid = next(_ids)
    await add_admin(db_session, tid, AdminRole.dispatcher)

    first = await client.post(
        "/internal/me/password",
        json={"login": "Disp", "new_password": "first password 1"},
        headers=admin_tma(tid),
    )
    assert first.status_code == 200, first.text
    assert (first.json()["login"], first.json()["has_password"]) == ("disp", True)

    wrong = await client.post(
        "/internal/me/password",
        json={"current_password": "nope", "new_password": "second password"},
        headers=admin_tma(tid),
    )
    assert wrong.status_code == 403
    assert wrong.json()["code"] == "wrong_password"

    right = await client.post(
        "/internal/me/password",
        json={"current_password": "first password 1", "new_password": "second password"},
        headers=admin_tma(tid),
    )
    assert right.status_code == 200


@pytest.mark.parametrize(
    ("login", "password"),
    [
        ("ab", "long enough pass"),
        ("bad login!", "long enough pass"),
        ("okay", "short"),
        ("samesame12", "samesame12"),
    ],
)
async def test_bad_logins_and_passwords_are_refused(
    client: AsyncClient, db_session: AsyncSession, login: str, password: str
) -> None:
    tid = next(_ids)
    await add_admin(db_session, tid)

    response = await client.post(
        "/internal/me/password",
        json={"login": login, "new_password": password},
        headers=admin_tma(tid),
    )

    assert response.status_code == 400


async def test_a_taken_login_is_refused(client: AsyncClient, db_session: AsyncSession) -> None:
    await _admin_with_password(db_session, login="taken")
    tid = next(_ids)
    await add_admin(db_session, tid)

    response = await client.post(
        "/internal/me/password",
        json={"login": "TAKEN", "new_password": "long enough pass"},
        headers=admin_tma(tid),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "login_taken"


async def test_changing_the_password_signs_out_other_sessions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _admin_with_password(db_session, login="sessions")
    first = await client.post(
        "/internal/auth/password", json={"login": "sessions", "password": PASSWORD}
    )
    old_cookie = _cookie_headers(dict(first.cookies))

    await client.post(
        "/internal/me/password",
        json={"current_password": PASSWORD, "new_password": "a brand new password"},
        headers=admin_tma(admin.telegram_id),
    )

    assert (await client.get("/internal/me", headers=old_cookie)).status_code == 401


# --- reset by an owner -----------------------------------------------------------------------


async def test_owner_reset_gives_a_temporary_password_that_must_be_changed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _admin_with_password(db_session)
    target = next(_ids)
    await add_admin(db_session, target, AdminRole.dispatcher)
    target_id = await db_session.scalar(select(Admin.id).where(Admin.telegram_id == target))

    reset = await client.post(
        f"/internal/admins/{target_id}/password-reset",
        headers=admin_confirmed(owner.telegram_id, version=owner.session_version),
    )
    assert reset.status_code == 200, reset.text
    login, temporary = reset.json()["login"], reset.json()["temporary_password"]

    signed_in = await client.post(
        "/internal/auth/password", json={"login": login, "password": temporary}
    )
    assert signed_in.json()["must_change_password"] is True
    session = _cookie_headers(dict(signed_in.cookies))

    blocked = await client.get("/internal/orders", headers=session)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "password_change_required"
    assert (await client.get("/internal/me", headers=session)).status_code == 200

    changed = await client.post(
        "/internal/me/password", json={"new_password": "my own password now"}, headers=session
    )
    assert changed.status_code == 200, changed.text
    session = _cookie_headers(dict(changed.cookies))  # this browser stays signed in
    assert (await client.get("/internal/orders", headers=session)).status_code == 200


async def test_an_owner_cannot_reset_their_own_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _admin_with_password(db_session)

    response = await client.post(
        f"/internal/admins/{owner.id}/password-reset",
        headers=admin_confirmed(owner.telegram_id, version=owner.session_version),
    )

    assert response.status_code == 409


# --- hashing and the terminal ----------------------------------------------------------------


def test_hashes_are_salted_and_verify() -> None:
    first, second = (
        passwords.hash_password("same password"),
        passwords.hash_password("same password"),
    )
    assert first != second and first.startswith("scrypt$")
    assert passwords.verify_password("same password", first)
    assert not passwords.verify_password("other password", first)
    assert not passwords.verify_password("same password", "garbage")
    assert not passwords.verify_password("same password", None)


async def test_the_terminal_sets_a_password_for_an_existing_admin(db_session: AsyncSession) -> None:
    tid = next(_ids)
    await add_admin(db_session, tid)

    admin = await admin_service.set_password_from_terminal(db_session, tid, None, PASSWORD)

    assert admin.login == "owner"
    assert passwords.verify_password(PASSWORD, admin.password_hash)


def test_the_terminal_refuses_mismatched_passwords(capsys: pytest.CaptureFixture[str]) -> None:
    answers = iter(["one password", "another one"])

    code = set_admin_password.main(["1"], ask=lambda prompt: next(answers))

    assert code == 1
    assert "do not match" in capsys.readouterr().err
