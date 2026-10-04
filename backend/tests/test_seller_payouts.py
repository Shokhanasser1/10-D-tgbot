"""Spec 11 §4-6: balances, payouts recorded by hand (🔒), the ledger, and a seller's own view."""

import itertools

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.enums import AdminRole
from app.models.notification import Notification
from app.services import earnings_service
from tests.admin_factories import add_admin, admin_confirmed, admin_tma
from tests.courier_factories import add_paid_order
from tests.factories import add_seller

_ids = itertools.count(898_001)


@pytest.fixture(autouse=True)
def _webapp_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "webapp_url", "https://shop.example.com/")


async def _earning_seller(db: AsyncSession, orders: int = 1) -> tuple[int, int]:
    """A seller with `orders` delivered orders of 30.00 each (27.00 theirs at 10%), and its
    account's Telegram id."""
    seller = await add_seller(db, "Lola")
    account = next(_ids)
    await add_admin(db, account, AdminRole.seller, seller_id=seller.id)
    for _ in range(orders):
        order, _ = await add_paid_order(db, customer_id=next(_ids), seller_id=seller.id, qty=3)
        await earnings_service.record_earning(db, order.id)
    await db.commit()
    return seller.id, account


async def _staff(db: AsyncSession, role: AdminRole, *, confirmed: bool = True) -> dict[str, str]:
    telegram_id = next(_ids)
    await add_admin(db, telegram_id, role)
    return admin_confirmed(telegram_id) if confirmed else admin_tma(telegram_id)


def _payout(amount: str, currency: str = "EUR", note: str | None = "Card *1234") -> dict:
    return {"amount": amount, "currency": currency, "note": note}


async def test_the_seller_list_shows_rates_and_balances(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seller_id, _ = await _earning_seller(db_session)
    owner = await _staff(db_session, AdminRole.owner)
    catalog = await _staff(db_session, AdminRole.catalog_manager)

    (mine,) = [
        s
        for s in (await client.get("/internal/sellers", headers=owner)).json()
        if s["id"] == seller_id
    ]
    (seen,) = [
        s
        for s in (await client.get("/internal/sellers", headers=catalog)).json()
        if s["id"] == seller_id
    ]

    assert mine["commission_percent"] == "10.00"
    assert mine["balances"] == [
        {"currency": "EUR", "earned": "27.00", "paid_out": "0.00", "balance": "27.00"}
    ]
    assert seen["balances"] == []  # money is for those who handle payouts


async def test_recording_a_payout_lowers_the_balance_and_tells_the_seller(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seller_id, account = await _earning_seller(db_session)
    owner = await _staff(db_session, AdminRole.owner)

    response = await client.post(
        f"/internal/sellers/{seller_id}/payouts", json=_payout("20.00"), headers=owner
    )

    assert response.status_code == 201, response.text
    assert (response.json()["amount"], response.json()["note"]) == ("20.00", "Card *1234")
    ledger = (await client.get(f"/internal/sellers/{seller_id}/ledger", headers=owner)).json()
    assert ledger["balances"] == [
        {"currency": "EUR", "earned": "27.00", "paid_out": "20.00", "balance": "7.00"}
    ]
    texts = list(
        await db_session.scalars(select(Notification.text).where(Notification.chat_id == account))
    )
    assert texts == ["Payout recorded: €20.00. Balance: €7.00."]


async def test_an_accountant_records_payouts_too(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seller_id, _ = await _earning_seller(db_session)
    accountant = await _staff(db_session, AdminRole.accountant)

    listed = await client.get("/internal/sellers", headers=accountant)
    paid = await client.post(
        f"/internal/sellers/{seller_id}/payouts", json=_payout("5.00"), headers=accountant
    )

    assert (listed.status_code, paid.status_code) == (200, 201)


@pytest.mark.parametrize("role", [AdminRole.manager, AdminRole.catalog_manager, AdminRole.seller])
async def test_other_roles_cannot_record_payouts(
    client: AsyncClient, db_session: AsyncSession, role: AdminRole
) -> None:
    seller_id, _ = await _earning_seller(db_session)
    headers = await _staff(db_session, role)

    response = await client.post(
        f"/internal/sellers/{seller_id}/payouts", json=_payout("5.00"), headers=headers
    )
    ledger = await client.get(f"/internal/sellers/{seller_id}/ledger", headers=headers)

    assert (response.status_code, ledger.status_code) == (403, 403)


async def test_a_payout_needs_the_password(client: AsyncClient, db_session: AsyncSession) -> None:
    seller_id, _ = await _earning_seller(db_session)
    owner = await _staff(db_session, AdminRole.owner, confirmed=False)

    response = await client.post(
        f"/internal/sellers/{seller_id}/payouts", json=_payout("5.00"), headers=owner
    )

    assert response.status_code == 403
    assert response.json()["code"] in ("password_confirmation_required", "password_not_set")


async def test_a_payout_never_exceeds_the_balance(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seller_id, _ = await _earning_seller(db_session)
    owner = await _staff(db_session, AdminRole.owner)

    too_much = await client.post(
        f"/internal/sellers/{seller_id}/payouts", json=_payout("27.01"), headers=owner
    )
    other_currency = await client.post(
        f"/internal/sellers/{seller_id}/payouts", json=_payout("1.00", "UZS"), headers=owner
    )
    all_of_it = await client.post(
        f"/internal/sellers/{seller_id}/payouts", json=_payout("27.00", note=None), headers=owner
    )

    for refused in (too_much, other_currency):
        assert (refused.status_code, refused.json()["code"]) == (409, "exceeds_balance")
    assert all_of_it.status_code == 201


@pytest.mark.parametrize("amount", ["0", "-5.00", "1.001"])
async def test_a_payout_amount_must_be_positive_cents(
    client: AsyncClient, db_session: AsyncSession, amount: str
) -> None:
    seller_id, _ = await _earning_seller(db_session)
    owner = await _staff(db_session, AdminRole.owner)

    response = await client.post(
        f"/internal/sellers/{seller_id}/payouts", json=_payout(amount), headers=owner
    )

    assert response.status_code == 422


async def test_an_unknown_seller_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _staff(db_session, AdminRole.owner)

    response = await client.post(
        "/internal/sellers/999999/payouts", json=_payout("1.00"), headers=owner
    )

    assert response.status_code == 404


async def test_the_ledger_lists_earnings_and_payouts_newest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seller_id, _ = await _earning_seller(db_session, orders=2)
    owner = await _staff(db_session, AdminRole.owner)
    for amount in ("10.00", "15.00"):
        await client.post(
            f"/internal/sellers/{seller_id}/payouts", json=_payout(amount), headers=owner
        )

    ledger = (await client.get(f"/internal/sellers/{seller_id}/ledger", headers=owner)).json()

    assert [e["amount"] for e in ledger["earnings"]] == ["27.00", "27.00"]
    assert ledger["earnings"][0]["order_id"] > ledger["earnings"][1]["order_id"]
    assert [p["amount"] for p in ledger["payouts"]] == ["15.00", "10.00"]
    assert ledger["balances"][0]["balance"] == "29.00"


async def test_a_seller_sees_their_own_money_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seller_id, account = await _earning_seller(db_session)
    await _earning_seller(db_session)  # another seller's money
    dispatcher = await _staff(db_session, AdminRole.dispatcher)

    mine = (await client.get("/internal/seller/earnings", headers=admin_tma(account))).json()
    staff = await client.get("/internal/seller/earnings", headers=dispatcher)

    assert len(mine["earnings"]) == 1
    assert mine["earnings"][0]["commission"] == "3.00"
    assert mine["balances"][0]["balance"] == "27.00"
    assert staff.status_code == 403


async def test_the_rate_is_set_with_the_seller(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _staff(db_session, AdminRole.owner)
    created = await client.post(
        "/internal/sellers",
        json={
            "name": "Anor",
            "pickup_address": "Yunusobod 1",
            "telegram_id": next(_ids),
            "display_name": "Anor",
            "commission_percent": "12.5",
        },
        headers=owner,
    )
    seller_id = created.json()["id"]

    changed = await client.patch(
        f"/internal/sellers/{seller_id}", json={"commission_percent": "8"}, headers=owner
    )
    too_high = await client.patch(
        f"/internal/sellers/{seller_id}", json={"commission_percent": "100.5"}, headers=owner
    )

    assert created.json()["commission_percent"] == "12.50"
    assert changed.json()["commission_percent"] == "8.00"
    assert too_high.status_code == 422
