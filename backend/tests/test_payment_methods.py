"""Payments in Uzbekistan (Spec 6): Telegram Payments with Click/Payme, cash on delivery."""

import itertools
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import PaymentUnavailableError
from app.models.category import Category
from app.models.enums import (
    AdminRole,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ProductStatus,
    RefundStatus,
    ShipmentStatus,
)
from app.models.notification import Notification
from app.models.order import Order
from app.models.payment import Payment
from app.models.product import Product
from app.models.shipment import Shipment
from app.models.variant import Variant
from app.services import (
    dispatch_service,
    order_ready_service,
    reservation_service,
    stripe_service,
    telegram_payments,
)
from app.services.notification_templates import money
from tests.admin_factories import add_admin
from tests.courier_factories import INTERNAL_HEADERS, add_courier, add_customer
from tests.factories import default_seller_id, make_init_data

ADDRESS = {
    "street": "Amir Temur 1",
    "city": "Tashkent",
    "postal_code": "100000",
    "country": "UZ",
    "phone": "+998901234567",
}
WEBHOOK_SECRET = "test-webhook-secret"
_seq = itertools.count(1)


@pytest.fixture(autouse=True)
def shop(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_payment_provider_token", "398062629:TEST:click")
    monkeypatch.setattr(settings, "cash_on_delivery_enabled", True)
    monkeypatch.setattr(settings, "default_currency", "UZS")
    monkeypatch.setattr(settings, "shipping_flat_rate", "20000")
    monkeypatch.setattr(settings, "free_shipping_threshold", "300000")
    monkeypatch.setattr(settings, "telegram_webhook_secret", WEBHOOK_SECRET)


class FakeInvoices:
    def __init__(self) -> None:
        self.params: list[dict] = []
        self.fail = False

    async def create_invoice_link(self, params: dict) -> str:
        if self.fail:
            raise PaymentUnavailableError("Bad Request: PAYMENT_PROVIDER_INVALID")
        self.params.append(params)
        return f"https://t.me/$invoice{len(self.params)}"


@pytest.fixture
def invoices(monkeypatch: pytest.MonkeyPatch) -> FakeInvoices:
    fake = FakeInvoices()
    monkeypatch.setattr(telegram_payments, "create_invoice_link", fake.create_invoice_link)
    return fake


def _headers(telegram_id: int) -> dict[str, str]:
    return {"Authorization": f"tma {make_init_data(telegram_id=telegram_id)}"}


async def _variant(db: AsyncSession, price: str = "89000", stock: int = 5) -> Variant:
    n = next(_seq)
    category = Category(slug=f"uz-cat-{n}", sort_order=0)
    db.add(category)
    await db.flush()
    product = Product(
        seller_id=await default_seller_id(db),
        category_id=category.id,
        base_sku=f"UZ-{n}",
        base_price=Decimal(price),
        status=ProductStatus.active,
    )
    db.add(product)
    await db.flush()
    variant = Variant(product_id=product.id, sku=f"UZ-{n}-V", price=Decimal(price), stock_qty=stock)
    db.add(variant)
    await db.commit()
    return variant


async def _checkout(
    client: AsyncClient, telegram_id: int, variant_id: int, method: str | None, qty=2
):
    headers = _headers(telegram_id)
    await client.post("/cart/items", json={"variant_id": variant_id, "qty": qty}, headers=headers)
    body: dict = {"delivery_address": ADDRESS}
    if method is not None:
        body["payment_method"] = method
    return await client.post("/checkout", json=body, headers=headers)


async def _order(db: AsyncSession, order_id: int) -> Order:
    return (
        await db.execute(
            select(Order).where(Order.id == order_id).execution_options(populate_existing=True)
        )
    ).scalar_one()


async def _payment(db: AsyncSession, order_id: int) -> Payment:
    return (
        await db.execute(
            select(Payment)
            .where(Payment.order_id == order_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()


async def _texts(db: AsyncSession, chat_id: int) -> list[str]:
    rows = await db.scalars(
        select(Notification.text).where(Notification.chat_id == chat_id).order_by(Notification.id)
    )
    return list(rows)


async def _webhook(client: AsyncClient, update_body: dict):
    return await client.post(
        "/webhooks/telegram",
        json=update_body,
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )


def _pre_checkout(order_id: int, sender: int, amount: int, currency: str = "UZS") -> dict:
    return {
        "update_id": next(_seq),
        "pre_checkout_query": {
            "id": f"q{next(_seq)}",
            "from": {"id": sender, "is_bot": False, "first_name": "A", "language_code": "ru"},
            "currency": currency,
            "total_amount": amount,
            "invoice_payload": f"order:{order_id}",
        },
    }


def _successful(order_id: int, sender: int, amount: int) -> dict:
    return {
        "update_id": next(_seq),
        "message": {
            "message_id": 5,
            "date": 1_758_700_000,
            "from": {"id": sender, "is_bot": False, "first_name": "A"},
            "chat": {"id": sender, "type": "private"},
            "successful_payment": {
                "currency": "UZS",
                "total_amount": amount,
                "invoice_payload": f"order:{order_id}",
                "telegram_payment_charge_id": "tg_charge_1",
                "provider_payment_charge_id": "click_777",
            },
        },
    }


# --- methods ---------------------------------------------------------------------------------


async def test_methods_list_what_is_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = await client.get("/checkout/methods", headers=_headers(5001))
    assert response.json() == {"methods": ["telegram", "cash", "stripe"], "currency": "UZS"}

    monkeypatch.setattr(get_settings(), "telegram_payment_provider_token", "")
    monkeypatch.setattr(get_settings(), "stripe_secret_key", "")
    response = await client.get("/checkout/methods", headers=_headers(5001))
    assert response.json()["methods"] == ["cash"]


async def test_a_disabled_method_is_refused(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "cash_on_delivery_enabled", False)
    variant = await _variant(db_session)

    response = await _checkout(client, 5002, variant.id, "cash")

    assert response.status_code == 400


# --- Telegram Payments -----------------------------------------------------------------------


async def test_telegram_checkout_reserves_and_returns_an_invoice(
    client: AsyncClient, db_session: AsyncSession, invoices: FakeInvoices
) -> None:
    variant = await _variant(db_session, price="89000")

    response = await _checkout(client, 5101, variant.id, None)  # telegram is the first method

    assert response.status_code == 200
    body = response.json()
    assert body["payment_method"] == "telegram"
    assert body["invoice_url"] == "https://t.me/$invoice1"
    assert body["client_secret"] is None
    (params,) = invoices.params
    assert params["payload"] == f"order:{body['order_id']}"
    assert params["currency"] == "UZS"
    assert params["provider_token"] == "398062629:TEST:click"
    # 2 × 89 000 = 178 000 plus 20 000 delivery, in tiyin.
    assert [p["amount"] for p in params["prices"]] == [17_800_000, 2_000_000]
    assert sum(p["amount"] for p in params["prices"]) == 19_800_000
    order = await _order(db_session, body["order_id"])
    assert (order.status, order.payment_method) == (OrderStatus.pending_payment, "telegram")
    assert await db_session.scalar(select(Variant.stock_qty).where(Variant.id == variant.id)) == 3
    payment = await _payment(db_session, order.id)
    assert (payment.method, payment.stripe_payment_intent_id) == (PaymentMethod.telegram, None)


async def test_an_invoice_failure_returns_the_cart_and_answers_502(
    client: AsyncClient, db_session: AsyncSession, invoices: FakeInvoices
) -> None:
    variant = await _variant(db_session)
    invoices.fail = True

    response = await _checkout(client, 5102, variant.id, "telegram")

    assert response.status_code == 502
    assert response.json()["code"] == "payment_unavailable"
    assert await db_session.scalar(select(Variant.stock_qty).where(Variant.id == variant.id)) == 5
    order_id = await db_session.scalar(select(Order.id).where(Order.telegram_id == 5102))
    assert (await _order(db_session, order_id)).cancel_reason == "payment_setup_failed"


async def _telegram_order(client, db, invoices, telegram_id: int) -> tuple[int, int]:
    variant = await _variant(db)
    body = (await _checkout(client, telegram_id, variant.id, "telegram")).json()
    return body["order_id"], 19_800_000


async def test_pre_checkout_approves_a_matching_unpaid_order_and_extends_the_hold(
    client: AsyncClient, db_session: AsyncSession, invoices: FakeInvoices
) -> None:
    order_id, amount = await _telegram_order(client, db_session, invoices, 5201)
    await db_session.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(reserved_until=datetime.now(UTC) + timedelta(seconds=30))
    )
    await db_session.commit()

    answer = (await _webhook(client, _pre_checkout(order_id, 5201, amount))).json()

    assert answer["method"] == "answerPreCheckoutQuery"
    assert answer["ok"] is True
    held = (await _order(db_session, order_id)).reserved_until
    assert held > datetime.now(UTC) + timedelta(minutes=4)


@pytest.mark.parametrize(
    ("change", "expected_message"),
    [
        ("amount", "Этот заказ больше нельзя оплатить."),
        ("currency", "Этот заказ больше нельзя оплатить."),
        ("sender", "Этот заказ больше нельзя оплатить."),
        ("expired", "Время на оплату истекло. Оформите заказ заново."),
        ("paid", "Этот заказ больше нельзя оплатить."),
        ("payload", "Этот заказ больше нельзя оплатить."),
    ],
)
async def test_pre_checkout_refuses_anything_else(
    client: AsyncClient,
    db_session: AsyncSession,
    invoices: FakeInvoices,
    change: str,
    expected_message: str,
) -> None:
    order_id, amount = await _telegram_order(client, db_session, invoices, 5202)
    query = _pre_checkout(order_id, 5202, amount)
    q = query["pre_checkout_query"]
    if change == "amount":
        q["total_amount"] = amount - 100
    elif change == "currency":
        q["currency"] = "USD"
    elif change == "sender":
        q["from"]["id"] = 9999
    elif change == "payload":
        q["invoice_payload"] = "nonsense"
    elif change == "expired":
        await db_session.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(reserved_until=datetime.now(UTC) - timedelta(hours=1))
        )
        await db_session.commit()
    elif change == "paid":
        await db_session.execute(
            update(Order).where(Order.id == order_id).values(status=OrderStatus.paid)
        )
        await db_session.commit()

    answer = (await _webhook(client, query)).json()

    assert answer["ok"] is False
    assert answer["error_message"] == expected_message


async def test_successful_payment_marks_paid_and_keeps_the_charge_ids(
    client: AsyncClient, db_session: AsyncSession, invoices: FakeInvoices
) -> None:
    order_id, amount = await _telegram_order(client, db_session, invoices, 5203)

    first = await _webhook(client, _successful(order_id, 5203, amount))
    again = await _webhook(client, _successful(order_id, 5203, amount))  # redelivered

    assert first.status_code == again.status_code == 200
    assert (await _order(db_session, order_id)).status == OrderStatus.paid
    payment = await _payment(db_session, order_id)
    assert payment.status == PaymentStatus.succeeded
    assert (payment.telegram_payment_charge_id, payment.provider_payment_charge_id) == (
        "tg_charge_1",
        "click_777",
    )
    shipments = await db_session.scalars(select(Shipment.id).where(Shipment.order_id == order_id))
    assert len(list(shipments)) == 1


async def test_a_payment_for_an_unknown_order_is_acknowledged(client: AsyncClient) -> None:
    response = await _webhook(client, _successful(99_999_999, 5204, 100))
    assert response.status_code == 200


async def test_an_expired_telegram_order_needs_no_provider_call(
    client: AsyncClient,
    db_session: AsyncSession,
    invoices: FakeInvoices,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order_id, _ = await _telegram_order(client, db_session, invoices, 5205)
    await db_session.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(reserved_until=datetime.now(UTC) - timedelta(hours=1))
    )
    await db_session.commit()

    async def _never(*args, **kwargs):
        raise AssertionError("Stripe must not be called for a Telegram payment")

    monkeypatch.setattr(stripe_service, "cancel_payment_intent", _never)

    assert await reservation_service.expire_order(db_session, order_id) is True


async def test_late_telegram_payment_needs_a_manual_refund(
    client: AsyncClient, db_session: AsyncSession, invoices: FakeInvoices
) -> None:
    await add_customer(db_session, 5299)
    await add_admin(db_session, 5299, AdminRole.owner)
    order_id, amount = await _telegram_order(client, db_session, invoices, 5206)
    await db_session.execute(
        update(Order).where(Order.id == order_id).values(status=OrderStatus.cancelled)
    )
    await db_session.commit()

    await _webhook(client, _successful(order_id, 5206, amount))

    payment = await _payment(db_session, order_id)
    assert payment.refund_status == RefundStatus.manual_required
    (text,) = await _texts(db_session, 5299)
    assert "UZS 198,000" in text and "click_777" in text


# --- cash on delivery ------------------------------------------------------------------------


async def test_cash_checkout_reaches_the_couriers_once_ready(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_customer(db_session, 5301)
    await add_courier(db_session, 5301)  # a courier is also a Telegram user
    variant = await _variant(db_session)

    response = await _checkout(client, 5302, variant.id, "cash")

    assert response.status_code == 200
    body = response.json()
    assert body["payment_method"] == "cash"
    assert body["client_secret"] is None and body["invoice_url"] is None
    order = await _order(db_session, body["order_id"])
    assert order.status == OrderStatus.paid
    assert (await _payment(db_session, order.id)).status == PaymentStatus.requires_payment_method
    assert await db_session.scalar(
        select(Shipment.status).where(Shipment.order_id == order.id)
    ) == (ShipmentStatus.processing)
    assert await db_session.scalar(select(Variant.stock_qty).where(Variant.id == variant.id)) == 3
    (customer_text,) = await _texts(db_session, 5302)
    assert customer_text == (
        f"Order #{order.id} is confirmed. Pay in cash on delivery: UZS 198,000."
    )
    # Spec 10: couriers hear about it once the seller has it ready.
    assert await _texts(db_session, 5301) == []
    await order_ready_service.mark_ready(db_session, order.id, None)
    (courier_text,) = await _texts(db_session, 5301)
    assert "Cash: UZS 198,000." in courier_text

    pool = (await client.get("/courier/pool", headers=_headers(5301))).json()
    mine = next(item for item in pool if item["order_id"] == order.id)
    assert (mine["cash_to_collect"], mine["currency"]) == ("198000.00", "UZS")


async def test_delivering_a_cash_order_records_the_money(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await add_customer(db_session, 5311)
    courier = await add_courier(db_session, 5311)
    variant = await _variant(db_session)
    order_id = (await _checkout(client, 5312, variant.id, "cash")).json()["order_id"]
    shipment_id = await db_session.scalar(select(Shipment.id).where(Shipment.order_id == order_id))
    await order_ready_service.mark_ready(db_session, order_id, None)

    await dispatch_service.claim(db_session, courier, shipment_id)
    await dispatch_service.pickup(db_session, courier, shipment_id)
    assert (await _payment(db_session, order_id)).status == PaymentStatus.requires_payment_method
    await dispatch_service.deliver(db_session, courier, shipment_id)

    assert (await _payment(db_session, order_id)).status == PaymentStatus.succeeded


# --- cancellations ---------------------------------------------------------------------------


async def test_cancelling_a_cash_order_refunds_nothing(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _never(*args, **kwargs):
        raise AssertionError("no refund for money never taken")

    monkeypatch.setattr(stripe_service, "create_refund", _never)
    variant = await _variant(db_session)
    order_id = (await _checkout(client, 5401, variant.id, "cash")).json()["order_id"]

    response = await client.post(
        f"/internal/orders/{order_id}/cancel", json={"reason": "No stock"}, headers=INTERNAL_HEADERS
    )

    assert response.status_code == 200
    payment = await _payment(db_session, order_id)
    assert (payment.status, payment.refund_status) == (PaymentStatus.canceled, None)
    texts = await _texts(db_session, 5401)
    assert texts[-1] == f"Order #{order_id} was cancelled by the shop: No stock."


async def test_cancelling_a_telegram_payment_asks_the_owner_to_refund_by_hand(
    client: AsyncClient, db_session: AsyncSession, invoices: FakeInvoices
) -> None:
    await add_customer(db_session, 5499)
    await add_admin(db_session, 5499, AdminRole.owner)
    order_id, amount = await _telegram_order(client, db_session, invoices, 5402)
    await _webhook(client, _successful(order_id, 5402, amount))

    cancelled = await client.post(
        f"/internal/orders/{order_id}/cancel", json={"reason": "Broken"}, headers=INTERNAL_HEADERS
    )

    assert cancelled.json()["payment"]["refund_status"] == "manual_required"
    assert cancelled.json()["payment"]["provider_payment_charge_id"] == "click_777"
    assert any("click_777" in text for text in await _texts(db_session, 5499))

    confirmed = await client.post(
        f"/internal/orders/{order_id}/refund/confirm", headers=INTERNAL_HEADERS
    )
    assert confirmed.json()["payment"]["refund_status"] == "succeeded"
    assert (await _texts(db_session, 5402))[-1] == (
        f"The payment for order #{order_id} has been refunded."
    )
    again = await client.post(
        f"/internal/orders/{order_id}/refund/confirm", headers=INTERNAL_HEADERS
    )
    assert again.status_code == 409


async def test_only_owners_confirm_manual_refunds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from tests.admin_factories import admin_tma

    await add_customer(db_session, 5501)
    await add_admin(db_session, 5501, AdminRole.dispatcher)

    response = await client.post("/internal/orders/1/refund/confirm", headers=admin_tma(5501))

    assert response.status_code == 403


# --- money -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("locale", "expected"),
    [("ru", "250 000 сум"), ("uz", "250 000 so'm"), ("en", "UZS 250,000"), (None, "UZS 250,000")],
)
def test_sums_are_whole_and_grouped(locale: str | None, expected: str) -> None:
    assert money(Decimal("250000.00"), "UZS", locale) == expected


def test_invoice_lines_match_the_order() -> None:
    params = telegram_payments.build_invoice(
        order_id=7,
        currency="uzs",
        lines=[("Помада", 1, Decimal("350000"))],
        shipping_cost=Decimal("0"),
        shipping_label="Доставка",
    )
    assert params["prices"] == [{"label": "Помада × 1", "amount": 35_000_000}]  # free delivery
    assert params["currency"] == "UZS"
    assert telegram_payments.order_id_from_payload(params["payload"]) == 7
    assert telegram_payments.order_id_from_payload("order:x") is None


async def test_create_invoice_link_never_leaks_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    token = "123:SECRET"
    monkeypatch.setattr(get_settings(), "telegram_bot_token", token)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"ok": False, "description": "Bad Request: CURRENCY_INVALID"}
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(PaymentUnavailableError) as raised:
        await telegram_payments.create_invoice_link({"title": "x"})

    assert "CURRENCY_INVALID" in str(raised.value)
    assert token not in str(raised.value)


def test_the_webhook_asks_telegram_for_payment_updates() -> None:
    from scripts import set_telegram_webhook

    assert "pre_checkout_query" in set_telegram_webhook.ALLOWED_UPDATES
