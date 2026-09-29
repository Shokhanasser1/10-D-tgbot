"""Stock reservation at checkout, expiry of unpaid orders, and late payments (Spec 4)."""

import asyncio
import itertools
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
import stripe
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.money import to_minor_units
from app.models.cart import Cart, CartItem
from app.models.category import Category
from app.models.enums import (
    CartStatus,
    OrderStatus,
    PaymentStatus,
    ProductStatus,
    RefundStatus,
)
from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.models.shipment import Shipment
from app.models.variant import Variant
from app.services import reservation_service, stripe_service
from tests.factories import make_init_data

ADDRESS = {
    "street": "Amir Temur 1",
    "city": "Tashkent",
    "postal_code": "100000",
    "country": "UZ",
    "phone": "+998901234567",
}
_seq = itertools.count(1)


def _headers(telegram_id: int) -> dict[str, str]:
    return {"Authorization": f"tma {make_init_data(telegram_id=telegram_id)}"}


class FakeStripe:
    """PaymentIntents, cancellation and refunds without the network."""

    def __init__(self) -> None:
        self.intents = 0
        self.fail_create = False
        self.cancel_answer: bool | Exception = True
        self.cancelled: list[str] = []
        self.refunds: list[dict] = []

    async def create_payment_intent(self, amount: Decimal, currency: str, metadata: dict):
        if self.fail_create:
            raise stripe.APIConnectionError("network down")
        self.intents += 1
        pi = f"pi_res_{next(_seq)}"
        return SimpleNamespace(
            id=pi, amount=to_minor_units(amount), client_secret=f"{pi}_secret", metadata=metadata
        )

    async def cancel_payment_intent(self, payment_intent_id: str) -> bool:
        self.cancelled.append(payment_intent_id)
        if isinstance(self.cancel_answer, Exception):
            raise self.cancel_answer
        return self.cancel_answer

    async def create_refund(self, payment_intent_id: str, idempotency_key: str, metadata: dict):
        self.refunds.append({"payment_intent": payment_intent_id, "key": idempotency_key})
        return SimpleNamespace(id=f"re_{len(self.refunds)}", status="pending")


@pytest.fixture
def fake_stripe(monkeypatch: pytest.MonkeyPatch) -> FakeStripe:
    fake = FakeStripe()
    for name in ("create_payment_intent", "cancel_payment_intent", "create_refund"):
        monkeypatch.setattr(stripe_service, name, getattr(fake, name))
    return fake


async def _variant(
    db: AsyncSession, *, stock: int, price: str = "10.00", status=ProductStatus.active
) -> Variant:
    n = next(_seq)
    category = Category(slug=f"res-cat-{n}", sort_order=0)
    db.add(category)
    await db.flush()
    product = Product(
        category_id=category.id, base_sku=f"RES-{n}", base_price=Decimal(price), status=status
    )
    db.add(product)
    await db.flush()
    variant = Variant(
        product_id=product.id, sku=f"RES-{n}-V", price=Decimal(price), stock_qty=stock
    )
    db.add(variant)
    await db.commit()
    return variant


async def _stock(db: AsyncSession, variant_id: int) -> int:
    return await db.scalar(select(Variant.stock_qty).where(Variant.id == variant_id))


async def _order(db: AsyncSession, order_id: int) -> Order:
    return (
        await db.execute(
            select(Order).where(Order.id == order_id).execution_options(populate_existing=True)
        )
    ).scalar_one()


async def _cart_lines(db: AsyncSession, telegram_id: int) -> dict[int, int]:
    rows = await db.execute(
        select(CartItem.variant_id, CartItem.qty)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(Cart.telegram_id == telegram_id, Cart.status == CartStatus.active)
        .execution_options(populate_existing=True)
    )
    return dict(rows.all())


async def _checkout(client: AsyncClient, telegram_id: int, lines: list[tuple[int, int]]):
    headers = _headers(telegram_id)
    for variant_id, qty in lines:
        added = await client.post(
            "/cart/items", json={"variant_id": variant_id, "qty": qty}, headers=headers
        )
        assert added.status_code in (200, 201), added.text
    return await client.post("/checkout", json={"delivery_address": ADDRESS}, headers=headers)


async def _make_overdue(db: AsyncSession, order_id: int) -> None:
    await db.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(reserved_until=datetime.now(UTC) - timedelta(hours=1))
    )
    await db.commit()


def _session_factory(db: AsyncSession) -> Callable[[], AsyncSession]:
    """Fresh sessions on the test's connection, so the sweeper's commits stay in its savepoints."""
    return lambda: AsyncSession(
        bind=db.bind, join_transaction_mode="create_savepoint", expire_on_commit=False
    )


# --- checkout --------------------------------------------------------------------------------


async def test_checkout_reserves_stock_and_sets_a_deadline(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    variant = await _variant(db_session, stock=5)

    before = datetime.now(UTC)
    response = await _checkout(client, 4101, [(variant.id, 2)])

    assert response.status_code == 200
    order = await _order(db_session, response.json()["order_id"])
    assert order.status == OrderStatus.pending_payment
    ttl = timedelta(minutes=get_settings().reservation_ttl_minutes)
    assert (
        before + ttl - timedelta(seconds=5)
        < order.reserved_until
        < before + ttl + timedelta(minutes=1)
    )
    assert await _stock(db_session, variant.id) == 3
    assert await _cart_lines(db_session, 4101) == {}


async def test_checkout_short_line_is_409_and_changes_nothing(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    plenty = await _variant(db_session, stock=5)
    scarce = await _variant(db_session, stock=2)
    plenty_id, scarce_id, scarce_sku = plenty.id, scarce.id, scarce.sku  # survive a rollback
    headers = _headers(4102)
    await client.post("/cart/items", json={"variant_id": plenty_id, "qty": 1}, headers=headers)
    await client.post("/cart/items", json={"variant_id": scarce_id, "qty": 2}, headers=headers)
    await db_session.execute(update(Variant).where(Variant.id == scarce_id).values(stock_qty=1))
    await db_session.commit()

    response = await client.post("/checkout", json={"delivery_address": ADDRESS}, headers=headers)

    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_stock"
    assert scarce_sku in response.json()["detail"]
    assert await _stock(db_session, plenty_id) == 5
    assert await _stock(db_session, scarce_id) == 1
    assert await _cart_lines(db_session, 4102) == {plenty_id: 1, scarce_id: 2}
    assert await db_session.scalar(select(Order.id).where(Order.telegram_id == 4102)) is None
    assert fake_stripe.intents == 0


async def test_stripe_failure_at_checkout_returns_stock_and_cart(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    variant = await _variant(db_session, stock=5)
    fake_stripe.fail_create = True

    with pytest.raises(stripe.APIConnectionError):
        await _checkout(client, 4103, [(variant.id, 2)])

    order_id = await db_session.scalar(select(Order.id).where(Order.telegram_id == 4103))
    order = await _order(db_session, order_id)
    assert order.status == OrderStatus.cancelled
    assert order.cancel_reason == reservation_service.SETUP_FAILED_REASON
    assert await _stock(db_session, variant.id) == 5
    assert await _cart_lines(db_session, 4103) == {variant.id: 2}


# --- expiry ----------------------------------------------------------------------------------


async def _pending(
    client: AsyncClient, db: AsyncSession, telegram_id: int, stock: int = 5, qty: int = 2
) -> tuple[int, Variant]:
    variant = await _variant(db, stock=stock)
    response = await _checkout(client, telegram_id, [(variant.id, qty)])
    assert response.status_code == 200, response.text
    return response.json()["order_id"], variant


async def test_expire_order_cancels_payment_returns_stock_and_cart(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    order_id, variant = await _pending(client, db_session, 4201)
    await _make_overdue(db_session, order_id)

    assert await reservation_service.expire_order(db_session, order_id) is True

    order = await _order(db_session, order_id)
    assert order.status == OrderStatus.cancelled
    assert order.cancel_reason == "payment_expired"
    assert order.cancelled_at is not None
    assert order.cancelled_by is None
    assert len(fake_stripe.cancelled) == 1
    payment = await db_session.scalar(
        select(Payment.status)
        .where(Payment.order_id == order_id)
        .execution_options(populate_existing=True)
    )
    assert payment == PaymentStatus.canceled
    assert await _stock(db_session, variant.id) == 5
    assert await _cart_lines(db_session, 4201) == {variant.id: 2}


async def test_expired_items_merge_into_an_existing_cart_and_skip_archived_products(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    kept = await _variant(db_session, stock=5)
    archived = await _variant(db_session, stock=5)
    response = await _checkout(client, 4202, [(kept.id, 2), (archived.id, 1)])
    order_id = response.json()["order_id"]
    # Meanwhile the customer started a new cart with one more of the same item.
    await client.post("/cart/items", json={"variant_id": kept.id, "qty": 1}, headers=_headers(4202))
    await db_session.execute(
        update(Product)
        .where(Product.id == archived.product_id)
        .values(status=ProductStatus.archived)
    )
    await _make_overdue(db_session, order_id)

    assert await reservation_service.expire_order(db_session, order_id) is True

    assert await _cart_lines(db_session, 4202) == {kept.id: 3}
    assert await _stock(db_session, archived.id) == 5  # stock still goes back


async def test_expire_leaves_an_order_whose_payment_already_went_through(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    order_id, variant = await _pending(client, db_session, 4203)
    await _make_overdue(db_session, order_id)
    fake_stripe.cancel_answer = False  # Stripe: already succeeded / processing

    assert await reservation_service.expire_order(db_session, order_id) is False

    assert (await _order(db_session, order_id)).status == OrderStatus.pending_payment
    assert await _stock(db_session, variant.id) == 3


async def test_expire_retries_later_on_a_stripe_error(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    order_id, variant = await _pending(client, db_session, 4204)
    await _make_overdue(db_session, order_id)
    fake_stripe.cancel_answer = stripe.APIConnectionError("network down")

    assert await reservation_service.expire_order(db_session, order_id) is False

    assert (await _order(db_session, order_id)).status == OrderStatus.pending_payment
    assert await _stock(db_session, variant.id) == 3


async def test_expire_ignores_an_order_that_is_not_due_yet(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    order_id, variant = await _pending(client, db_session, 4205)

    assert await reservation_service.expire_order(db_session, order_id) is False

    assert fake_stripe.cancelled == []
    assert (await _order(db_session, order_id)).status == OrderStatus.pending_payment
    assert await _stock(db_session, variant.id) == 3


async def test_expiring_twice_returns_stock_only_once(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    order_id, variant = await _pending(client, db_session, 4206)
    await _make_overdue(db_session, order_id)

    assert await reservation_service.expire_order(db_session, order_id) is True
    assert await reservation_service.expire_order(db_session, order_id) is False

    assert await _stock(db_session, variant.id) == 5
    assert await _cart_lines(db_session, 4206) == {variant.id: 2}


async def test_expire_order_without_a_payment_row(
    db_session: AsyncSession, fake_stripe: FakeStripe, client: AsyncClient
) -> None:
    """The process died between reserving and recording the payment."""
    order_id, variant = await _pending(client, db_session, 4207)
    await db_session.execute(Payment.__table__.delete().where(Payment.order_id == order_id))
    await _make_overdue(db_session, order_id)

    assert await reservation_service.expire_order(db_session, order_id) is True

    assert fake_stripe.cancelled == []
    assert await _stock(db_session, variant.id) == 5


async def test_sweep_expires_due_orders_and_survives_a_failing_one(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken_id, _ = await _pending(client, db_session, 4208)
    good_id, good_variant = await _pending(client, db_session, 4209)
    fresh_id, _ = await _pending(client, db_session, 4210)
    await _make_overdue(db_session, broken_id)
    await _make_overdue(db_session, good_id)

    real_expire = reservation_service.expire_order

    async def flaky_expire(db: AsyncSession, order_id: int) -> bool:
        if order_id == broken_id:
            raise RuntimeError("boom")
        return await real_expire(db, order_id)

    monkeypatch.setattr(reservation_service, "expire_order", flaky_expire)

    assert await reservation_service.sweep_once(_session_factory(db_session)) == 1

    assert (await _order(db_session, good_id)).status == OrderStatus.cancelled
    assert await _stock(db_session, good_variant.id) == 5
    assert (await _order(db_session, broken_id)).status == OrderStatus.pending_payment
    assert (await _order(db_session, fresh_id)).status == OrderStatus.pending_payment


async def test_the_sweeper_loop_keeps_going_after_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def failing_sweep(factory) -> int:
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise asyncio.CancelledError
        raise RuntimeError("database down")

    monkeypatch.setattr(reservation_service, "sweep_once", failing_sweep)

    with pytest.raises(asyncio.CancelledError):
        await reservation_service.run_sweeper(lambda: None, 0)
    assert calls == 2


# --- payment ---------------------------------------------------------------------------------


@pytest.fixture
def pay(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    async def _pay(order_id: int) -> None:
        event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi", "metadata": {"order_id": str(order_id)}}},
        }
        monkeypatch.setattr(stripe_service, "construct_webhook_event", lambda payload, sig: event)
        response = await client.post(
            "/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t"}
        )
        assert response.status_code == 200

    return _pay


async def test_paying_a_reserved_order_does_not_take_stock_again(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe, pay
) -> None:
    order_id, variant = await _pending(client, db_session, 4301, stock=2, qty=2)

    await pay(order_id)

    order = await _order(db_session, order_id)
    assert order.status == OrderStatus.paid
    assert order.stock_shortfall is False
    assert await _stock(db_session, variant.id) == 0
    assert await db_session.scalar(select(Shipment.id).where(Shipment.order_id == order_id))


async def test_payment_after_expiry_is_refunded_once(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe, pay
) -> None:
    order_id, variant = await _pending(client, db_session, 4302)
    await _make_overdue(db_session, order_id)
    await reservation_service.expire_order(db_session, order_id)

    await pay(order_id)
    await pay(order_id)  # Stripe redelivers

    order = await _order(db_session, order_id)
    assert order.status == OrderStatus.cancelled
    assert [r["key"] for r in fake_stripe.refunds] == [f"late-payment-{order_id}"]
    payment = (
        await db_session.execute(
            select(Payment)
            .where(Payment.order_id == order_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert payment.status == PaymentStatus.succeeded
    assert payment.refund_status == RefundStatus.pending
    assert payment.stripe_refund_id == "re_1"
    assert await _stock(db_session, variant.id) == 5  # returned once, on expiry
    assert await db_session.scalar(select(Shipment.id).where(Shipment.order_id == order_id)) is None


async def test_order_detail_shows_the_deadline_and_the_expiry_reason(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    order_id, _ = await _pending(client, db_session, 4303)

    pending = (await client.get(f"/orders/{order_id}", headers=_headers(4303))).json()
    assert pending["reserved_until"] is not None
    assert pending["cancel_reason"] is None

    await _make_overdue(db_session, order_id)
    await reservation_service.expire_order(db_session, order_id)

    expired = (await client.get(f"/orders/{order_id}", headers=_headers(4303))).json()
    assert expired["status"] == "cancelled"
    assert expired["cancel_reason"] == "payment_expired"
    assert expired["payment_status"] == "canceled"
    assert expired["refund_status"] is None


# --- the Stripe wrapper ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cancel", "retrieved", "expected"),
    [
        ("canceled", None, True),  # cancelled now
        (stripe.InvalidRequestError("finished", None), "canceled", True),  # already cancelled
        (stripe.InvalidRequestError("finished", None), "succeeded", False),  # paid meanwhile
        (stripe.InvalidRequestError("finished", None), "processing", False),
    ],
)
async def test_cancel_payment_intent_reports_whether_it_can_still_be_paid(
    monkeypatch: pytest.MonkeyPatch, cancel, retrieved, expected
) -> None:
    async def _cancel(payment_intent_id: str):
        if isinstance(cancel, Exception):
            raise cancel
        return SimpleNamespace(status=cancel)

    async def _retrieve(payment_intent_id: str):
        return SimpleNamespace(status=retrieved)

    monkeypatch.setattr(stripe.PaymentIntent, "cancel_async", _cancel)
    monkeypatch.setattr(stripe.PaymentIntent, "retrieve_async", _retrieve)

    assert await stripe_service.cancel_payment_intent("pi_x") is expected


async def test_cancel_payment_intent_lets_network_errors_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _cancel(payment_intent_id: str):
        raise stripe.APIConnectionError("network down")

    monkeypatch.setattr(stripe.PaymentIntent, "cancel_async", _cancel)

    with pytest.raises(stripe.APIConnectionError):
        await stripe_service.cancel_payment_intent("pi_x")
