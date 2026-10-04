"""Spec 9 §5: the owner and the manager add, edit and deactivate sellers, each with its admin
account; the general admin endpoints never hand out or take away the seller role."""

import itertools
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Admin, Category, Product, Seller
from app.models.enums import AdminRole
from tests.admin_factories import add_admin, admin_confirmed, admin_tma
from tests.factories import add_seller

_ids = itertools.count(860_001)


def _new_seller(telegram_id: int, name: str = "Lola Beauty") -> dict:
    return {
        "name": name,
        "phone": "+998901112233",
        "pickup_address": "Tashkent, Chilonzor 5",
        "telegram_id": telegram_id,
        "display_name": "Lola",
    }


async def _as(db: AsyncSession, role: AdminRole, **kwargs) -> dict[str, str]:
    telegram_id = next(_ids)
    await add_admin(db, telegram_id, role, **kwargs)
    return admin_tma(telegram_id)


@pytest.mark.parametrize("role", [AdminRole.owner, AdminRole.manager])
async def test_owner_and_manager_add_a_seller_with_its_account(
    client: AsyncClient, db_session: AsyncSession, role: AdminRole
) -> None:
    headers = await _as(db_session, role)
    telegram_id = next(_ids)

    response = await client.post(
        "/internal/sellers", json=_new_seller(telegram_id), headers=headers
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["name"], body["pickup_address"], body["is_active"], body["product_count"]) == (
        "Lola Beauty",
        "Tashkent, Chilonzor 5",
        True,
        0,
    )
    (account,) = body["accounts"]
    assert (account["telegram_id"], account["display_name"], account["is_active"]) == (
        telegram_id,
        "Lola",
        True,
    )
    admin = await db_session.scalar(select(Admin).where(Admin.telegram_id == telegram_id))
    assert admin is not None and (admin.role, admin.seller_id) == (AdminRole.seller, body["id"])
    # The account works at once.
    me = (await client.get("/internal/me", headers=admin_tma(telegram_id))).json()
    assert me["seller_name"] == "Lola Beauty"


@pytest.mark.parametrize(
    "role", [AdminRole.catalog_manager, AdminRole.dispatcher, AdminRole.viewer, AdminRole.seller]
)
async def test_other_roles_cannot_add_or_edit_sellers(
    client: AsyncClient, db_session: AsyncSession, role: AdminRole
) -> None:
    headers = await _as(db_session, role)
    seller = await add_seller(db_session, "Someone")

    created = await client.post("/internal/sellers", json=_new_seller(next(_ids)), headers=headers)
    edited = await client.patch(
        f"/internal/sellers/{seller.id}", json={"name": "Mine"}, headers=headers
    )

    assert (created.status_code, edited.status_code) == (403, 403)


async def test_a_telegram_id_that_already_has_an_admin_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _as(db_session, AdminRole.owner)
    taken = next(_ids)
    await add_admin(db_session, taken, AdminRole.dispatcher)
    sellers_before = await db_session.scalar(select(func.count()).select_from(Seller))

    response = await client.post("/internal/sellers", json=_new_seller(taken), headers=headers)

    assert response.status_code == 409
    assert response.json()["code"] == "already_exists"
    assert await db_session.scalar(select(func.count()).select_from(Seller)) == sellers_before


async def test_the_list_is_ordered_by_name_and_counts_products(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _as(db_session, AdminRole.owner)
    zara = await add_seller(db_session, "Zara Cosmetics")
    anor = await add_seller(db_session, "Anor Beauty")
    category = Category(slug="sellers-list", sort_order=0)
    db_session.add(category)
    await db_session.flush()
    for n in range(2):
        db_session.add(
            Product(
                category_id=category.id,
                seller_id=zara.id,
                base_sku=f"ZARA-{n}",
                base_price=Decimal("1.00"),
            )
        )
    await db_session.commit()

    listed = (await client.get("/internal/sellers", headers=headers)).json()

    names = [s["name"] for s in listed]
    assert names.index("Anor Beauty") < names.index("Zara Cosmetics")
    counts = {s["id"]: s["product_count"] for s in listed}
    assert (counts[zara.id], counts[anor.id]) == (2, 0)


async def test_catalog_staff_see_the_list_and_a_seller_sees_only_itself(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    mine = await add_seller(db_session, "Mine")
    await add_seller(db_session, "Theirs")
    as_seller = await _as(db_session, AdminRole.seller, seller_id=mine.id)
    as_catalog = await _as(db_session, AdminRole.catalog_manager)
    as_dispatcher = await _as(db_session, AdminRole.dispatcher)

    seller_view = (await client.get("/internal/sellers", headers=as_seller)).json()
    catalog_view = (await client.get("/internal/sellers", headers=as_catalog)).json()
    dispatcher = await client.get("/internal/sellers", headers=as_dispatcher)

    assert [s["id"] for s in seller_view] == [mine.id]
    assert {"Mine", "Theirs"} <= {s["name"] for s in catalog_view}
    # Accounts (Telegram ids) are for those who manage sellers.
    assert all(s["accounts"] == [] for s in catalog_view)
    assert dispatcher.status_code == 403


async def test_editing_a_seller(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _as(db_session, AdminRole.owner)
    seller = await add_seller(db_session, "Old name")

    edited = await client.patch(
        f"/internal/sellers/{seller.id}",
        json={"name": "New name", "phone": "+998900000000", "pickup_address": "Yunusobod 1"},
        headers=headers,
    )
    nulled = await client.patch(
        f"/internal/sellers/{seller.id}", json={"name": None}, headers=headers
    )
    missing = await client.patch("/internal/sellers/999999", json={"name": "x"}, headers=headers)

    assert edited.status_code == 200
    assert (edited.json()["name"], edited.json()["phone"], edited.json()["pickup_address"]) == (
        "New name",
        "+998900000000",
        "Yunusobod 1",
    )
    assert nulled.status_code == 422
    assert missing.status_code == 404


async def test_deactivating_a_seller_locks_its_account_until_reactivated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _as(db_session, AdminRole.owner)
    telegram_id = next(_ids)
    seller = (
        await client.post("/internal/sellers", json=_new_seller(telegram_id), headers=headers)
    ).json()

    await client.patch(
        f"/internal/sellers/{seller['id']}", json={"is_active": False}, headers=headers
    )
    locked = await client.get("/internal/me", headers=admin_tma(telegram_id))
    await client.patch(
        f"/internal/sellers/{seller['id']}", json={"is_active": True}, headers=headers
    )
    unlocked = await client.get("/internal/me", headers=admin_tma(telegram_id))

    assert (locked.status_code, locked.json()["code"]) == (403, "seller_inactive")
    assert unlocked.status_code == 200


# --- the general admin endpoints -------------------------------------------------------------


async def _owner_confirmed(db: AsyncSession) -> dict[str, str]:
    telegram_id = next(_ids)
    await add_admin(db, telegram_id, AdminRole.owner)
    return admin_confirmed(telegram_id)


async def test_the_admins_api_does_not_create_seller_accounts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _owner_confirmed(db_session)

    response = await client.post(
        "/internal/admins",
        json={"telegram_id": next(_ids), "role": "seller", "display_name": "Lola"},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "seller_role_fixed"


async def test_roles_do_not_change_to_or_from_seller(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _owner_confirmed(db_session)
    # Ids up front: a refused update rolls back the session the test shares with the app.
    seller_account_id = (await add_admin(db_session, next(_ids), AdminRole.seller)).id
    staff_id = (await add_admin(db_session, next(_ids), AdminRole.dispatcher)).id

    from_seller = await client.patch(
        f"/internal/admins/{seller_account_id}", json={"role": "manager"}, headers=headers
    )
    to_seller = await client.patch(
        f"/internal/admins/{staff_id}", json={"role": "seller"}, headers=headers
    )

    assert (from_seller.status_code, from_seller.json()["code"]) == (409, "seller_role_fixed")
    assert (to_seller.status_code, to_seller.json()["code"]) == (409, "seller_role_fixed")


async def test_a_seller_account_can_still_be_deactivated_there(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _owner_confirmed(db_session)
    seller_account = await add_admin(db_session, next(_ids), AdminRole.seller)

    response = await client.patch(
        f"/internal/admins/{seller_account.id}", json={"is_active": False}, headers=headers
    )
    listed = (await client.get("/internal/admins", headers=headers)).json()

    assert response.status_code == 200 and response.json()["is_active"] is False
    (row,) = [a for a in listed if a["id"] == seller_account.id]
    assert row["seller_id"] == seller_account.seller_id
