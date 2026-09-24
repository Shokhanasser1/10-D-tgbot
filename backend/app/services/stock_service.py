"""Moving an order's quantities off and back onto the shelf.

Variant rows are updated in ascending id order, the last step of the global lock order
(courier -> shipment -> order -> variants), so two orders sharing variants cannot deadlock.
"""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import OrderItem
from app.models.variant import Variant


async def _adjust(db: AsyncSession, order_id: int, sign: int) -> bool:
    lines = (
        await db.execute(
            select(OrderItem.variant_id, func.sum(OrderItem.qty))
            .where(OrderItem.order_id == order_id)
            .group_by(OrderItem.variant_id)
            .order_by(OrderItem.variant_id)
        )
    ).all()
    went_negative = False
    for variant_id, qty in lines:
        remaining = await db.scalar(
            update(Variant)
            .where(Variant.id == variant_id)
            .values(stock_qty=Variant.stock_qty + sign * qty)
            .returning(Variant.stock_qty)
            .execution_options(synchronize_session=False)
        )
        went_negative = went_negative or (remaining is not None and remaining < 0)
    return went_negative


async def take(db: AsyncSession, order_id: int) -> bool:
    """Subtract the order's quantities. Returns True if any variant went below zero."""
    return await _adjust(db, order_id, -1)


async def put_back(db: AsyncSession, order_id: int) -> None:
    await _adjust(db, order_id, +1)
