import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.courier import Courier, CourierLocation
from app.models.enums import OrderStatus, ShipmentStatus
from app.models.order import Order
from app.models.shipment import Shipment
from tests.courier_factories import add_courier, add_paid_order, tma_headers

COURIER_A = 810_001
COURIER_B = 810_002


async def act(client: AsyncClient, action: str, shipment_id: int, courier_tid: int) -> Response:
    return await client.post(
        f"/courier/deliveries/{shipment_id}/{action}", headers=tma_headers(courier_tid)
    )


async def state(
    db: AsyncSession, shipment: Shipment, order: Order
) -> tuple[ShipmentStatus, OrderStatus, int | None]:
    await db.refresh(shipment)
    await db.refresh(order)
    return shipment.status, order.status, shipment.courier_id


async def put_in_state(
    db: AsyncSession,
    shipment: Shipment,
    order: Order,
    shipment_status: ShipmentStatus,
    order_status: OrderStatus,
    courier: Courier | None,
) -> None:
    shipment.status = shipment_status
    shipment.courier_id = courier.id if courier else None
    order.status = order_status
    await db.commit()


HELD_STATES = {
    "assigned": (ShipmentStatus.assigned, OrderStatus.processing),
    "shipped": (ShipmentStatus.shipped, OrderStatus.shipped),
    "delivered": (ShipmentStatus.delivered, OrderStatus.delivered),
}


async def test_claim_assigns_the_shipment_and_moves_the_order_along(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, COURIER_A)
    order, shipment = await add_paid_order(db_session)

    response = await act(client, "claim", shipment.id, COURIER_A)

    assert response.status_code == 200
    assert response.json() == {
        "shipment_id": shipment.id,
        "order_id": order.id,
        "status": "assigned",
    }
    assert await state(db_session, shipment, order) == (
        ShipmentStatus.assigned,
        OrderStatus.processing,
        courier.id,
    )
    assert shipment.assigned_at is not None


async def test_a_delivery_runs_from_the_pool_to_delivered(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, COURIER_A)
    order, shipment = await add_paid_order(db_session)

    assert (await act(client, "claim", shipment.id, COURIER_A)).status_code == 200

    assert (await act(client, "pickup", shipment.id, COURIER_A)).json()["status"] == "shipped"
    assert await state(db_session, shipment, order) == (
        ShipmentStatus.shipped,
        OrderStatus.shipped,
        courier.id,
    )
    assert shipment.picked_up_at is not None and shipment.delivered_at is None

    assert (await act(client, "deliver", shipment.id, COURIER_A)).json()["status"] == "delivered"
    assert await state(db_session, shipment, order) == (
        ShipmentStatus.delivered,
        OrderStatus.delivered,
        courier.id,
    )
    assert shipment.delivered_at is not None


async def test_release_puts_the_order_back_in_the_pool_for_any_courier(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, COURIER_A)
    other = await add_courier(db_session, COURIER_B)
    order, shipment = await add_paid_order(db_session)
    await act(client, "claim", shipment.id, COURIER_A)

    response = await act(client, "release", shipment.id, COURIER_A)

    assert response.status_code == 200
    assert await state(db_session, shipment, order) == (
        ShipmentStatus.processing,
        OrderStatus.paid,
        None,
    )
    assert shipment.assigned_at is None and shipment.picked_up_at is None

    assert (await act(client, "claim", shipment.id, COURIER_B)).status_code == 200
    await db_session.refresh(shipment)
    assert shipment.courier_id == other.id


@pytest.mark.parametrize(
    ("action", "held_state"),
    [
        ("claim", "assigned"),
        ("claim", "shipped"),
        ("claim", "delivered"),
        ("release", "shipped"),
        ("release", "delivered"),
        ("pickup", "shipped"),
        ("pickup", "delivered"),
        ("deliver", "assigned"),
        ("deliver", "delivered"),
    ],
)
async def test_an_action_from_the_wrong_state_is_a_conflict_and_changes_nothing(
    client: AsyncClient, db_session: AsyncSession, action: str, held_state: str
) -> None:
    courier = await add_courier(db_session, COURIER_A)
    order, shipment = await add_paid_order(db_session)
    shipment_status, order_status = HELD_STATES[held_state]
    await put_in_state(db_session, shipment, order, shipment_status, order_status, courier)

    response = await act(client, action, shipment.id, COURIER_A)

    assert response.status_code == 409
    assert response.json()["code"] == ("shipment_taken" if action == "claim" else "invalid_state")
    assert await state(db_session, shipment, order) == (shipment_status, order_status, courier.id)


@pytest.mark.parametrize("action", ["release", "pickup", "deliver"])
@pytest.mark.parametrize("held_state", ["assigned", "shipped"])
async def test_another_couriers_delivery_looks_like_it_does_not_exist(
    client: AsyncClient, db_session: AsyncSession, action: str, held_state: str
) -> None:
    holder = await add_courier(db_session, COURIER_A)
    await add_courier(db_session, COURIER_B)
    order, shipment = await add_paid_order(db_session)
    shipment_status, order_status = HELD_STATES[held_state]
    await put_in_state(db_session, shipment, order, shipment_status, order_status, holder)

    response = await act(client, action, shipment.id, COURIER_B)

    assert response.status_code == 404
    assert await state(db_session, shipment, order) == (shipment_status, order_status, holder.id)


@pytest.mark.parametrize("action", ["claim", "release", "pickup", "deliver"])
async def test_an_unknown_shipment_is_404(
    client: AsyncClient, db_session: AsyncSession, action: str
) -> None:
    await add_courier(db_session, COURIER_A)

    assert (await act(client, action, 999_999, COURIER_A)).status_code == 404


@pytest.mark.parametrize("action", ["release", "pickup", "deliver"])
async def test_an_unclaimed_delivery_cannot_be_progressed(
    client: AsyncClient, db_session: AsyncSession, action: str
) -> None:
    await add_courier(db_session, COURIER_A)
    order, shipment = await add_paid_order(db_session)

    assert (await act(client, action, shipment.id, COURIER_A)).status_code == 404
    assert await state(db_session, shipment, order) == (
        ShipmentStatus.processing,
        OrderStatus.paid,
        None,
    )


async def test_the_second_courier_to_claim_loses(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await add_courier(db_session, COURIER_A)
    await add_courier(db_session, COURIER_B)
    _, shipment = await add_paid_order(db_session)

    assert (await act(client, "claim", shipment.id, COURIER_A)).status_code == 200
    late = await act(client, "claim", shipment.id, COURIER_B)

    assert late.status_code == 409
    assert late.json()["code"] == "shipment_taken"
    await db_session.refresh(shipment)
    assert shipment.courier_id == first.id


async def test_a_courier_cannot_hold_more_than_the_limit(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "max_active_deliveries_per_courier", 2)
    await add_courier(db_session, COURIER_A)
    shipments = [(await add_paid_order(db_session))[1] for _ in range(3)]

    assert (await act(client, "claim", shipments[0].id, COURIER_A)).status_code == 200
    assert (await act(client, "claim", shipments[1].id, COURIER_A)).status_code == 200
    over = await act(client, "claim", shipments[2].id, COURIER_A)

    assert over.status_code == 409
    assert over.json()["code"] == "delivery_limit_reached"
    await db_session.refresh(shipments[2])
    assert shipments[2].courier_id is None

    # Finishing one frees a slot.
    await act(client, "pickup", shipments[0].id, COURIER_A)
    await act(client, "deliver", shipments[0].id, COURIER_A)
    assert (await act(client, "claim", shipments[2].id, COURIER_A)).status_code == 200


async def test_a_failed_order_update_rolls_the_shipment_back(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, COURIER_A)
    order, shipment = await add_paid_order(db_session)
    # The order was cancelled behind our back; it is no longer claimable even though the
    # shipment still sits in the pool.
    order.status = OrderStatus.cancelled
    await db_session.commit()

    response = await act(client, "claim", shipment.id, COURIER_A)

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_state"
    assert await state(db_session, shipment, order) == (
        ShipmentStatus.processing,
        OrderStatus.cancelled,
        None,
    )


async def location_count(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(CourierLocation)) or 0


async def test_position_survives_until_the_last_active_delivery_ends(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, COURIER_A)
    first = (await add_paid_order(db_session))[1]
    second = (await add_paid_order(db_session))[1]
    for shipment in (first, second):
        await act(client, "claim", shipment.id, COURIER_A)
        await act(client, "pickup", shipment.id, COURIER_A)
    db_session.add(CourierLocation(courier_id=courier.id, latitude=52.5, longitude=13.4))
    await db_session.commit()

    await act(client, "deliver", first.id, COURIER_A)
    assert await location_count(db_session) == 1

    await act(client, "deliver", second.id, COURIER_A)
    assert await location_count(db_session) == 0


async def test_releasing_the_last_delivery_removes_the_position(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, COURIER_A)
    _, shipment = await add_paid_order(db_session)
    await act(client, "claim", shipment.id, COURIER_A)
    db_session.add(CourierLocation(courier_id=courier.id, latitude=52.5, longitude=13.4))
    await db_session.commit()

    await act(client, "release", shipment.id, COURIER_A)

    assert await location_count(db_session) == 0


async def test_a_leftover_position_from_an_idle_courier_is_dropped_on_claim(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, COURIER_A)
    _, shipment = await add_paid_order(db_session)
    db_session.add(CourierLocation(courier_id=courier.id, latitude=1.0, longitude=2.0))
    await db_session.commit()

    await act(client, "claim", shipment.id, COURIER_A)

    assert await location_count(db_session) == 0


async def test_another_couriers_position_is_untouched(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, COURIER_A)
    other = await add_courier(db_session, COURIER_B)
    _, shipment = await add_paid_order(db_session)
    db_session.add(CourierLocation(courier_id=other.id, latitude=1.0, longitude=2.0))
    await db_session.commit()

    await act(client, "claim", shipment.id, COURIER_A)
    await act(client, "release", shipment.id, COURIER_A)

    assert await location_count(db_session) == 1


COURIER_ENDPOINTS = [
    ("GET", "/courier/pool"),
    ("GET", "/courier/deliveries"),
    ("POST", "/courier/deliveries/1/claim"),
    ("POST", "/courier/deliveries/1/release"),
    ("POST", "/courier/deliveries/1/pickup"),
    ("POST", "/courier/deliveries/1/deliver"),
]


@pytest.mark.parametrize(("method", "path"), COURIER_ENDPOINTS)
async def test_every_courier_endpoint_requires_a_telegram_login(
    client: AsyncClient, method: str, path: str
) -> None:
    assert (await client.request(method, path)).status_code == 401


@pytest.mark.parametrize(("method", "path"), COURIER_ENDPOINTS)
async def test_every_courier_endpoint_rejects_customers(
    client: AsyncClient, method: str, path: str
) -> None:
    response = await client.request(method, path, headers=tma_headers(810_900))

    assert response.status_code == 403


@pytest.mark.parametrize(("method", "path"), COURIER_ENDPOINTS)
async def test_every_courier_endpoint_rejects_deactivated_couriers(
    client: AsyncClient, db_session: AsyncSession, method: str, path: str
) -> None:
    await add_courier(db_session, 810_901, is_active=False)

    response = await client.request(method, path, headers=tma_headers(810_901))

    assert response.status_code == 403
