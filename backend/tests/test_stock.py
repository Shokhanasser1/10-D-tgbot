import itertools
from decimal import Decimal
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.enums import OrderStatus, PaymentStatus, ProductStatus
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.shipment import Shipment
from app.models.variant import Variant
from app.services import stripe_service
from tests.courier_factories import add_customer

_seq = itertools.count(1)


async def _pending_order(
    db: AsyncSession, lines: list[tuple[str, int]], stock: dict[str, int]
) -> tuple[int, dict[str, int]]:
    """An unpaid order; `lines` are (variant key, qty), `stock` the starting stock per key."""
    n = next(_seq)
    await add_customer(db, 950_000 + n)
    category = Category(slug=f"stock-cat-{n}", sort_order=0)
    db.add(category)
    await db.flush()
    product = Product(
        category_id=category.id,
        base_sku=f"STOCK-{n}",
        base_price=Decimal("1.00"),
        status=ProductStatus.active,
    )
    db.add(product)
    await db.flush()
    variants = {
        key: Variant(
            product_id=product.id, sku=f"STOCK-{n}-{key}", price=Decimal("1.00"), stock_qty=qty
        )
        for key, qty in stock.items()
    }
    db.add_all(variants.values())
    order = Order(
        telegram_id=950_000 + n,
        status=OrderStatus.pending_payment,
        currency="EUR",
        subtotal=Decimal("1.00"),
        shipping_cost=Decimal("0"),
        total=Decimal("1.00"),
        delivery_address={"city": "Tashkent"},
    )
    db.add(order)
    await db.flush()
    db.add_all(
        [
            OrderItem(
                order_id=order.id,
                variant_id=variants[key].id,
                product_name_snapshot="X",
                qty=qty,
                unit_price_snapshot=Decimal("1.00"),
            )
            for key, qty in lines
        ]
        + [
            Payment(
                order_id=order.id,
                stripe_payment_intent_id=f"pi_stock_{n}",
                status=PaymentStatus.requires_payment_method,
                amount=Decimal("1.00"),
                currency="EUR",
            )
        ]
    )
    await db.commit()
    return order.id, {key: v.id for key, v in variants.items()}


async def _stock(db: AsyncSession, variant_ids: dict[str, int]) -> dict[str, int]:
    rows = await db.execute(
        select(Variant.id, Variant.stock_qty).where(Variant.id.in_(variant_ids.values()))
    )
    by_id = dict(rows.all())
    return {key: by_id[vid] for key, vid in variant_ids.items()}


async def _order(db: AsyncSession, order_id: int) -> Order:
    return (
        await db.execute(
            select(Order).where(Order.id == order_id).execution_options(populate_existing=True)
        )
    ).scalar_one()


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


async def test_payment_takes_stock_summing_lines_of_one_variant(
    db_session: AsyncSession, pay
) -> None:
    order_id, variants = await _pending_order(
        db_session, [("a", 2), ("b", 1), ("a", 1)], {"a": 5, "b": 4}
    )

    await pay(order_id)

    assert await _stock(db_session, variants) == {"a": 2, "b": 3}
    order = await _order(db_session, order_id)
    assert (order.status, order.stock_shortfall) == (OrderStatus.paid, False)


async def test_redelivered_payment_event_takes_stock_once(db_session: AsyncSession, pay) -> None:
    order_id, variants = await _pending_order(db_session, [("a", 2)], {"a": 5})

    await pay(order_id)
    await pay(order_id)

    assert await _stock(db_session, variants) == {"a": 3}
    shipments = await db_session.scalars(select(Shipment).where(Shipment.order_id == order_id))
    assert len(shipments.all()) == 1


async def test_selling_more_than_the_shelf_flags_a_shortfall(db_session: AsyncSession, pay) -> None:
    order_id, variants = await _pending_order(db_session, [("a", 3), ("b", 1)], {"a": 1, "b": 9})

    await pay(order_id)

    assert await _stock(db_session, variants) == {"a": -2, "b": 8}
    order = await _order(db_session, order_id)
    assert (order.status, order.stock_shortfall) == (OrderStatus.paid, True)


async def test_late_payment_event_for_a_cancelled_order_refunds_and_takes_no_stock(
    db_session: AsyncSession, pay, monkeypatch: pytest.MonkeyPatch
) -> None:
    refunds: list[str] = []

    async def _refund(payment_intent_id: str, idempotency_key: str, metadata: dict):
        refunds.append(idempotency_key)
        return SimpleNamespace(id="re_late", status="pending")

    monkeypatch.setattr(stripe_service, "create_refund", _refund)
    order_id, variants = await _pending_order(db_session, [("a", 2)], {"a": 5})
    order = await _order(db_session, order_id)
    order.status = OrderStatus.cancelled
    await db_session.commit()

    await pay(order_id)

    assert refunds == [f"late-payment-{order_id}"]

    assert (await _order(db_session, order_id)).status == OrderStatus.cancelled
    assert await _stock(db_session, variants) == {"a": 5}
    assert (
        await db_session.scalar(select(Shipment.id).where(Shipment.order_id == order_id))
    ) is None


async def test_payment_event_for_unknown_order_is_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi", "metadata": {"order_id": "99999999"}}},
    }
    monkeypatch.setattr(stripe_service, "construct_webhook_event", lambda payload, sig: event)

    response = await client.post(
        "/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t"}
    )

    assert response.status_code == 404
