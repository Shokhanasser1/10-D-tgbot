"""Spec 10 §7: the platform sees each order's seller and readiness; couriers see the pickup."""

import itertools

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.courier_factories import (
    INTERNAL_HEADERS,
    add_courier,
    add_customer,
    add_paid_order,
    tma_headers,
)
from tests.factories import add_seller

_ids = itertools.count(897_001)


async def _lola(db: AsyncSession) -> int:
    seller = await add_seller(db, "Lola Beauty", pickup_address="Tashkent, Chilonzor 5")
    seller.phone = "+998901112233"
    await db.commit()
    return seller.id


async def test_the_order_list_shows_seller_and_readiness_and_filters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    lola = await _lola(db_session)
    anor = (await add_seller(db_session, "Anor")).id
    waiting, _ = await add_paid_order(
        db_session, customer_id=next(_ids), seller_id=lola, ready=False
    )
    await add_paid_order(db_session, customer_id=next(_ids), seller_id=anor)

    page = (
        await client.get("/internal/orders", params={"seller_id": lola}, headers=INTERNAL_HEADERS)
    ).json()

    (item,) = page["items"]
    assert (item["id"], item["seller_id"], item["seller_name"], item["ready_at"]) == (
        waiting.id,
        lola,
        "Lola Beauty",
        None,
    )


async def test_the_order_page_shows_the_seller_and_offers_mark_ready(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    lola = await _lola(db_session)
    waiting, _ = await add_paid_order(
        db_session, customer_id=next(_ids), seller_id=lola, ready=False
    )
    ready, _ = await add_paid_order(db_session, customer_id=next(_ids), seller_id=lola)

    detail = (await client.get(f"/internal/orders/{waiting.id}", headers=INTERNAL_HEADERS)).json()
    done = (await client.get(f"/internal/orders/{ready.id}", headers=INTERNAL_HEADERS)).json()

    assert detail["seller"] == {
        "id": lola,
        "name": "Lola Beauty",
        "phone": "+998901112233",
        "pickup_address": "Tashkent, Chilonzor 5",
    }
    assert (detail["shipment"]["ready_at"], detail["can_mark_ready"]) == (None, True)
    assert done["shipment"]["ready_at"] is not None
    assert done["can_mark_ready"] is False


async def test_couriers_see_where_to_collect(client: AsyncClient, db_session: AsyncSession) -> None:
    lola = await _lola(db_session)
    courier_tid = next(_ids)
    await add_customer(db_session, courier_tid)
    courier = await add_courier(db_session, courier_tid)
    order, shipment = await add_paid_order(db_session, customer_id=next(_ids), seller_id=lola)
    pickup = {"name": "Lola Beauty", "address": "Tashkent, Chilonzor 5", "phone": "+998901112233"}

    pool = (await client.get("/courier/pool", headers=tma_headers(courier_tid))).json()
    (item,) = [p for p in pool if p["order_id"] == order.id]
    assert item["pickup"] == pickup

    claim = await client.post(
        f"/courier/deliveries/{shipment.id}/claim", headers=tma_headers(courier.telegram_id)
    )
    assert claim.status_code == 200
    deliveries = (await client.get("/courier/deliveries", headers=tma_headers(courier_tid))).json()[
        "deliveries"
    ]
    (delivery,) = [d for d in deliveries if d["order_id"] == order.id]
    assert delivery["pickup"] == pickup
