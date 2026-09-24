from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.courier import CourierLocation
from app.models.enums import AdminRole, OrderStatus, ShipmentStatus
from app.services import courier_state
from tests.admin_factories import add_admin, admin_tma
from tests.courier_factories import INTERNAL_HEADERS, add_courier, add_paid_order, tma_headers


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/internal/couriers"),
        ("GET", "/internal/couriers"),
        ("PATCH", "/internal/couriers/1"),
    ],
)
@pytest.mark.parametrize(("headers", "expected"), [({}, 401), ({"X-Internal-Token": "wrong"}, 403)])
async def test_courier_management_needs_the_internal_token(
    client: AsyncClient, method: str, path: str, headers: dict[str, str], expected: int
) -> None:
    response = await client.request(
        method, path, json={"telegram_id": 1, "name": "x"}, headers=headers
    )

    assert response.status_code == expected


async def test_create_courier(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/couriers",
        json={"telegram_id": 777_001, "name": "Ali", "phone": "+998900000000"},
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["telegram_id"], body["name"], body["phone"], body["is_active"]) == (
        777_001,
        "Ali",
        "+998900000000",
        True,
    )


async def test_phone_is_optional(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/couriers",
        json={"telegram_id": 777_002, "name": "Bo"},
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 201
    assert response.json()["phone"] is None


async def test_registering_the_same_telegram_id_twice_is_a_conflict(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, 777_003)

    response = await client.post(
        "/internal/couriers",
        json={"telegram_id": 777_003, "name": "Again"},
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"telegram_id": 0, "name": "x"},
        {"telegram_id": -5, "name": "x"},
        {"telegram_id": 5, "name": ""},
    ],
)
async def test_invalid_courier_payload_is_rejected(
    client: AsyncClient, payload: dict[str, object]
) -> None:
    response = await client.post("/internal/couriers", json=payload, headers=INTERNAL_HEADERS)

    assert response.status_code == 422


async def test_update_name_and_phone(client: AsyncClient, db_session: AsyncSession) -> None:
    courier = await add_courier(db_session, 777_004, name="Old", phone="+1")

    response = await client.patch(
        f"/internal/couriers/{courier.id}",
        json={"name": "New", "phone": "+2"},
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 200
    assert (response.json()["name"], response.json()["phone"]) == ("New", "+2")


async def test_phone_can_be_cleared_with_an_explicit_null(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, 777_005, phone="+1")

    response = await client.patch(
        f"/internal/couriers/{courier.id}", json={"phone": None}, headers=INTERNAL_HEADERS
    )

    assert response.json()["phone"] is None


@pytest.mark.parametrize("payload", [{"name": None}, {"is_active": None}, {"telegram_id": 9}])
async def test_update_rejects_nulling_required_fields_and_changing_identity(
    client: AsyncClient, db_session: AsyncSession, payload: dict[str, object]
) -> None:
    courier = await add_courier(db_session, 777_006)

    response = await client.patch(
        f"/internal/couriers/{courier.id}", json=payload, headers=INTERNAL_HEADERS
    )

    assert response.status_code == 422


async def test_updating_an_unknown_courier_is_404(client: AsyncClient) -> None:
    response = await client.patch(
        "/internal/couriers/999999", json={"name": "x"}, headers=INTERNAL_HEADERS
    )

    assert response.status_code == 404


async def test_deactivation_takes_effect_immediately_and_can_be_undone(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, 777_007)
    headers = tma_headers(777_007)
    assert (await client.get("/courier/me", headers=headers)).status_code == 200

    off = await client.patch(
        f"/internal/couriers/{courier.id}", json={"is_active": False}, headers=INTERNAL_HEADERS
    )
    assert off.json()["is_active"] is False
    assert (await client.get("/courier/me", headers=headers)).status_code == 403

    await client.patch(
        f"/internal/couriers/{courier.id}", json={"is_active": True}, headers=INTERNAL_HEADERS
    )
    assert (await client.get("/courier/me", headers=headers)).status_code == 200


async def test_deactivation_deletes_the_couriers_stored_position(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, 777_008)
    other = await add_courier(db_session, 777_009)
    db_session.add_all(
        [
            CourierLocation(courier_id=courier.id, latitude=52.5, longitude=13.4),
            CourierLocation(courier_id=other.id, latitude=48.1, longitude=11.6),
        ]
    )
    await db_session.commit()

    await client.patch(
        f"/internal/couriers/{courier.id}", json={"is_active": False}, headers=INTERNAL_HEADERS
    )

    remaining = (await db_session.execute(select(CourierLocation.courier_id))).scalars().all()
    assert remaining == [other.id]


async def test_list_returns_couriers_in_registration_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await add_courier(db_session, 777_010, name="First")
    second = await add_courier(db_session, 777_011, name="Second", is_active=False)

    response = await client.get("/internal/couriers", headers=INTERNAL_HEADERS)

    listed = response.json()
    ids = [courier["id"] for courier in listed]
    assert ids.index(first.id) < ids.index(second.id)
    assert next(c for c in listed if c["id"] == second.id)["is_active"] is False


async def test_courier_list_counts_active_deliveries(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    busy = await add_courier(db_session, 880_101)
    idle = await add_courier(db_session, 880_102)
    for _ in range(2):
        order, shipment = await add_paid_order(db_session, customer_id=880_103)
        shipment.status = ShipmentStatus.assigned
        shipment.courier_id = busy.id
        order.status = OrderStatus.processing
    await db_session.commit()

    response = await client.get("/internal/couriers", headers=INTERNAL_HEADERS)

    counts = {c["id"]: c["active_deliveries"] for c in response.json()}
    assert (counts[busy.id], counts[idle.id]) == (2, 0)


async def test_courier_locations_show_only_working_couriers(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    working = await add_courier(db_session, 880_201, name="Aziz")
    leftover = await add_courier(db_session, 880_202)
    order, shipment = await add_paid_order(db_session, customer_id=880_203)
    shipment.status = ShipmentStatus.shipped
    shipment.courier_id = working.id
    order.status = OrderStatus.shipped
    await db_session.commit()
    await courier_state.record_location(db_session, working.id, 41.31, 69.24)
    # A stray row for an idle courier must still not be shown.
    await courier_state.record_location(db_session, leftover.id, 41.0, 69.0)
    await db_session.commit()

    response = await client.get("/internal/couriers/locations", headers=INTERNAL_HEADERS)

    assert response.status_code == 200
    rows = [r for r in response.json() if r["courier_id"] in (working.id, leftover.id)]
    assert len(rows) == 1
    row = rows[0]
    assert (row["courier_id"], row["name"], row["latitude"], row["longitude"]) == (
        working.id,
        "Aziz",
        41.31,
        69.24,
    )
    assert (row["is_stale"], row["active_deliveries"]) == (False, 1)


async def test_old_positions_are_marked_stale(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, 880_301)
    order, shipment = await add_paid_order(db_session, customer_id=880_302)
    shipment.status = ShipmentStatus.shipped
    shipment.courier_id = courier.id
    order.status = OrderStatus.shipped
    db_session.add(
        CourierLocation(
            courier_id=courier.id,
            latitude=1.0,
            longitude=2.0,
            updated_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.commit()

    response = await client.get("/internal/couriers/locations", headers=INTERNAL_HEADERS)

    row = next(r for r in response.json() if r["courier_id"] == courier.id)
    assert row["is_stale"] is True


async def test_catalog_managers_cannot_see_courier_positions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_admin(db_session, 880_401, AdminRole.catalog_manager)
    response = await client.get("/internal/couriers/locations", headers=admin_tma(880_401))
    assert response.status_code == 403
