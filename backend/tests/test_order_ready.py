"""Spec 10 §4: a paid order waits for its seller's "Ready for pickup" before couriers see it."""

import itertools

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.enums import AdminRole, OrderStatus, ShipmentStatus
from app.models.notification import Notification
from app.models.order import Order
from app.models.shipment import Shipment
from app.services import order_service
from tests.admin_factories import add_admin, admin_tma
from tests.courier_factories import add_courier, add_customer, add_paid_order, tma_headers
from tests.factories import add_seller

WEBAPP = "https://shop.example.com/"
COURIER = 890_001
_ids = itertools.count(890_100)


@pytest.fixture(autouse=True)
def _webapp_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "webapp_url", WEBAPP)


async def _shop(db: AsyncSession, name: str = "Lola Beauty") -> tuple[int, int]:
    """A seller with one account; returns (seller id, the account's Telegram id)."""
    seller = await add_seller(db, name, pickup_address="Tashkent, Chilonzor 5")
    telegram_id = next(_ids)
    await add_admin(db, telegram_id, AdminRole.seller, seller_id=seller.id)
    return seller.id, telegram_id


async def _waiting_order(db: AsyncSession, seller_id: int) -> tuple[Order, Shipment]:
    await add_customer(db, COURIER)
    await add_courier(db, COURIER, name="Bekzod")
    return await add_paid_order(
        db, customer_id=next(_ids), seller_id=seller_id, ready=False, city="Tashkent"
    )


async def _pool(client: AsyncClient) -> list[int]:
    response = await client.get("/courier/pool", headers=tma_headers(COURIER))
    return [item["order_id"] for item in response.json()]


async def _texts(db: AsyncSession, chat_id: int) -> list[str]:
    rows = await db.execute(
        select(Notification.text)
        .where(Notification.chat_id == chat_id)
        .order_by(Notification.id)
        .execution_options(populate_existing=True)
    )
    return list(rows.scalars())


async def test_a_paid_order_waits_for_its_seller(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seller_id, _ = await _shop(db_session)
    order, shipment = await _waiting_order(db_session, seller_id)

    assert order.id not in await _pool(client)
    claim = await client.post(
        f"/courier/deliveries/{shipment.id}/claim", headers=tma_headers(COURIER)
    )
    assert claim.status_code == 404


async def test_the_seller_marks_it_ready_and_the_couriers_are_told(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seller_id, account = await _shop(db_session)
    order, shipment = await _waiting_order(db_session, seller_id)

    response = await client.post(f"/internal/orders/{order.id}/ready", headers=admin_tma(account))

    assert response.status_code == 200, response.text
    assert response.json()["order_id"] == order.id
    assert response.json()["ready_at"] is not None
    assert order.id in await _pool(client)
    (text,) = await _texts(db_session, COURIER)
    assert text.startswith("New order in the pool: Tashkent")
    assert text.endswith("Pickup: Lola Beauty, Tashkent, Chilonzor 5.")
    claim = await client.post(
        f"/courier/deliveries/{shipment.id}/claim", headers=tma_headers(COURIER)
    )
    assert claim.status_code == 200


async def test_ready_twice_is_harmless(client: AsyncClient, db_session: AsyncSession) -> None:
    seller_id, account = await _shop(db_session)
    order, _ = await _waiting_order(db_session, seller_id)

    first = await client.post(f"/internal/orders/{order.id}/ready", headers=admin_tma(account))
    second = await client.post(f"/internal/orders/{order.id}/ready", headers=admin_tma(account))

    assert second.status_code == 200
    assert second.json()["ready_at"] == first.json()["ready_at"]
    assert len(await _texts(db_session, COURIER)) == 1


async def test_another_sellers_order_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seller_id, _ = await _shop(db_session)
    _, stranger = await _shop(db_session, "Anor")
    order, _ = await _waiting_order(db_session, seller_id)

    response = await client.post(f"/internal/orders/{order.id}/ready", headers=admin_tma(stranger))

    assert response.status_code == 404
    assert order.id not in await _pool(client)


async def test_the_platform_may_mark_an_order_ready(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seller_id, _ = await _shop(db_session)
    order, _ = await _waiting_order(db_session, seller_id)
    dispatcher = next(_ids)
    await add_admin(db_session, dispatcher, AdminRole.dispatcher)

    response = await client.post(
        f"/internal/orders/{order.id}/ready", headers=admin_tma(dispatcher)
    )

    assert response.status_code == 200


async def test_roles_without_orders_prepare_are_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seller_id, _ = await _shop(db_session)
    order, _ = await _waiting_order(db_session, seller_id)
    catalog_manager = next(_ids)
    await add_admin(db_session, catalog_manager, AdminRole.catalog_manager)

    response = await client.post(
        f"/internal/orders/{order.id}/ready", headers=admin_tma(catalog_manager)
    )

    assert response.status_code == 403


async def test_a_cancelled_order_cannot_be_made_ready(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    seller_id, account = await _shop(db_session)
    order, shipment = await _waiting_order(db_session, seller_id)
    await db_session.execute(
        update(Shipment).where(Shipment.id == shipment.id).values(status=ShipmentStatus.cancelled)
    )
    await db_session.execute(
        update(Order).where(Order.id == order.id).values(status=OrderStatus.cancelled)
    )
    await db_session.commit()

    response = await client.post(f"/internal/orders/{order.id}/ready", headers=admin_tma(account))

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_state"


async def test_payment_tells_the_seller_and_not_yet_the_couriers(
    db_session: AsyncSession,
) -> None:
    seller_id, account = await _shop(db_session)
    order, shipment = await _waiting_order(db_session, seller_id)
    # Back to unpaid, as the payment webhook finds it.
    await db_session.execute(delete(Shipment).where(Shipment.id == shipment.id))
    await db_session.execute(
        update(Order).where(Order.id == order.id).values(status=OrderStatus.pending_payment)
    )
    await db_session.commit()

    await order_service.mark_order_paid(db_session, order.id)

    assert await _texts(db_session, account) == [
        f"New order #{order.id}: 1 item. Collect it and press Ready, then a courier comes."
    ]
    assert await _texts(db_session, COURIER) == []
    message = await db_session.scalar(select(Notification).where(Notification.chat_id == account))
    assert message is not None and message.reply_markup is not None
    url = message.reply_markup["inline_keyboard"][0][0]["web_app"]["url"]
    assert url == f"{WEBAPP}admin/orders/{order.id}"
    ready_at = await db_session.scalar(
        select(Shipment.ready_at).where(Shipment.order_id == order.id)
    )
    assert ready_at is None
