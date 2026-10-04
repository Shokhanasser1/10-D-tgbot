"""Telegram notifications: who is told what (Spec 5 §3), and how the outbox is delivered (§6)."""

from collections.abc import Callable
from types import SimpleNamespace

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.enums import AdminRole, NotificationStatus, OrderStatus, RefundStatus
from app.models.notification import Notification
from app.models.order import Order
from app.models.payment import Payment
from app.models.shipment import Shipment
from app.models.telegram_user import TelegramUser
from app.services import (
    dispatch_service,
    notification_sender,
    notification_service,
    order_admin_service,
    order_ready_service,
    order_service,
    reservation_service,
    stripe_service,
)
from app.services.notification_sender import Outcome
from app.services.notification_templates import items, money
from tests.admin_factories import add_admin
from tests.courier_factories import add_courier, add_customer, add_paid_order
from tests.factories import default_seller_id

CUSTOMER = 880_001
WEBAPP = "https://shop.example.com/"


@pytest.fixture(autouse=True)
def webapp_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "webapp_url", WEBAPP)


async def _messages(db: AsyncSession) -> list[Notification]:
    return list(
        (
            await db.execute(
                select(Notification)
                .order_by(Notification.id)
                .execution_options(populate_existing=True)
            )
        ).scalars()
    )


async def _by_chat(db: AsyncSession) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for message in await _messages(db):
        result.setdefault(message.chat_id, []).append(message.text)
    return result


async def _set_locale(db: AsyncSession, telegram_id: int, locale: str) -> None:
    await add_customer(db, telegram_id)
    await db.execute(
        update(TelegramUser).where(TelegramUser.telegram_id == telegram_id).values(locale=locale)
    )
    await db.commit()


def _button_url(message: Notification) -> str | None:
    if not message.reply_markup:
        return None
    return message.reply_markup["inline_keyboard"][0][0]["web_app"]["url"]


async def _unpaid_order(db: AsyncSession, **kwargs) -> Order:
    """A paid-looking order put back to pending_payment, as the Stripe webhook finds it."""
    order, shipment = await add_paid_order(db, customer_id=CUSTOMER, **kwargs)
    await db.execute(delete(Shipment).where(Shipment.id == shipment.id))
    await db.execute(
        update(Order).where(Order.id == order.id).values(status=OrderStatus.pending_payment)
    )
    await db.commit()
    return order


# --- templates -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("count", "locale", "expected"),
    [
        (1, "en", "1 item"),
        (2, "en", "2 items"),
        (1, "ru", "1 товар"),
        (3, "ru", "3 товара"),
        (5, "ru", "5 товаров"),
        (11, "ru", "11 товаров"),
        (21, "ru", "21 товар"),
        (2, "uz", "2 ta mahsulot"),
        (2, "de", "2 items"),
    ],
)
def test_item_counts_are_spelled_per_language(count: int, locale: str, expected: str) -> None:
    assert items(count, locale) == expected


def test_money_uses_a_symbol_when_there_is_one() -> None:
    from decimal import Decimal

    assert money(Decimal("44.9"), "EUR") == "€44.90"
    assert money(Decimal("120000"), "UZS") == "UZS 120,000"  # whole sums, grouped


def test_no_button_without_an_https_webapp_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "webapp_url", "http://localhost:8080")
    assert notification_service.web_app_button("Open", "orders/1") is None


# --- payment ---------------------------------------------------------------------------------


async def test_payment_tells_the_customer_the_seller_and_admins(db_session: AsyncSession) -> None:
    await _set_locale(db_session, CUSTOMER, "ru")
    order = await _unpaid_order(db_session, city="Tashkent", street="Amir Temur 1", qty=2)
    await add_customer(db_session, 881_001)
    await add_courier(db_session, 881_001, name="Bekzod")
    await add_admin(db_session, 881_010, AdminRole.owner)
    await add_admin(db_session, 881_011, AdminRole.dispatcher)
    await add_admin(db_session, 881_012, AdminRole.catalog_manager)
    await add_admin(
        db_session, 881_013, AdminRole.seller, seller_id=await default_seller_id(db_session)
    )

    await order_service.mark_order_paid(db_session, order.id)

    by_chat = await _by_chat(db_session)
    assert by_chat[CUSTOMER] == [f"Заказ №{order.id} оплачен. Ищем курьера."]
    assert by_chat[881_013] == [
        f"New order #{order.id}: 2 items. Collect it and press Ready, then a courier comes."
    ]
    assert by_chat[881_010] == [f"New order #{order.id}, €24.99."]
    assert 881_011 in by_chat
    assert 881_001 not in by_chat  # couriers hear about it once the seller has it ready
    assert 881_012 not in by_chat  # catalog managers do not handle orders
    urls = {m.chat_id: _button_url(m) for m in await _messages(db_session)}
    assert urls[CUSTOMER] == f"{WEBAPP}orders/{order.id}"
    assert urls[881_013] == f"{WEBAPP}admin/orders/{order.id}"
    assert urls[881_010] == f"{WEBAPP}admin/orders/{order.id}"


async def test_ready_tells_the_active_couriers_where_to_collect(db_session: AsyncSession) -> None:
    order = await _unpaid_order(db_session, city="Tashkent", street="Amir Temur 1", qty=2)
    await add_customer(db_session, 881_001)
    await add_courier(db_session, 881_001, name="Bekzod")
    await add_courier(db_session, 881_002, name="Off", is_active=False)
    await order_service.mark_order_paid(db_session, order.id)

    await order_ready_service.mark_ready(db_session, order.id, None)

    by_chat = await _by_chat(db_session)
    assert by_chat[881_001] == [
        "New order in the pool: Tashkent, Amir Temur 1, 2 items."
        " Pickup: Test shop, Tashkent, Amir Temur 1."
    ]
    assert 881_002 not in by_chat  # inactive courier
    urls = {m.chat_id: _button_url(m) for m in await _messages(db_session)}
    assert urls[881_001] == f"{WEBAPP}courier"


async def test_pool_messages_never_carry_the_phone_or_notes(db_session: AsyncSession) -> None:
    order = await _unpaid_order(db_session, notes="Code 1234")
    await add_customer(db_session, 881_020)
    await add_courier(db_session, 881_020)

    await order_service.mark_order_paid(db_session, order.id)
    await order_ready_service.mark_ready(db_session, order.id, None)

    (text,) = (await _by_chat(db_session))[881_020]
    assert "1234" not in text and "+49" not in text


async def test_a_replayed_payment_event_notifies_once(db_session: AsyncSession) -> None:
    order = await _unpaid_order(db_session)

    await order_service.mark_order_paid(db_session, order.id)
    await order_service.mark_order_paid(db_session, order.id)

    assert len((await _by_chat(db_session))[CUSTOMER]) == 1


async def test_shortfall_is_flagged_to_admins(db_session: AsyncSession) -> None:
    order = await _unpaid_order(db_session)
    await db_session.execute(update(Order).where(Order.id == order.id).values(stock_shortfall=True))
    await db_session.commit()
    await add_admin(db_session, 881_030)

    await order_service.mark_order_paid(db_session, order.id)

    assert (await _by_chat(db_session))[881_030][0].endswith("⚠ Not enough stock.")


# --- courier actions -------------------------------------------------------------------------


async def _claimed(db: AsyncSession, courier_tg: int = 882_001, name: str = "Bekzod Karimov"):
    order, shipment = await add_paid_order(db, customer_id=CUSTOMER)
    await add_customer(db, courier_tg)
    courier = await add_courier(db, courier_tg, name=name)
    await dispatch_service.claim(db, courier, shipment.id)
    return order, shipment, courier


async def test_customer_follows_claim_pickup_and_delivery(db_session: AsyncSession) -> None:
    order, shipment, courier = await _claimed(db_session)
    await dispatch_service.pickup(db_session, courier, shipment.id)
    await dispatch_service.deliver(db_session, courier, shipment.id)

    assert (await _by_chat(db_session))[CUSTOMER] == [
        f"Courier Bekzod has taken order #{order.id}.",
        f"Order #{order.id} is on its way. Follow the courier on the map.",
        f"Order #{order.id} has been delivered. Thank you!",
    ]
    assert courier.telegram_id not in await _by_chat(db_session)


async def test_a_released_order_goes_to_the_other_couriers_only(db_session: AsyncSession) -> None:
    order, shipment, courier = await _claimed(db_session)
    await add_customer(db_session, 882_002)
    await add_courier(db_session, 882_002)

    await dispatch_service.release(db_session, courier, shipment.id)

    by_chat = await _by_chat(db_session)
    assert by_chat[882_002] == [
        "Order back in the pool: Berlin, Alexanderplatz 1, 1 item."
        " Pickup: Test shop, Tashkent, Amir Temur 1."
    ]
    assert courier.telegram_id not in by_chat
    assert len(by_chat[CUSTOMER]) == 1  # only "taken"; release is not the customer's concern


async def test_claiming_again_after_a_release_notifies_again(db_session: AsyncSession) -> None:
    order, shipment, courier = await _claimed(db_session)
    await dispatch_service.release(db_session, courier, shipment.id)
    await dispatch_service.claim(db_session, courier, shipment.id)

    assert len((await _by_chat(db_session))[CUSTOMER]) == 2


async def test_owner_release_skips_the_courier_it_was_taken_from(db_session: AsyncSession) -> None:
    order, shipment, courier = await _claimed(db_session)
    await add_customer(db_session, 882_003)
    await add_courier(db_session, 882_003)

    await dispatch_service.force_release(db_session, shipment.id)

    by_chat = await _by_chat(db_session)
    assert 882_003 in by_chat
    assert courier.telegram_id not in by_chat


# --- cancellations and refunds ---------------------------------------------------------------


class FakeRefunds:
    def __init__(self) -> None:
        self.status = "succeeded"
        self.fail = False

    async def create_refund(self, payment_intent_id: str, idempotency_key: str, metadata: dict):
        if self.fail:
            import stripe

            raise stripe.APIConnectionError("down")
        return SimpleNamespace(id="re_1", status=self.status)


@pytest.fixture
def refunds(monkeypatch: pytest.MonkeyPatch) -> FakeRefunds:
    fake = FakeRefunds()
    monkeypatch.setattr(stripe_service, "create_refund", fake.create_refund)
    return fake


async def test_shop_cancellation_and_refund_reach_the_customer(
    db_session: AsyncSession, refunds: FakeRefunds
) -> None:
    order, _ = await add_paid_order(db_session, customer_id=CUSTOMER)

    await order_admin_service.cancel_order(db_session, order.id, "Out of stock", None)

    assert (await _by_chat(db_session))[CUSTOMER] == [
        f"Order #{order.id} was cancelled by the shop: Out of stock. Your money will be refunded.",
        f"The payment for order #{order.id} has been refunded.",
    ]


async def test_a_failed_refund_alerts_owners_once_per_failure(
    db_session: AsyncSession, refunds: FakeRefunds
) -> None:
    order, _ = await add_paid_order(db_session, customer_id=CUSTOMER)
    await add_admin(db_session, 883_001)
    await add_admin(db_session, 883_002, AdminRole.dispatcher)
    refunds.status = "failed"

    await order_admin_service.cancel_order(db_session, order.id, "Broken", None)
    # Stripe also reports the same failure through the webhook.
    await order_admin_service.apply_refund_event(db_session, "pi_x", "re_1", "failed")
    payment_intent = await db_session.scalar(
        select(Payment.stripe_payment_intent_id).where(Payment.order_id == order.id)
    )
    await order_admin_service.apply_refund_event(db_session, payment_intent, "re_1", "failed")

    by_chat = await _by_chat(db_session)
    assert by_chat[883_001] == [
        f"⚠ The refund for order #{order.id} failed. Retry it in the admin panel."
    ]
    assert 883_002 not in by_chat  # refunds are the owner's business

    refunds.fail = True
    await order_admin_service.retry_refund(db_session, order.id)
    assert len((await _by_chat(db_session))[883_001]) == 2  # a new failure, a new alert


async def test_refund_success_reported_by_webhook(db_session: AsyncSession) -> None:
    order, _ = await add_paid_order(db_session, customer_id=CUSTOMER)
    await db_session.execute(
        update(Payment)
        .where(Payment.order_id == order.id)
        .values(refund_status=RefundStatus.pending, stripe_payment_intent_id="pi_hook")
    )
    await db_session.commit()

    await order_admin_service.apply_refund_event(db_session, "pi_hook", "re_9", "succeeded")
    await order_admin_service.apply_refund_event(db_session, "pi_hook", "re_9", "succeeded")

    assert (await _by_chat(db_session))[CUSTOMER] == [
        f"The payment for order #{order.id} has been refunded."
    ]


async def test_expired_order_tells_the_customer_with_a_cart_button(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime, timedelta

    order = await _unpaid_order(db_session)
    await db_session.execute(
        update(Order)
        .where(Order.id == order.id)
        .values(reserved_until=datetime.now(UTC) - timedelta(hours=1))
    )
    await db_session.execute(delete(Payment).where(Payment.order_id == order.id))
    await db_session.commit()

    assert await reservation_service.expire_order(db_session, order.id)

    (message,) = await _messages(db_session)
    assert message.text.startswith(f"Payment time for order #{order.id} ran out.")
    assert _button_url(message) == f"{WEBAPP}cart"


async def test_a_rolled_back_action_leaves_no_message(db_session: AsyncSession) -> None:
    order, _ = await add_paid_order(db_session, customer_id=CUSTOMER)

    # The event is enqueued inside the action's transaction; if that transaction is rolled
    # back (a guarded UPDATE lost a race, say), the message must go with it.
    await notification_service.enqueue(
        db_session, chat_id=CUSTOMER, kind="test", dedupe_key="rolled-back", text="never"
    )
    await db_session.rollback()

    assert await _messages(db_session) == []


# --- sender ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "body", "kind"),
    [
        (200, {"ok": True}, "sent"),
        (
            403,
            {"ok": False, "description": "Forbidden: bot was blocked by the user"},
            "undeliverable",
        ),
        (400, {"ok": False, "description": "Bad Request: chat not found"}, "undeliverable"),
        (400, {"ok": False, "description": "Bad Request: message is too long"}, "failed"),
        (429, {"ok": False, "parameters": {"retry_after": 7}}, "rate_limited"),
        (502, {}, "retry"),
    ],
)
def test_telegram_answers_are_classified(status: int, body: dict, kind: str) -> None:
    assert notification_sender.classify(status, body).kind == kind


def test_backoff_grows() -> None:
    assert [notification_sender.backoff(n).total_seconds() for n in (1, 2, 3)] == [5, 15, 45]


class FakeTelegram:
    def __init__(self, answers: list[Outcome] | None = None) -> None:
        self.answers = answers or []
        self.sent: list[tuple[int, str]] = []

    async def send(self, chat_id: int, text: str, reply_markup: dict | None) -> Outcome:
        self.sent.append((chat_id, text))
        return self.answers.pop(0) if self.answers else Outcome("sent")


def _factory(db: AsyncSession) -> Callable[[], AsyncSession]:
    return lambda: AsyncSession(
        bind=db.bind, join_transaction_mode="create_savepoint", expire_on_commit=False
    )


async def _queue(db: AsyncSession, *chat_ids: int) -> None:
    for chat_id in chat_ids:
        await notification_service.enqueue(
            db, chat_id=chat_id, kind="test", dedupe_key=f"t:{chat_id}", text=f"hi {chat_id}"
        )
    await db.commit()


async def test_sender_delivers_and_records_each_outcome(db_session: AsyncSession) -> None:
    await _queue(db_session, 1, 2, 3, 4)
    telegram = FakeTelegram(
        [
            Outcome("sent"),
            Outcome("undeliverable", "Forbidden: bot was blocked by the user"),
            Outcome("retry", "HTTP 502"),
            Outcome("failed", "Bad Request: message is too long"),
        ]
    )

    assert await notification_sender.send_batch(_factory(db_session), telegram, gap=0) == 1

    rows = {m.chat_id: m for m in await _messages(db_session)}
    assert rows[1].status == NotificationStatus.sent and rows[1].sent_at is not None
    assert rows[2].status == NotificationStatus.undeliverable
    assert (rows[3].status, rows[3].attempts) == (NotificationStatus.pending, 1)
    assert rows[4].status == NotificationStatus.failed


async def test_a_leased_row_is_not_taken_twice(db_session: AsyncSession) -> None:
    await _queue(db_session, 1)
    factory = _factory(db_session)
    async with factory() as db:
        first = await notification_sender.lease_due(db)
    async with factory() as db:
        second = await notification_sender.lease_due(db)

    assert [row.chat_id for row in first] == [1]
    assert second == []


async def test_a_rate_limit_stops_the_batch_and_hands_back_the_rest(
    db_session: AsyncSession,
) -> None:
    await _queue(db_session, 1, 2, 3)
    telegram = FakeTelegram([Outcome("sent"), Outcome("rate_limited", "Too Many Requests", 7)])

    await notification_sender.send_batch(_factory(db_session), telegram, gap=0)

    assert [chat for chat, _ in telegram.sent] == [1, 2]
    async with _factory(db_session)() as db:
        again = await notification_sender.lease_due(db)
    assert [row.chat_id for row in again] == [3]  # the unsent one is due again at once


async def test_retries_give_up_after_the_limit(db_session: AsyncSession) -> None:
    await _queue(db_session, 1)
    await db_session.execute(
        update(Notification).values(attempts=notification_sender.MAX_ATTEMPTS - 1)
    )
    await db_session.commit()

    await notification_sender.send_batch(
        _factory(db_session), FakeTelegram([Outcome("retry", "HTTP 500")]), gap=0
    )

    (row,) = await _messages(db_session)
    assert row.status == NotificationStatus.failed


async def test_one_broken_message_does_not_stop_the_batch(db_session: AsyncSession) -> None:
    await _queue(db_session, 1, 2)

    class Flaky(FakeTelegram):
        async def send(self, chat_id: int, text: str, reply_markup: dict | None) -> Outcome:
            if chat_id == 1:
                raise RuntimeError("boom")
            return await super().send(chat_id, text, reply_markup)

    assert await notification_sender.send_batch(_factory(db_session), Flaky(), gap=0) == 1


async def test_cleanup_removes_only_old_finished_messages(db_session: AsyncSession) -> None:
    from datetime import UTC, datetime, timedelta

    await _queue(db_session, 1, 2, 3)
    old = datetime.now(UTC) - timedelta(days=40)
    await db_session.execute(
        update(Notification)
        .where(Notification.chat_id.in_((1, 2)))
        .values(created_at=old, status=NotificationStatus.sent)
    )
    await db_session.execute(
        update(Notification).where(Notification.chat_id == 3).values(created_at=old)
    )
    await db_session.commit()

    assert await notification_sender.cleanup(db_session) == 2
    assert [m.chat_id for m in await _messages(db_session)] == [3]  # pending is kept


async def test_the_http_client_never_leaks_the_token() -> None:
    token = "123:SECRET-TOKEN"
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if len(seen) == 1:
            return httpx.Response(200, json={"ok": True, "result": {}})
        raise httpx.ConnectError(f"cannot reach {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = notification_sender.TelegramClient(token, http)
        ok = await client.send(1, "hi", {"inline_keyboard": []})
        failed = await client.send(1, "hi", None)

    assert seen[0].endswith(f"/bot{token}/sendMessage")
    assert ok.kind == "sent"
    assert failed.kind == "retry" and token not in (failed.error or "")


# --- start-up --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seconds", "token", "expected"),
    [(2, "123:abc", 1), (0, "123:abc", 0), (2, "", 0)],
)
async def test_the_sender_starts_only_with_a_token_and_an_interval(
    monkeypatch: pytest.MonkeyPatch, seconds: float, token: str, expected: int
) -> None:
    from app.main import background_tasks

    settings = get_settings().model_copy(
        update={
            "notification_send_seconds": seconds,
            "telegram_bot_token": token,
            "reservation_sweep_seconds": 0,
        }
    )
    tasks = background_tasks(settings)
    for task in tasks:
        task.cancel()
    assert len(tasks) == expected


async def test_webhook_payment_notifies_through_the_api(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    order = await _unpaid_order(db_session)
    event = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi", "metadata": {"order_id": str(order.id)}}},
    }
    monkeypatch.setattr(stripe_service, "construct_webhook_event", lambda payload, sig: event)

    response = await client.post(
        "/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t"}
    )

    assert response.status_code == 200
    assert CUSTOMER in await _by_chat(db_session)
