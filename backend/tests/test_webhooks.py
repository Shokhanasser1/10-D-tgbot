from decimal import Decimal

import pytest
import stripe
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.enums import OrderStatus, PaymentStatus, ShipmentStatus
from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.models.shipment import Shipment
from app.services import stripe_service
from tests.courier_factories import add_courier, add_paid_order


def _make_event(event_type: str, order_id: int, payment_intent_id: str = "pi_test_wh") -> dict:
    return {
        "type": event_type,
        "data": {
            "object": {
                "id": payment_intent_id,
                "metadata": {"order_id": str(order_id)},
            }
        },
    }


@pytest.fixture
def patch_construct_event(monkeypatch: pytest.MonkeyPatch):
    def _patch(event: dict) -> None:
        monkeypatch.setattr(stripe_service, "construct_webhook_event", lambda payload, sig: event)

    return _patch


async def _make_pending_order(db_session: AsyncSession, telegram_id: int) -> Order:
    category = Category(slug=f"wh-cat-{telegram_id}", sort_order=0)
    db_session.add(category)
    await db_session.flush()
    product = Product(
        category_id=category.id, base_sku=f"WH-{telegram_id}", base_price=Decimal("10.00")
    )
    db_session.add(product)

    from app.models.telegram_user import TelegramUser

    if await db_session.get(TelegramUser, telegram_id) is None:
        db_session.add(TelegramUser(telegram_id=telegram_id, locale="en"))

    await db_session.flush()

    order = Order(
        telegram_id=telegram_id,
        status=OrderStatus.pending_payment,
        currency="EUR",
        subtotal=Decimal("10.00"),
        shipping_cost=Decimal("4.99"),
        total=Decimal("14.99"),
        delivery_address={"city": "Berlin"},
    )
    db_session.add(order)
    await db_session.flush()

    db_session.add(
        Payment(
            order_id=order.id,
            stripe_payment_intent_id="pi_test_wh",
            status=PaymentStatus.requires_payment_method,
            amount=Decimal("14.99"),
            currency="EUR",
        )
    )
    await db_session.commit()
    await db_session.refresh(order)
    return order


async def test_payment_succeeded_marks_order_paid_and_creates_shipment(
    client: AsyncClient, db_session: AsyncSession, patch_construct_event
) -> None:
    order = await _make_pending_order(db_session, telegram_id=4001)
    patch_construct_event(_make_event("payment_intent.succeeded", order.id))

    response = await client.post(
        "/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t"}
    )
    assert response.status_code == 200

    refreshed = (
        await db_session.execute(
            select(Order).where(Order.id == order.id).execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert refreshed.status == OrderStatus.paid

    shipment = (
        await db_session.execute(select(Shipment).where(Shipment.order_id == order.id))
    ).scalar_one_or_none()
    assert shipment is not None


async def test_duplicate_webhook_does_not_create_second_shipment(
    client: AsyncClient, db_session: AsyncSession, patch_construct_event
) -> None:
    order = await _make_pending_order(db_session, telegram_id=4002)
    patch_construct_event(_make_event("payment_intent.succeeded", order.id))

    await client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t"})
    await client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t"})

    stmt = select(Order).where(Order.id == order.id).execution_options(populate_existing=True)
    refreshed = (await db_session.execute(stmt)).scalar_one()
    assert refreshed.status == OrderStatus.paid


async def test_payment_failed_updates_payment_status_without_marking_paid(
    client: AsyncClient, db_session: AsyncSession, patch_construct_event
) -> None:
    order = await _make_pending_order(db_session, telegram_id=4003)
    patch_construct_event(_make_event("payment_intent.payment_failed", order.id))

    await client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t"})

    await db_session.refresh(order)
    assert order.status == OrderStatus.pending_payment


async def test_invalid_signature_returns_400(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(payload, sig):
        raise stripe.SignatureVerificationError("bad sig", sig)

    monkeypatch.setattr(stripe_service, "construct_webhook_event", _raise)

    response = await client.post(
        "/webhooks/stripe", content=b"{}", headers={"stripe-signature": "bad"}
    )
    assert response.status_code == 400


async def test_replayed_payment_event_does_not_reset_an_order_a_courier_holds(
    client: AsyncClient, db_session: AsyncSession, patch_construct_event
) -> None:
    # Stripe redelivers events. Once a courier has the order it is past "paid"; a replay must
    # not drag it back (which would also let the pool hand it to someone else).
    courier = await add_courier(db_session, 840_001)
    order, shipment = await add_paid_order(db_session, customer_id=840_002)
    shipment.status = ShipmentStatus.shipped
    shipment.courier_id = courier.id
    order.status = OrderStatus.shipped
    await db_session.commit()
    patch_construct_event(_make_event("payment_intent.succeeded", order.id))

    response = await client.post(
        "/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t"}
    )

    assert response.status_code == 200
    await db_session.refresh(order)
    await db_session.refresh(shipment)
    assert (order.status, shipment.status, shipment.courier_id) == (
        OrderStatus.shipped,
        ShipmentStatus.shipped,
        courier.id,
    )
