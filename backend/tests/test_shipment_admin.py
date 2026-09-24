"""The owner's escape hatch for deliveries stuck with a courier who vanished."""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.courier import Courier, CourierLocation
from app.models.enums import OrderStatus, ShipmentStatus
from app.models.order import Order
from app.models.shipment import Shipment
from tests.courier_factories import INTERNAL_HEADERS, add_courier, add_paid_order, tma_headers

COURIER_A = 830_001
COURIER_B = 830_002


async def hold(
    db: AsyncSession,
    courier: Courier,
    shipment: Shipment,
    order: Order,
    shipment_status: ShipmentStatus,
    order_status: OrderStatus,
) -> None:
    shipment.status = shipment_status
    shipment.courier_id = courier.id
    order.status = order_status
    await db.commit()


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/internal/shipments"), ("POST", "/internal/shipments/1/release")],
)
async def test_shipment_admin_needs_the_internal_token(
    client: AsyncClient, method: str, path: str
) -> None:
    assert (await client.request(method, path)).status_code == 401
    wrong = await client.request(method, path, headers={"X-Internal-Token": "nope"})
    assert wrong.status_code == 403


@pytest.mark.parametrize(
    ("shipment_status", "order_status"),
    [
        (ShipmentStatus.assigned, OrderStatus.processing),
        (ShipmentStatus.shipped, OrderStatus.shipped),
    ],
)
async def test_release_returns_a_held_delivery_to_the_pool(
    client: AsyncClient,
    db_session: AsyncSession,
    shipment_status: ShipmentStatus,
    order_status: OrderStatus,
) -> None:
    courier = await add_courier(db_session, COURIER_A)
    order, shipment = await add_paid_order(db_session)
    await hold(db_session, courier, shipment, order, shipment_status, order_status)

    response = await client.post(
        f"/internal/shipments/{shipment.id}/release", headers=INTERNAL_HEADERS
    )

    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    await db_session.refresh(shipment)
    await db_session.refresh(order)
    assert (shipment.status, shipment.courier_id, order.status) == (
        ShipmentStatus.processing,
        None,
        OrderStatus.paid,
    )
    assert shipment.assigned_at is None and shipment.picked_up_at is None


async def test_release_works_after_the_courier_was_deactivated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, COURIER_A)
    order, shipment = await add_paid_order(db_session)
    await hold(
        db_session, courier, shipment, order, ShipmentStatus.assigned, OrderStatus.processing
    )
    await client.patch(
        f"/internal/couriers/{courier.id}", json={"is_active": False}, headers=INTERNAL_HEADERS
    )

    response = await client.post(
        f"/internal/shipments/{shipment.id}/release", headers=INTERNAL_HEADERS
    )

    assert response.status_code == 200


async def test_a_released_delivery_can_be_claimed_by_someone_else(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await add_courier(db_session, COURIER_A)
    second = await add_courier(db_session, COURIER_B)
    order, shipment = await add_paid_order(db_session)
    await hold(db_session, first, shipment, order, ShipmentStatus.shipped, OrderStatus.shipped)
    await client.post(f"/internal/shipments/{shipment.id}/release", headers=INTERNAL_HEADERS)

    claimed = await client.post(
        f"/courier/deliveries/{shipment.id}/claim", headers=tma_headers(COURIER_B)
    )

    assert claimed.status_code == 200
    await db_session.refresh(shipment)
    assert shipment.courier_id == second.id


@pytest.mark.parametrize("status", [ShipmentStatus.processing, ShipmentStatus.delivered])
async def test_only_a_held_delivery_can_be_released(
    client: AsyncClient, db_session: AsyncSession, status: ShipmentStatus
) -> None:
    order, shipment = await add_paid_order(db_session)
    shipment.status = status
    await db_session.commit()

    response = await client.post(
        f"/internal/shipments/{shipment.id}/release", headers=INTERNAL_HEADERS
    )

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_state"


async def test_releasing_an_unknown_shipment_is_404(client: AsyncClient) -> None:
    response = await client.post("/internal/shipments/999999/release", headers=INTERNAL_HEADERS)

    assert response.status_code == 404


async def test_position_is_only_dropped_when_it_was_the_couriers_last_active_delivery(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, COURIER_A)
    first_order, first = await add_paid_order(db_session)
    second_order, second = await add_paid_order(db_session)
    await hold(db_session, courier, first, first_order, ShipmentStatus.shipped, OrderStatus.shipped)
    await hold(
        db_session, courier, second, second_order, ShipmentStatus.shipped, OrderStatus.shipped
    )
    db_session.add(CourierLocation(courier_id=courier.id, latitude=52.5, longitude=13.4))
    await db_session.commit()

    async def positions() -> int:
        return await db_session.scalar(select(func.count()).select_from(CourierLocation)) or 0

    await client.post(f"/internal/shipments/{first.id}/release", headers=INTERNAL_HEADERS)
    assert await positions() == 1

    await client.post(f"/internal/shipments/{second.id}/release", headers=INTERNAL_HEADERS)
    assert await positions() == 0


async def test_listing_defaults_to_deliveries_a_courier_is_holding(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, COURIER_A, name="Ali")
    held_order, held = await add_paid_order(db_session)
    _, pooled = await add_paid_order(db_session)
    done_order, done = await add_paid_order(db_session)
    await hold(
        db_session, courier, held, held_order, ShipmentStatus.assigned, OrderStatus.processing
    )
    await hold(
        db_session, courier, done, done_order, ShipmentStatus.delivered, OrderStatus.delivered
    )

    default = (await client.get("/internal/shipments", headers=INTERNAL_HEADERS)).json()
    delivered = (
        await client.get("/internal/shipments?status=delivered", headers=INTERNAL_HEADERS)
    ).json()
    several = (
        await client.get(
            "/internal/shipments?status=processing&status=delivered", headers=INTERNAL_HEADERS
        )
    ).json()

    assert [s["id"] for s in default] == [held.id]
    assert default[0]["courier_name"] == "Ali" and default[0]["courier_id"] == courier.id
    assert [s["id"] for s in delivered] == [done.id]
    assert {s["id"] for s in several} >= {pooled.id, done.id}
    assert held.id not in {s["id"] for s in several}


async def test_listing_rejects_an_unknown_status(client: AsyncClient) -> None:
    response = await client.get("/internal/shipments?status=lost", headers=INTERNAL_HEADERS)

    assert response.status_code == 422
