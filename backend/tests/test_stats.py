from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.enums import AdminRole, OrderStatus, ProductStatus, RefundStatus
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.translation import Translation
from app.models.variant import Variant
from app.services.stats_service import period_start
from tests.admin_factories import add_admin, admin_tma
from tests.courier_factories import INTERNAL_HEADERS, add_paid_order

settings = get_settings()


@pytest.fixture(autouse=True)
async def _isolated_orders(db_session: AsyncSession) -> None:
    # The summary aggregates every order in the database; start each test from none. The outer
    # transaction rolls this back afterwards, like everything else the test writes.
    await db_session.execute(
        text("TRUNCATE orders, order_items, payments, shipments, courier_locations CASCADE")
    )
    await db_session.commit()


async def _sold(
    db: AsyncSession,
    *,
    qty: int = 1,
    days_ago: float = 0,
    refund: RefundStatus | None = None,
    status: OrderStatus = OrderStatus.paid,
) -> Order:
    order, _ = await add_paid_order(db, customer_id=970_001, qty=qty)
    order.placed_at = datetime.now(UTC) - timedelta(days=days_ago)
    order.status = status
    payment = (await db.execute(select(Payment).where(Payment.order_id == order.id))).scalar_one()
    payment.refund_status = refund
    await db.commit()
    return order


async def _summary(client: AsyncClient, period: str = "today") -> dict:
    response = await client.get(
        f"/internal/stats/summary?period={period}", headers=INTERNAL_HEADERS
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_revenue_counts_paid_orders_in_the_period(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _sold(db_session, qty=1)  # 10.00 + 4.99
    await _sold(db_session, qty=2)  # 20.00 + 4.99
    await _sold(db_session, days_ago=3)  # outside "today", inside 7d

    today = await _summary(client, "today")
    week = await _summary(client, "7d")

    assert (today["revenue"], today["orders_count"], today["average_order"]) == (
        "39.98",
        2,
        "19.99",
    )
    assert (week["revenue"], week["orders_count"]) == ("54.97", 3)
    assert today["currency"] == "EUR"


async def test_refunded_orders_are_not_revenue_but_failed_refunds_are(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _sold(db_session, refund=RefundStatus.succeeded, status=OrderStatus.cancelled)
    await _sold(db_session, refund=RefundStatus.pending, status=OrderStatus.cancelled)
    await _sold(db_session, refund=RefundStatus.failed, status=OrderStatus.cancelled)

    body = await _summary(client)

    assert (body["revenue"], body["orders_count"]) == ("14.99", 1)


async def test_unpaid_orders_are_not_revenue(client: AsyncClient, db_session: AsyncSession) -> None:
    order = await _sold(db_session, status=OrderStatus.pending_payment)
    payment = (
        await db_session.execute(select(Payment).where(Payment.order_id == order.id))
    ).scalar_one()
    payment.status = "requires_payment_method"
    await db_session.commit()

    body = await _summary(client)

    assert (body["revenue"], body["orders_count"], body["average_order"]) == ("0.00", 0, "0.00")


async def test_status_counts_cover_every_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _sold(db_session)
    await _sold(db_session, status=OrderStatus.shipped, days_ago=100)  # not period-bound

    counts = (await _summary(client))["status_counts"]

    assert counts == {
        "pending_payment": 0,
        "paid": 1,
        "processing": 0,
        "shipped": 1,
        "delivered": 0,
        "cancelled": 0,
    }


async def test_top_products_by_quantity(client: AsyncClient, db_session: AsyncSession) -> None:
    big = await _sold(db_session, qty=5)
    await _sold(db_session, qty=2)
    product_id = await db_session.scalar(
        select(Variant.product_id)
        .join(OrderItem, OrderItem.variant_id == Variant.id)
        .where(OrderItem.order_id == big.id)
    )
    db_session.add(
        Translation(
            entity_type="product", entity_id=product_id, locale="en", field="name", value="Balm"
        )
    )
    await db_session.commit()

    top = (await _summary(client))["top_products"]

    assert top[0] == {"product_id": product_id, "name": "Balm", "qty": 5, "revenue": "50.00"}
    assert [t["qty"] for t in top] == [5, 2]


async def test_low_stock_skips_archived_products(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    order = await _sold(db_session)
    variant = (
        await db_session.execute(
            select(Variant)
            .join(OrderItem, OrderItem.variant_id == Variant.id)
            .where(OrderItem.order_id == order.id)
        )
    ).scalar_one()
    variant.stock_qty = -1
    await db_session.commit()

    low = (await _summary(client))["low_stock"]
    assert low[0]["variant_id"] == variant.id
    assert low[0]["stock_qty"] == -1

    product = await db_session.get(Product, variant.product_id)
    product.status = ProductStatus.archived
    await db_session.commit()

    low = (await _summary(client))["low_stock"]
    assert variant.id not in [v["variant_id"] for v in low]


def test_periods_start_at_local_midnight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "shop_timezone", "Asia/Tashkent")  # UTC+5
    # 20:00 UTC on 10 March is 01:00 on 11 March in Tashkent.
    now = datetime(2026, 3, 10, 20, 0, tzinfo=UTC)

    assert period_start("today", now) == datetime(2026, 3, 10, 19, 0, tzinfo=UTC)
    assert period_start("7d", now) == datetime(2026, 3, 4, 19, 0, tzinfo=UTC)
    assert period_start("30d", now) == datetime(2026, 2, 9, 19, 0, tzinfo=UTC)


async def test_unknown_period_is_422(client: AsyncClient) -> None:
    response = await client.get("/internal/stats/summary?period=1y", headers=INTERNAL_HEADERS)
    assert response.status_code == 422


@pytest.mark.parametrize("role", [AdminRole.dispatcher, AdminRole.catalog_manager])
async def test_summary_is_for_owners_only(
    client: AsyncClient, db_session: AsyncSession, role: AdminRole
) -> None:
    telegram_id = 971_000 + list(AdminRole).index(role)
    await add_admin(db_session, telegram_id, role)

    response = await client.get("/internal/stats/summary", headers=admin_tma(telegram_id))

    assert response.status_code == 403


async def test_owner_sees_the_summary(client: AsyncClient, db_session: AsyncSession) -> None:
    await add_admin(db_session, 971_100, AdminRole.owner)
    response = await client.get("/internal/stats/summary", headers=admin_tma(971_100))
    assert response.status_code == 200
    assert Decimal(response.json()["revenue"]) >= 0
