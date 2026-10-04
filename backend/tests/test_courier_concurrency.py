"""Real races between independent database sessions.

Every other test shares one connection inside a rolled-back transaction, which cannot express
parallelism. These use sessions that genuinely commit, so they clean up by truncating.
"""

import asyncio
from collections.abc import AsyncGenerator, Callable

import pytest
import stripe
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models import Base
from app.models.courier import Courier
from app.models.enums import OrderStatus, ShipmentStatus
from app.models.order import Order
from app.models.shipment import Shipment
from app.services import courier_state, stripe_service
from tests.courier_factories import (
    INTERNAL_HEADERS,
    add_courier,
    add_customer,
    add_paid_order,
    tma_headers,
)
from tests.factories import default_seller_id

SessionFactory = Callable[[], AsyncSession]


@pytest.fixture
async def sessions(test_engine: AsyncEngine) -> AsyncGenerator[SessionFactory, None]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:  # one session per request, as in production
            yield session

    app.dependency_overrides[get_db] = _get_db
    try:
        yield factory
    finally:
        app.dependency_overrides.clear()
        async with test_engine.begin() as conn:
            tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
            await conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def http(sessions: SessionFactory) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def make_courier(sessions: SessionFactory, telegram_id: int) -> Courier:
    # Create the Telegram user up front: two first-ever requests upserting the same user at once
    # would trip over each other, which is a different race from the one under test.
    async with sessions() as session:
        await add_customer(session, telegram_id)
        return await add_courier(session, telegram_id)


def claim(http: AsyncClient, shipment_id: int, telegram_id: int) -> "asyncio.Future[Response]":
    return asyncio.ensure_future(
        http.post(f"/courier/deliveries/{shipment_id}/claim", headers=tma_headers(telegram_id))
    )


async def test_five_couriers_racing_for_one_order_produce_exactly_one_winner(
    sessions: SessionFactory, http: AsyncClient
) -> None:
    telegram_ids = [850_001 + i for i in range(5)]
    couriers = {tid: await make_courier(sessions, tid) for tid in telegram_ids}
    async with sessions() as session:
        _, shipment = await add_paid_order(session, customer_id=850_100)

    responses = await asyncio.gather(*(claim(http, shipment.id, tid) for tid in telegram_ids))

    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409, 409]
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {"shipment_taken"}
    winner = next(
        tid for tid, r in zip(telegram_ids, responses, strict=True) if r.status_code == 200
    )
    async with sessions() as session:
        row = (await session.execute(select(Shipment.courier_id, Shipment.status))).one()
        assert (row.courier_id, row.status) == (couriers[winner].id, ShipmentStatus.assigned)
        assert await session.scalar(select(Order.status)) == OrderStatus.processing


async def test_the_delivery_limit_holds_when_one_courier_claims_twice_at_once(
    sessions: SessionFactory, http: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "max_active_deliveries_per_courier", 1)
    telegram_id = 850_201
    await make_courier(sessions, telegram_id)
    async with sessions() as session:
        shipments = [(await add_paid_order(session, customer_id=850_300))[1] for _ in range(2)]

    # Make the check-then-act window wide and deterministic. Each request pauses right after
    # counting, waiting up to 0.5s for the other to arrive at the same point. With the courier
    # row lock the second request never gets there while the first is paused, so the first
    # simply times out and finishes; without the lock both count 0 and both claims succeed.
    real_count = courier_state.count_active
    arrivals = 0
    both_counted = asyncio.Event()

    async def count_then_wait_for_the_other(db: AsyncSession, courier_id: int) -> int:
        nonlocal arrivals
        count = await real_count(db, courier_id)
        arrivals += 1
        if arrivals == 2:
            both_counted.set()
        try:
            await asyncio.wait_for(both_counted.wait(), timeout=0.5)
        except TimeoutError:
            pass
        return count

    monkeypatch.setattr(courier_state, "count_active", count_then_wait_for_the_other)

    responses = await asyncio.gather(*(claim(http, s.id, telegram_id) for s in shipments))

    assert sorted(r.status_code for r in responses) == [200, 409]
    assert next(r for r in responses if r.status_code == 409).json()["code"] == (
        "delivery_limit_reached"
    )


async def test_owner_release_racing_a_pickup_never_errors_and_ends_consistent(
    sessions: SessionFactory, http: AsyncClient
) -> None:
    telegram_id = 850_401
    courier = await make_courier(sessions, telegram_id)

    for _ in range(15):  # interleavings vary run to run, so try several
        async with sessions() as session:
            order, shipment = await add_paid_order(session, customer_id=850_500)
            shipment.status = ShipmentStatus.assigned
            shipment.courier_id = courier.id
            order.status = OrderStatus.processing
            await session.commit()

        pickup, release = await asyncio.gather(
            http.post(
                f"/courier/deliveries/{shipment.id}/pickup", headers=tma_headers(telegram_id)
            ),
            http.post(f"/internal/shipments/{shipment.id}/release", headers=INTERNAL_HEADERS),
        )

        # Either the pickup lands first and is then released, or the release wins and the
        # pickup finds nothing of the courier's to pick up. Never a 500, never a split state.
        assert release.status_code == 200
        assert pickup.status_code in (200, 404)
        async with sessions() as session:
            final = (
                await session.execute(
                    select(Shipment.status, Shipment.courier_id).where(Shipment.id == shipment.id)
                )
            ).one()
            order_status = await session.scalar(select(Order.status).where(Order.id == order.id))
        assert (final.status, final.courier_id, order_status) == (
            ShipmentStatus.processing,
            None,
            OrderStatus.paid,
        )


async def _no_refund(payment_intent_id: str, idempotency_key: str, metadata: dict) -> object:
    raise stripe.APIConnectionError("not under test")


async def test_cancel_racing_a_pickup_ends_in_exactly_one_of_them(
    sessions: SessionFactory, http: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(stripe_service, "create_refund", _no_refund)
    telegram_id = 850_601
    courier = await make_courier(sessions, telegram_id)

    for _ in range(15):
        async with sessions() as session:
            order, shipment = await add_paid_order(session, customer_id=850_700)
            shipment.status = ShipmentStatus.assigned
            shipment.courier_id = courier.id
            order.status = OrderStatus.processing
            await session.commit()

        pickup, cancel = await asyncio.gather(
            http.post(
                f"/courier/deliveries/{shipment.id}/pickup", headers=tma_headers(telegram_id)
            ),
            http.post(
                f"/internal/orders/{order.id}/cancel",
                json={"reason": "race"},
                headers=INTERNAL_HEADERS,
            ),
        )

        async with sessions() as session:
            final = (
                await session.execute(
                    select(Shipment.status, Shipment.courier_id).where(Shipment.id == shipment.id)
                )
            ).one()
            order_status = await session.scalar(select(Order.status).where(Order.id == order.id))
        if cancel.status_code == 200:
            assert pickup.status_code in (404, 409)
            assert (final.status, final.courier_id, order_status) == (
                ShipmentStatus.cancelled,
                None,
                OrderStatus.cancelled,
            )
        else:
            assert (cancel.status_code, pickup.status_code) == (409, 200)
            assert (final.status, order_status) == (ShipmentStatus.shipped, OrderStatus.shipped)


async def test_cancel_racing_a_claim_ends_in_exactly_one_of_them(
    sessions: SessionFactory, http: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(stripe_service, "create_refund", _no_refund)
    telegram_id = 850_801
    await make_courier(sessions, telegram_id)

    for _ in range(15):
        async with sessions() as session:
            order, shipment = await add_paid_order(session, customer_id=850_900)

        claim_response, cancel = await asyncio.gather(
            claim(http, shipment.id, telegram_id),
            http.post(
                f"/internal/orders/{order.id}/cancel",
                json={"reason": "race"},
                headers=INTERNAL_HEADERS,
            ),
        )

        async with sessions() as session:
            final = (
                await session.execute(
                    select(Shipment.status, Shipment.courier_id).where(Shipment.id == shipment.id)
                )
            ).one()
            order_status = await session.scalar(select(Order.status).where(Order.id == order.id))
        # A claim that lands first is simply cancelled on top (still before pickup); a cancel
        # that lands first leaves the claim nothing to take.
        assert cancel.status_code == 200
        assert claim_response.status_code in (200, 409)
        assert (final.status, final.courier_id, order_status) == (
            ShipmentStatus.cancelled,
            None,
            OrderStatus.cancelled,
        )


async def test_two_customers_checking_out_the_last_unit_produce_exactly_one_order(
    sessions: SessionFactory, http: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from decimal import Decimal
    from types import SimpleNamespace

    from app.models.category import Category
    from app.models.enums import ProductStatus
    from app.models.product import Product
    from app.models.variant import Variant

    async def _intent(amount, currency, metadata):
        return SimpleNamespace(id=f"pi_race_{metadata['order_id']}", amount=100, client_secret="s")

    monkeypatch.setattr(stripe_service, "create_payment_intent", _intent)
    address = {
        "street": "Amir Temur 1",
        "city": "Tashkent",
        "postal_code": "100000",
        "country": "UZ",
        "phone": "+998901234567",
    }

    for round_no in range(10):
        async with sessions() as session:
            category = Category(slug=f"race-{round_no}", sort_order=0)
            session.add(category)
            await session.flush()
            product = Product(
                seller_id=await default_seller_id(session),
                category_id=category.id,
                base_sku=f"RACE-{round_no}",
                base_price=Decimal("1.00"),
                status=ProductStatus.active,
            )
            session.add(product)
            await session.flush()
            variant = Variant(
                product_id=product.id, sku=f"RACE-{round_no}-V", price=Decimal("1"), stock_qty=1
            )
            session.add(variant)
            await session.commit()
            variant_id = variant.id

        buyers = (851_000 + round_no * 2, 851_001 + round_no * 2)
        for buyer in buyers:
            async with sessions() as session:
                await add_customer(session, buyer)
            added = await http.post(
                "/cart/items", json={"variant_id": variant_id, "qty": 1}, headers=tma_headers(buyer)
            )
            assert added.status_code in (200, 201)

        responses = await asyncio.gather(
            *(
                http.post(
                    "/checkout", json={"delivery_address": address}, headers=tma_headers(buyer)
                )
                for buyer in buyers
            )
        )

        assert sorted(r.status_code for r in responses) == [200, 409]
        async with sessions() as session:
            assert (
                await session.scalar(select(Variant.stock_qty).where(Variant.id == variant_id)) == 0
            )
