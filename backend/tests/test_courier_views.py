import json
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.courier import CourierLocation
from app.models.enums import OrderStatus, ShipmentStatus
from tests.courier_factories import add_courier, add_paid_order, tma_headers

COURIER_A = 820_001
COURIER_B = 820_002

POOL_KEYS = {"shipment_id", "order_id", "city", "street", "item_count", "placed_at"}
MONEY_KEYS = {"total", "subtotal", "shipping_cost", "unit_price_snapshot", "price", "amount"}


async def get_pool(client: AsyncClient, tid: int = COURIER_A) -> list[dict]:
    response = await client.get("/courier/pool", headers=tma_headers(tid))
    assert response.status_code == 200
    return response.json()


async def get_deliveries(client: AsyncClient, tid: int = COURIER_A) -> dict:
    response = await client.get("/courier/deliveries", headers=tma_headers(tid))
    assert response.status_code == 200
    return response.json()


def all_keys(node: object) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {key for value in node.values() for key in all_keys(value)}
    if isinstance(node, list):
        return {key for value in node for key in all_keys(value)}
    return set()


async def test_pool_shows_only_unclaimed_paid_orders(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, COURIER_A)
    await add_courier(db_session, COURIER_B)
    open_order, open_shipment = await add_paid_order(db_session)
    _, taken = await add_paid_order(db_session)
    _, delivered = await add_paid_order(db_session)
    cancelled_order, cancelled = await add_paid_order(db_session)
    await client.post(f"/courier/deliveries/{taken.id}/claim", headers=tma_headers(COURIER_B))
    delivered.status = ShipmentStatus.delivered
    cancelled_order.status = OrderStatus.cancelled
    await db_session.commit()

    pool = await get_pool(client)

    assert [item["shipment_id"] for item in pool] == [open_shipment.id]
    assert pool[0]["order_id"] == open_order.id
    assert cancelled.id not in {item["shipment_id"] for item in pool}


async def test_pool_reveals_only_what_is_needed_to_choose_an_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, COURIER_A)
    await add_paid_order(
        db_session, qty=3, city="Hamburg", street="Reeperbahn 5", pin=(53.55, 9.99), notes="secret"
    )

    (item,) = await get_pool(client)

    assert set(item) == POOL_KEYS
    assert (item["city"], item["street"], item["item_count"]) == ("Hamburg", "Reeperbahn 5", 3)
    body = json.dumps(item)
    for private in ("+491234567", "secret", "53.55", "9.99", "10178"):
        assert private not in body


async def test_pool_is_oldest_first(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_courier(db_session, COURIER_A)
    shipments = [(await add_paid_order(db_session))[1] for _ in range(3)]
    for shipment, day in zip(shipments, (3, 1, 2), strict=True):
        shipment.created_at = datetime(2026, 1, day, tzinfo=UTC)
    await db_session.commit()

    pool = await get_pool(client)

    assert [item["shipment_id"] for item in pool] == [
        shipments[1].id,
        shipments[2].id,
        shipments[0].id,
    ]


async def test_a_released_order_is_back_in_the_pool(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, COURIER_A)
    _, shipment = await add_paid_order(db_session)
    await client.post(f"/courier/deliveries/{shipment.id}/claim", headers=tma_headers(COURIER_A))
    assert await get_pool(client) == []

    await client.post(f"/courier/deliveries/{shipment.id}/release", headers=tma_headers(COURIER_A))

    assert [item["shipment_id"] for item in await get_pool(client)] == [shipment.id]


async def test_deliveries_are_only_the_callers_active_ones(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, COURIER_A)
    await add_courier(db_session, COURIER_B)
    _, mine = await add_paid_order(db_session)
    _, finished = await add_paid_order(db_session)
    _, theirs = await add_paid_order(db_session)
    _, unclaimed = await add_paid_order(db_session)
    for shipment in (mine, finished):
        await client.post(
            f"/courier/deliveries/{shipment.id}/claim", headers=tma_headers(COURIER_A)
        )
    await client.post(f"/courier/deliveries/{theirs.id}/claim", headers=tma_headers(COURIER_B))
    for step in ("pickup", "deliver"):
        await client.post(
            f"/courier/deliveries/{finished.id}/{step}", headers=tma_headers(COURIER_A)
        )

    body = await get_deliveries(client)

    assert [d["shipment_id"] for d in body["deliveries"]] == [mine.id]
    assert unclaimed.id not in {d["shipment_id"] for d in body["deliveries"]}


async def test_a_delivery_carries_everything_the_courier_needs(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, COURIER_A)
    order, shipment = await add_paid_order(
        db_session, qty=2, pin=(52.52, 13.405), notes="Ring twice"
    )
    await client.post(f"/courier/deliveries/{shipment.id}/claim", headers=tma_headers(COURIER_A))

    (delivery,) = (await get_deliveries(client))["deliveries"]

    assert delivery["order_id"] == order.id
    assert delivery["status"] == "assigned"
    assert delivery["address"] == {
        "street": "Alexanderplatz 1",
        "city": "Berlin",
        "postal_code": "10178",
        "country": "DE",
        "phone": "+491234567",
        "notes": "Ring twice",
    }
    assert delivery["items"] == [{"name": "Velvet Lipstick", "qty": 2}]
    assert delivery["destination"] == {"latitude": 52.52, "longitude": 13.405}
    assert delivery["assigned_at"] is not None and delivery["picked_up_at"] is None


async def test_destination_is_null_when_the_customer_set_no_pin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, COURIER_A)
    _, shipment = await add_paid_order(db_session, pin=None)
    await client.post(f"/courier/deliveries/{shipment.id}/claim", headers=tma_headers(COURIER_A))

    (delivery,) = (await get_deliveries(client))["deliveries"]

    assert delivery["destination"] is None


async def test_deliveries_expose_no_money_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_courier(db_session, COURIER_A)
    _, shipment = await add_paid_order(db_session)
    await client.post(f"/courier/deliveries/{shipment.id}/claim", headers=tma_headers(COURIER_A))

    body = await get_deliveries(client)

    assert set(body) == {"location_updated_at", "deliveries"}
    assert not (all_keys(body) & MONEY_KEYS)


async def test_location_age_is_reported_but_the_position_is_not_echoed_back(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    courier = await add_courier(db_session, COURIER_A)
    _, shipment = await add_paid_order(db_session)
    await client.post(f"/courier/deliveries/{shipment.id}/claim", headers=tma_headers(COURIER_A))
    assert (await get_deliveries(client))["location_updated_at"] is None

    db_session.add(CourierLocation(courier_id=courier.id, latitude=41.123456, longitude=29.654321))
    await db_session.commit()
    body = await get_deliveries(client)

    assert body["location_updated_at"] is not None
    assert "41.123456" not in json.dumps(body) and "29.654321" not in json.dumps(body)
