from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.courier import Courier, CourierLocation
from app.models.enums import OrderStatus, ShipmentStatus
from app.models.order import Order
from app.models.shipment import Shipment
from tests.courier_factories import add_courier, add_paid_order, tma_headers

CUSTOMER = 870_001
STRANGER = 870_002
COURIER = 870_003


async def track(client: AsyncClient, order_id: int, telegram_id: int = CUSTOMER):
    return await client.get(f"/orders/{order_id}/tracking", headers=tma_headers(telegram_id))


async def deliver_state(
    db: AsyncSession,
    shipment: Shipment,
    order: Order,
    courier: Courier | None,
    status: ShipmentStatus,
    order_status: OrderStatus,
) -> None:
    shipment.status = status
    shipment.courier_id = courier.id if courier else None
    order.status = order_status
    await db.commit()


async def out_for_delivery(db: AsyncSession, **order_kwargs):
    courier = await add_courier(db, COURIER, name="Ali", phone="+998901112233")
    order, shipment = await add_paid_order(db, customer_id=CUSTOMER, **order_kwargs)
    await deliver_state(db, shipment, order, courier, ShipmentStatus.shipped, OrderStatus.shipped)
    return courier, order, shipment


async def test_tracking_needs_a_telegram_login(client: AsyncClient) -> None:
    assert (await client.get("/orders/1/tracking")).status_code == 401


async def test_another_customers_order_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    order, _ = await add_paid_order(db_session, customer_id=CUSTOMER)

    assert (await track(client, order.id, STRANGER)).status_code == 404


async def test_an_unknown_order_is_not_found(client: AsyncClient) -> None:
    assert (await track(client, 999_999)).status_code == 404


async def test_an_order_with_no_shipment_yet_has_null_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    order, shipment = await add_paid_order(db_session, customer_id=CUSTOMER)
    await db_session.execute(delete(Shipment).where(Shipment.id == shipment.id))
    await db_session.commit()

    body = (await track(client, order.id)).json()

    assert body["status"] is None
    assert body["courier"] is None and body["courier_location"] is None


async def test_a_waiting_order_has_no_courier(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    order, _ = await add_paid_order(db_session, customer_id=CUSTOMER)

    body = (await track(client, order.id)).json()

    assert body["status"] == "processing"
    assert body["courier"] is None and body["courier_location"] is None


async def test_an_assigned_order_shows_the_courier_but_never_a_position(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, COURIER, name="Ali")
    order, shipment = await add_paid_order(db_session, customer_id=CUSTOMER)
    await deliver_state(
        db_session, shipment, order, courier, ShipmentStatus.assigned, OrderStatus.processing
    )
    # Even if a fix exists (the courier is on the way to the shop), it is not shared yet.
    db_session.add(CourierLocation(courier_id=courier.id, latitude=1.5, longitude=2.5))
    await db_session.commit()

    body = (await track(client, order.id)).json()

    assert body["status"] == "assigned"
    assert body["courier"] == {"name": "Ali"}
    assert body["courier_location"] is None


async def test_an_order_out_for_delivery_shares_the_couriers_fresh_position(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier, order, _ = await out_for_delivery(db_session, pin=(52.52, 13.405))
    db_session.add(CourierLocation(courier_id=courier.id, latitude=52.5, longitude=13.4))
    await db_session.commit()

    body = (await track(client, order.id)).json()

    assert body["status"] == "shipped"
    assert body["courier"] == {"name": "Ali"}
    location = body["courier_location"]
    assert (location["latitude"], location["longitude"], location["is_stale"]) == (
        52.5,
        13.4,
        False,
    )
    assert body["destination"] == {"latitude": 52.52, "longitude": 13.405}


async def test_an_old_position_is_marked_stale(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "location_stale_seconds", 120)
    courier, order, _ = await out_for_delivery(db_session)
    db_session.add(
        CourierLocation(
            courier_id=courier.id,
            latitude=52.5,
            longitude=13.4,
            updated_at=datetime.now(UTC) - timedelta(seconds=500),
        )
    )
    await db_session.commit()

    assert (await track(client, order.id)).json()["courier_location"]["is_stale"] is True


async def test_the_stale_threshold_is_configurable(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "location_stale_seconds", 1000)
    courier, order, _ = await out_for_delivery(db_session)
    db_session.add(
        CourierLocation(
            courier_id=courier.id,
            latitude=52.5,
            longitude=13.4,
            updated_at=datetime.now(UTC) - timedelta(seconds=500),
        )
    )
    await db_session.commit()

    assert (await track(client, order.id)).json()["courier_location"]["is_stale"] is False


async def test_out_for_delivery_without_a_fix_yet_has_no_position(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, order, _ = await out_for_delivery(db_session)

    body = (await track(client, order.id)).json()

    assert body["status"] == "shipped"
    assert body["courier"] == {"name": "Ali"}
    assert body["courier_location"] is None


async def test_a_delivered_order_shows_when_and_no_courier_or_position(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier, order, shipment = await out_for_delivery(db_session)
    db_session.add(CourierLocation(courier_id=courier.id, latitude=52.5, longitude=13.4))
    shipment.status = ShipmentStatus.delivered
    shipment.delivered_at = datetime.now(UTC)
    order.status = OrderStatus.delivered
    await db_session.commit()

    body = (await track(client, order.id)).json()

    assert body["status"] == "delivered"
    assert body["delivered_at"] is not None
    assert body["courier"] is None and body["courier_location"] is None


async def test_the_couriers_contact_details_and_identity_never_leak(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier, order, _ = await out_for_delivery(db_session)
    db_session.add(CourierLocation(courier_id=courier.id, latitude=52.5, longitude=13.4))
    await db_session.commit()

    raw = (await track(client, order.id)).text

    assert "998901112233" not in raw  # phone
    assert str(COURIER) not in raw  # Telegram ID
    assert '"courier_id"' not in raw


async def test_only_the_orders_own_courier_position_is_returned(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier, order, _ = await out_for_delivery(db_session)
    other = await add_courier(db_session, COURIER + 1, name="Bo")
    db_session.add_all(
        [
            CourierLocation(courier_id=courier.id, latitude=52.5, longitude=13.4),
            CourierLocation(courier_id=other.id, latitude=-33.9, longitude=151.2),
        ]
    )
    await db_session.commit()

    location = (await track(client, order.id)).json()["courier_location"]

    assert (location["latitude"], location["longitude"]) == (52.5, 13.4)


async def test_destination_is_null_when_the_customer_set_no_pin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    order, _ = await add_paid_order(db_session, customer_id=CUSTOMER, pin=None)

    assert (await track(client, order.id)).json()["destination"] is None
