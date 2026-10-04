"""Spec 11 §4: a seller earns their share of an order when it is delivered, once."""

import itertools
from decimal import Decimal

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.seller_money import SellerEarning
from app.services import dispatch_service, earnings_service
from tests.courier_factories import add_courier, add_customer, add_paid_order
from tests.factories import add_seller

_ids = itertools.count(899_001)


@pytest.mark.parametrize(
    ("goods", "percent", "commission"),
    [
        ("30.00", "10", "3.00"),
        ("10.01", "12.5", "1.25"),  # 1.25125
        ("10.04", "12.5", "1.26"),  # 1.255, half-up
        ("99.99", "0", "0.00"),
        ("20.00", "100", "20.00"),
    ],
)
def test_commission_is_rounded_half_up_to_cents(goods: str, percent: str, commission: str) -> None:
    assert earnings_service.commission_of(Decimal(goods), Decimal(percent)) == Decimal(commission)


async def _delivered(db: AsyncSession, seller_id: int, qty: int) -> Order:
    courier_tid = next(_ids)
    await add_customer(db, courier_tid)
    courier = await add_courier(db, courier_tid)
    order, shipment = await add_paid_order(db, customer_id=next(_ids), seller_id=seller_id, qty=qty)
    await dispatch_service.claim(db, courier, shipment.id)
    await dispatch_service.pickup(db, courier, shipment.id)
    await dispatch_service.deliver(db, courier, shipment.id)
    return order


async def test_delivery_records_the_sellers_share(db_session: AsyncSession) -> None:
    seller = await add_seller(db_session, "Lola")
    order = await _delivered(db_session, seller.id, qty=3)

    earning = await db_session.scalar(
        select(SellerEarning).where(SellerEarning.order_id == order.id)
    )

    assert earning is not None
    assert (earning.seller_id, earning.currency) == (seller.id, "EUR")
    assert (earning.goods_total, earning.commission_percent) == (Decimal("30.00"), Decimal("10.00"))
    assert (earning.commission, earning.amount) == (Decimal("3.00"), Decimal("27.00"))


async def test_the_rate_on_the_order_wins_over_a_later_change(db_session: AsyncSession) -> None:
    seller = await add_seller(db_session, "Lola")
    courier_tid = next(_ids)
    await add_customer(db_session, courier_tid)
    courier = await add_courier(db_session, courier_tid)
    order, shipment = await add_paid_order(db_session, customer_id=next(_ids), seller_id=seller.id)
    seller.commission_percent = Decimal("50")
    await db_session.commit()

    await dispatch_service.claim(db_session, courier, shipment.id)
    await dispatch_service.pickup(db_session, courier, shipment.id)
    await dispatch_service.deliver(db_session, courier, shipment.id)

    earning = await db_session.scalar(
        select(SellerEarning).where(SellerEarning.order_id == order.id)
    )
    assert earning is not None and earning.commission_percent == Decimal("10.00")


async def test_an_order_earns_once(db_session: AsyncSession) -> None:
    seller = await add_seller(db_session, "Lola")
    order = await _delivered(db_session, seller.id, qty=1)

    await earnings_service.record_earning(db_session, order.id)
    await db_session.commit()

    count = await db_session.scalar(
        select(func.count()).select_from(SellerEarning).where(SellerEarning.order_id == order.id)
    )
    assert count == 1


async def test_an_undelivered_order_earns_nothing(db_session: AsyncSession) -> None:
    seller = await add_seller(db_session, "Lola")
    order, _ = await add_paid_order(db_session, customer_id=next(_ids), seller_id=seller.id)
    await db_session.execute(update(Order).where(Order.id == order.id).values(status="cancelled"))
    await db_session.commit()

    count = await db_session.scalar(
        select(func.count()).select_from(SellerEarning).where(SellerEarning.seller_id == seller.id)
    )
    assert count == 0
