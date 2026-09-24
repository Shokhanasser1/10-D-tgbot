from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AdminRole
from tests.admin_factories import add_admin, admin_tma
from tests.courier_factories import INTERNAL_HEADERS


async def test_owner_adds_an_admin(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_admin(db_session, 710_001)

    response = await client.post(
        "/internal/admins",
        json={"telegram_id": 710_002, "role": "dispatcher", "display_name": "Jasur"},
        headers=admin_tma(710_001),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["telegram_id"] == 710_002
    assert body["role"] == "dispatcher"
    assert body["is_active"] is True
    assert body["created_by"] == 710_001


async def test_adding_an_existing_admin_is_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_admin(db_session, 710_003, AdminRole.dispatcher)

    response = await client.post(
        "/internal/admins",
        json={"telegram_id": 710_003, "role": "owner", "display_name": "X"},
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "already_exists"


async def test_list_admins(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_admin(db_session, 710_004)

    response = await client.get("/internal/admins", headers=INTERNAL_HEADERS)

    assert response.status_code == 200
    assert 710_004 in [a["telegram_id"] for a in response.json()]


async def test_non_owners_cannot_manage_admins(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_admin(db_session, 710_005, AdminRole.dispatcher)
    await add_admin(db_session, 710_006, AdminRole.catalog_manager)

    for tid in (710_005, 710_006):
        assert (await client.get("/internal/admins", headers=admin_tma(tid))).status_code == 403


async def test_owner_changes_role_and_name(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_admin(db_session, 710_007)
    target = await add_admin(db_session, 710_008, AdminRole.dispatcher)

    response = await client.patch(
        f"/internal/admins/{target.id}",
        json={"role": "catalog_manager", "display_name": "Nodira"},
        headers=admin_tma(710_007),
    )

    assert response.status_code == 200
    assert response.json()["role"] == "catalog_manager"
    assert response.json()["display_name"] == "Nodira"


async def test_cannot_deactivate_yourself(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_admin(db_session, 710_009)
    me_id = (await add_admin(db_session, 710_010)).id

    response = await client.patch(
        f"/internal/admins/{me_id}", json={"is_active": False}, headers=admin_tma(710_010)
    )

    assert response.status_code == 409
    assert response.json()["code"] == "self_deactivation"


async def test_cannot_remove_the_last_active_owner(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner_id = (await add_admin(db_session, 710_011)).id

    demote = await client.patch(
        f"/internal/admins/{owner_id}", json={"role": "dispatcher"}, headers=INTERNAL_HEADERS
    )
    deactivate = await client.patch(
        f"/internal/admins/{owner_id}", json={"is_active": False}, headers=INTERNAL_HEADERS
    )

    assert demote.status_code == deactivate.status_code == 409
    assert demote.json()["code"] == deactivate.json()["code"] == "last_owner"


async def test_one_of_two_owners_can_be_demoted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_admin(db_session, 710_012)
    second = await add_admin(db_session, 710_013)

    response = await client.patch(
        f"/internal/admins/{second.id}", json={"is_active": False}, headers=admin_tma(710_012)
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_patch_unknown_admin_is_404(client: AsyncClient) -> None:
    response = await client.patch(
        "/internal/admins/999999", json={"display_name": "X"}, headers=INTERNAL_HEADERS
    )
    assert response.status_code == 404


async def test_patch_rejects_nulls_and_unknown_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_id = (await add_admin(db_session, 710_014)).id

    for body in ({"role": None}, {"telegram_id": 1}):
        response = await client.patch(
            f"/internal/admins/{admin_id}", json=body, headers=INTERNAL_HEADERS
        )
        assert response.status_code == 422
