"""Spec 11: sellers' earnings (one per delivered order) and the money paid out to them."""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.seller_money import SellerEarning

CENT = Decimal("0.01")


def commission_of(goods_total: Decimal, percent: Decimal) -> Decimal:
    """The platform's part of the goods, half-up to cents (12.5% of 10.04 is 1.26)."""
    return (goods_total * percent / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)


async def record_earning(db: AsyncSession, order_id: int) -> None:
    """The seller's share of a delivered order (no commit: delivery commits it).

    Uses the rate copied onto the order at checkout. A second call for the same order (a
    replayed delivery) adds nothing.
    """
    order = (
        await db.execute(
            select(Order.seller_id, Order.currency, Order.subtotal, Order.commission_percent).where(
                Order.id == order_id
            )
        )
    ).one()
    commission = commission_of(order.subtotal, order.commission_percent)
    await db.execute(
        pg_insert(SellerEarning)
        .values(
            order_id=order_id,
            seller_id=order.seller_id,
            currency=order.currency,
            goods_total=order.subtotal,
            commission_percent=order.commission_percent,
            commission=commission,
            amount=order.subtotal - commission,
        )
        .on_conflict_do_nothing(index_elements=[SellerEarning.order_id])
    )
