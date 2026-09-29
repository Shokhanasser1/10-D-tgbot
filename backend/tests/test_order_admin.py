from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import stripe
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.courier import CourierLocation
from app.models.enums import (
    AdminRole,
    OrderStatus,
    PaymentStatus,
    RefundStatus,
    ShipmentStatus,
)
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.shipment import Shipment
from app.models.variant import Variant
from app.services import courier_state, stripe_service
from tests.admin_factories import add_admin, admin_confirmed, admin_tma
from tests.courier_factories import INTERNAL_HEADERS, add_courier, add_paid_order

settings = get_settings()


class FakeStripe:
    """Records refund calls; answers with `status` or raises when `fail` is set."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.status = "pending"
        self.fail = False

    async def create_refund(self, payment_intent_id: str, idempotency_key: str, metadata: dict):
        self.calls.append(
            {"payment_intent": payment_intent_id, "key": idempotency_key, "metadata": metadata}
        )
        if self.fail:
            raise stripe.APIConnectionError("network down")
        return SimpleNamespace(id=f"re_{len(self.calls)}", status=self.status)


@pytest.fixture
def fake_stripe(monkeypatch: pytest.MonkeyPatch) -> FakeStripe:
    fake = FakeStripe()
    monkeypatch.setattr(stripe_service, "create_refund", fake.create_refund)
    return fake


async def _fresh(db: AsyncSession, model, *where):
    return (
        await db.execute(select(model).where(*where).execution_options(populate_existing=True))
    ).scalar_one()


async def _stock(db: AsyncSession, order_id: int) -> int:
    variant_id = await db.scalar(select(OrderItem.variant_id).where(OrderItem.order_id == order_id))
    return await db.scalar(select(Variant.stock_qty).where(Variant.id == variant_id))


def _cancel(client: AsyncClient, order_id: int, headers=INTERNAL_HEADERS, reason="Out of stock"):
    return client.post(
        f"/internal/orders/{order_id}/cancel", json={"reason": reason}, headers=headers
    )


# --- list and detail -------------------------------------------------------------------------


async def test_list_orders_newest_first_with_badges(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    older, _ = await add_paid_order(db_session, customer_id=960_001)
    newer, _ = await add_paid_order(db_session, customer_id=960_001)
    newer.stock_shortfall = True
    await db_session.commit()

    response = await client.get("/internal/orders?q=960001", headers=INTERNAL_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [o["id"] for o in body["items"]] == [newer.id, older.id]
    first = body["items"][0]
    assert first["status"] == "paid"
    assert first["shipment_status"] == "processing"
    assert first["stock_shortfall"] is True
    assert first["refund_status"] is None
    assert first["telegram_id"] == 960_001


async def test_search_by_order_number(client: AsyncClient, db_session: AsyncSession) -> None:
    order, _ = await add_paid_order(db_session, customer_id=960_002)

    response = await client.get(f"/internal/orders?q={order.id}", headers=INTERNAL_HEADERS)

    assert order.id in [o["id"] for o in response.json()["items"]]


async def test_non_numeric_search_matches_nothing(client: AsyncClient) -> None:
    response = await client.get("/internal/orders?q=abc", headers=INTERNAL_HEADERS)
    assert response.json() == {"items": [], "total": 0}


async def test_filter_by_status_and_shortfall(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    order, _ = await add_paid_order(db_session, customer_id=960_003)
    order.stock_shortfall = True
    await db_session.commit()

    hit = await client.get(
        "/internal/orders?q=960003&status=paid&status=processing&shortfall=true",
        headers=INTERNAL_HEADERS,
    )
    miss = await client.get("/internal/orders?q=960003&status=delivered", headers=INTERNAL_HEADERS)

    assert [o["id"] for o in hit.json()["items"]] == [order.id]
    assert miss.json()["total"] == 0


async def test_date_filter_uses_shop_timezone_days(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "shop_timezone", "Asia/Tashkent")  # UTC+5
    order, _ = await add_paid_order(db_session, customer_id=960_004)
    # 21:30 UTC on 1 March is already 2 March in Tashkent.
    order.placed_at = datetime(2026, 3, 1, 21, 30, tzinfo=UTC)
    await db_session.commit()

    def ids(response) -> list[int]:
        return [o["id"] for o in response.json()["items"]]

    base = "/internal/orders?q=960004"
    on_2nd = await client.get(f"{base}&from=2026-03-02&to=2026-03-02", headers=INTERNAL_HEADERS)
    on_1st = await client.get(f"{base}&from=2026-03-01&to=2026-03-01", headers=INTERNAL_HEADERS)

    assert ids(on_2nd) == [order.id]
    assert ids(on_1st) == []


async def test_order_detail(client: AsyncClient, db_session: AsyncSession) -> None:
    courier = await add_courier(db_session, 960_010, name="Bekzod")
    order, shipment = await add_paid_order(db_session, customer_id=960_011, pin=(41.3, 69.2))
    shipment.status = ShipmentStatus.assigned
    shipment.courier_id = courier.id
    order.status = OrderStatus.processing
    await db_session.commit()

    response = await client.get(f"/internal/orders/{order.id}", headers=INTERNAL_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["delivery_address"]["phone"] == "+491234567"
    assert (body["delivery_address"]["latitude"], body["delivery_address"]["longitude"]) == (
        41.3,
        69.2,
    )
    assert body["customer"]["telegram_id"] == 960_011
    assert body["items"][0]["sku"].startswith("COURIER-V-")
    assert body["payment"] == {
        "method": "stripe",
        "status": "succeeded",
        "amount": "14.99",
        "refund_status": None,
        "telegram_payment_charge_id": None,
        "provider_payment_charge_id": None,
    }
    assert body["shipment"]["courier_name"] == "Bekzod"
    assert body["shipment"]["status"] == "assigned"
    assert body["can_cancel"] is True


async def test_unknown_order_is_404(client: AsyncClient) -> None:
    assert (
        await client.get("/internal/orders/999999", headers=INTERNAL_HEADERS)
    ).status_code == 404


@pytest.mark.parametrize(
    ("role", "expected"),
    [(AdminRole.owner, 200), (AdminRole.dispatcher, 200), (AdminRole.catalog_manager, 403)],
)
async def test_orders_are_for_dispatch_roles(
    client: AsyncClient, db_session: AsyncSession, role: AdminRole, expected: int
) -> None:
    telegram_id = 961_000 + list(AdminRole).index(role)
    await add_admin(db_session, telegram_id, role)

    response = await client.get("/internal/orders", headers=admin_tma(telegram_id))

    assert response.status_code == expected


# --- cancellation ----------------------------------------------------------------------------


async def test_cancel_from_the_pool_refunds_and_restocks(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    # Money goes back, so it takes a role allowed to refund and a fresh password confirmation.
    await add_admin(db_session, 962_000, AdminRole.accountant)
    order, shipment = await add_paid_order(db_session, customer_id=962_001, qty=2)
    stock_before = await _stock(db_session, order.id)

    response = await _cancel(
        client, order.id, headers=admin_confirmed(962_000), reason="  Asked to  "
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["shipment"]["status"] == "cancelled"
    assert body["cancel_reason"] == "Asked to"
    assert body["cancelled_by"] == 962_000
    assert body["cancelled_at"] is not None
    assert body["can_cancel"] is False
    assert body["payment"]["refund_status"] == "pending"
    assert await _stock(db_session, order.id) == stock_before + 2
    assert [c["key"] for c in fake_stripe.calls] == [f"refund-order-{order.id}"]
    payment = await _fresh(db_session, Payment, Payment.order_id == order.id)
    assert payment.stripe_refund_id == "re_1"


async def test_cancel_uses_the_orders_payment_intent(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    order, _ = await add_paid_order(db_session, customer_id=962_002)
    intent = (
        await _fresh(db_session, Payment, Payment.order_id == order.id)
    ).stripe_payment_intent_id

    await _cancel(client, order.id)

    assert [c["payment_intent"] for c in fake_stripe.calls] == [intent]
    assert fake_stripe.calls[0]["metadata"] == {"order_id": str(order.id)}


async def test_cancel_takes_the_order_off_the_courier_and_clears_their_position(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    courier = await add_courier(db_session, 962_010)
    order, shipment = await add_paid_order(db_session, customer_id=962_011)
    shipment.status = ShipmentStatus.assigned
    shipment.courier_id = courier.id
    order.status = OrderStatus.processing
    await db_session.commit()
    await courier_state.record_location(db_session, courier.id, 41.3, 69.2)
    await db_session.commit()

    response = await _cancel(client, order.id)

    assert response.status_code == 200
    fresh = await _fresh(db_session, Shipment, Shipment.id == shipment.id)
    assert (fresh.status, fresh.courier_id) == (ShipmentStatus.cancelled, None)
    assert await db_session.get(CourierLocation, courier.id, populate_existing=True) is None


async def test_cancel_keeps_the_position_of_a_courier_with_other_work(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    courier = await add_courier(db_session, 962_020)
    first, s1 = await add_paid_order(db_session, customer_id=962_021)
    second, s2 = await add_paid_order(db_session, customer_id=962_021)
    for order, shipment in ((first, s1), (second, s2)):
        shipment.status = ShipmentStatus.assigned
        shipment.courier_id = courier.id
        order.status = OrderStatus.processing
    await db_session.commit()
    await courier_state.record_location(db_session, courier.id, 41.3, 69.2)
    await db_session.commit()

    await _cancel(client, first.id)

    assert await db_session.get(CourierLocation, courier.id, populate_existing=True) is not None


@pytest.mark.parametrize(
    ("shipment_status", "order_status"),
    [
        (ShipmentStatus.shipped, OrderStatus.shipped),
        (ShipmentStatus.delivered, OrderStatus.delivered),
        (ShipmentStatus.cancelled, OrderStatus.cancelled),
    ],
)
async def test_cannot_cancel_after_pickup(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    shipment_status: ShipmentStatus,
    order_status: OrderStatus,
) -> None:
    courier = await add_courier(db_session, 962_030 + list(ShipmentStatus).index(shipment_status))
    order, shipment = await add_paid_order(db_session, customer_id=962_035)
    shipment.status = shipment_status
    shipment.courier_id = courier.id if shipment_status != ShipmentStatus.cancelled else None
    order.status = order_status
    await db_session.commit()
    stock_before = await _stock(db_session, order.id)

    response = await _cancel(client, order.id)

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_state"
    assert fake_stripe.calls == []
    assert await _stock(db_session, order.id) == stock_before


async def test_cannot_cancel_an_unpaid_order(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    order, shipment = await add_paid_order(db_session, customer_id=962_040)
    order.status = OrderStatus.pending_payment
    await db_session.delete(shipment)
    await db_session.commit()

    response = await _cancel(client, order.id)

    assert response.status_code == 409


async def test_cancel_unknown_order_is_404(client: AsyncClient, fake_stripe: FakeStripe) -> None:
    assert (await _cancel(client, 999_999)).status_code == 404


@pytest.mark.parametrize("reason", ["", "x" * 501])
async def test_cancel_needs_a_reason(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe, reason: str
) -> None:
    order, _ = await add_paid_order(db_session, customer_id=962_050)
    assert (await _cancel(client, order.id, reason=reason)).status_code == 422


async def test_catalog_managers_cannot_cancel(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    await add_admin(db_session, 962_060, AdminRole.catalog_manager)
    order, _ = await add_paid_order(db_session, customer_id=962_061)

    assert (await _cancel(client, order.id, headers=admin_tma(962_060))).status_code == 403


async def test_customer_sees_the_cancellation(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    order, _ = await add_paid_order(db_session, customer_id=962_070)
    await _cancel(client, order.id)

    tracking = await client.get(f"/orders/{order.id}/tracking", headers=admin_tma(962_070))
    detail = await client.get(f"/orders/{order.id}", headers=admin_tma(962_070))

    assert tracking.json()["status"] == "cancelled"
    assert detail.json()["status"] == "cancelled"


async def test_cancelled_order_leaves_the_courier_pool(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    await add_courier(db_session, 962_080)
    order, _ = await add_paid_order(db_session, customer_id=962_081)
    await _cancel(client, order.id)

    pool = await client.get("/courier/pool", headers=admin_tma(962_080))

    assert order.id not in [s["order_id"] for s in pool.json()]


# --- refunds ---------------------------------------------------------------------------------


async def test_stripe_failure_keeps_the_cancellation_and_marks_the_refund_failed(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    fake_stripe.fail = True
    order, _ = await add_paid_order(db_session, customer_id=963_001)

    response = await _cancel(client, order.id)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["payment"]["refund_status"] == "failed"


async def test_retry_a_failed_refund_with_a_new_key(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    fake_stripe.fail = True
    order, _ = await add_paid_order(db_session, customer_id=963_002)
    await _cancel(client, order.id)
    fake_stripe.fail = False
    fake_stripe.status = "succeeded"

    response = await client.post(f"/internal/orders/{order.id}/refund", headers=INTERNAL_HEADERS)

    assert response.status_code == 200
    assert response.json()["payment"]["refund_status"] == "succeeded"
    first_key, retry_key = (c["key"] for c in fake_stripe.calls)
    assert first_key == f"refund-order-{order.id}"
    assert retry_key.startswith(f"refund-order-{order.id}-retry-")


async def test_retry_without_a_failed_refund_is_409(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: FakeStripe
) -> None:
    order, _ = await add_paid_order(db_session, customer_id=963_003)
    await _cancel(client, order.id)  # refund pending, not failed

    response = await client.post(f"/internal/orders/{order.id}/refund", headers=INTERNAL_HEADERS)

    assert response.status_code == 409
    assert len(fake_stripe.calls) == 1


async def test_retry_for_unknown_order_is_404(client: AsyncClient) -> None:
    response = await client.post("/internal/orders/999999/refund", headers=INTERNAL_HEADERS)
    assert response.status_code == 404


def _refund_event(event_type: str, intent: str, status: str, refund_id: str = "re_wh") -> dict:
    return {
        "type": event_type,
        "data": {"object": {"id": refund_id, "payment_intent": intent, "status": status}},
    }


async def _post_event(client: AsyncClient, monkeypatch: pytest.MonkeyPatch, event: dict) -> None:
    monkeypatch.setattr(stripe_service, "construct_webhook_event", lambda payload, sig: event)
    response = await client.post(
        "/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t"}
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("event_type", "status", "expected"),
    [
        ("refund.updated", "succeeded", RefundStatus.succeeded),
        ("refund.failed", "failed", RefundStatus.failed),
        ("refund.updated", "canceled", RefundStatus.failed),
        ("refund.created", "pending", RefundStatus.pending),
    ],
)
async def test_refund_webhooks_update_the_status(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    monkeypatch: pytest.MonkeyPatch,
    event_type: str,
    status: str,
    expected: RefundStatus,
) -> None:
    order, _ = await add_paid_order(db_session, customer_id=963_010)
    await _cancel(client, order.id)
    intent = (
        await _fresh(db_session, Payment, Payment.order_id == order.id)
    ).stripe_payment_intent_id

    await _post_event(client, monkeypatch, _refund_event(event_type, intent, status))

    payment = await _fresh(db_session, Payment, Payment.order_id == order.id)
    assert payment.refund_status == expected
    assert payment.stripe_refund_id == "re_wh"


async def test_a_late_event_never_downgrades_a_succeeded_refund(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_stripe.status = "succeeded"
    order, _ = await add_paid_order(db_session, customer_id=963_020)
    await _cancel(client, order.id)
    intent = (
        await _fresh(db_session, Payment, Payment.order_id == order.id)
    ).stripe_payment_intent_id

    await _post_event(client, monkeypatch, _refund_event("refund.created", intent, "pending"))

    payment = await _fresh(db_session, Payment, Payment.order_id == order.id)
    assert payment.refund_status == RefundStatus.succeeded


async def test_refund_events_for_payments_not_refunded_here_are_ignored(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    order, _ = await add_paid_order(db_session, customer_id=963_030)
    intent = (
        await _fresh(db_session, Payment, Payment.order_id == order.id)
    ).stripe_payment_intent_id

    await _post_event(client, monkeypatch, _refund_event("refund.updated", intent, "succeeded"))
    await _post_event(client, monkeypatch, _refund_event("refund.updated", "pi_unknown", "failed"))
    await _post_event(
        client,
        monkeypatch,
        {"type": "refund.updated", "data": {"object": {"id": "re_x", "status": "failed"}}},
    )

    payment = await _fresh(db_session, Payment, Payment.order_id == order.id)
    assert payment.refund_status is None
    assert payment.status == PaymentStatus.succeeded
    assert (await _fresh(db_session, Order, Order.id == order.id)).status == OrderStatus.paid


async def test_cancel_looks_again_when_a_courier_moved_the_order_meanwhile(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import order_admin_service

    real = order_admin_service._cancel_rows
    attempts: list[int] = []

    async def lose_the_first_race(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            return False  # as if a claim landed between the read and the guarded UPDATE
        return await real(*args, **kwargs)

    monkeypatch.setattr(order_admin_service, "_cancel_rows", lose_the_first_race)
    order, _ = await add_paid_order(db_session, customer_id=964_001)

    response = await _cancel(client, order.id)

    assert response.status_code == 200
    assert len(attempts) == 2


async def test_cancel_gives_up_after_repeated_interference(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: FakeStripe,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import order_admin_service

    async def always_lose(*args, **kwargs):
        return False

    monkeypatch.setattr(order_admin_service, "_cancel_rows", always_lose)
    order, _ = await add_paid_order(db_session, customer_id=964_002)

    response = await _cancel(client, order.id)

    assert response.status_code == 409
    assert fake_stripe.calls == []
