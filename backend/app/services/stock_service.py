"""Moving an order's quantities off and back onto the shelf.

Variant rows are updated in ascending id order, the last step of the global lock order
(courier -> shipment -> order -> variants), so two orders sharing variants cannot deadlock.
"""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.order import OrderItem
from app.models.variant import Variant


async def _lines(db: AsyncSession, order_id: int) -> list[tuple[int, int]]:
    """(variant_id, total qty) per variant of the order, in ascending variant id order."""
    rows = await db.execute(
        select(OrderItem.variant_id, func.sum(OrderItem.qty))
        .where(OrderItem.order_id == order_id)
        .group_by(OrderItem.variant_id)
        .order_by(OrderItem.variant_id)
    )
    return [(variant_id, int(qty)) for variant_id, qty in rows.all()]


async def _adjust(db: AsyncSession, order_id: int, sign: int) -> bool:
    went_negative = False
    for variant_id, qty in await _lines(db, order_id):
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


async def reserve(db: AsyncSession, order_id: int) -> None:
    """Hold the order's quantities for checkout, all or nothing.

    Each variant is a guarded UPDATE that only matches while enough is left, so two checkouts
    racing for the last unit are settled by the row lock: one matches, the other does not.
    On a short line the caller's transaction is rolled back and ConflictError names the SKU.
    """
    for variant_id, qty in await _lines(db, order_id):
        reserved = await db.scalar(
            update(Variant)
            .where(Variant.id == variant_id, Variant.stock_qty >= qty)
            .values(stock_qty=Variant.stock_qty - qty)
            .returning(Variant.id)
            .execution_options(synchronize_session=False)
        )
        if reserved is None:
            sku = await db.scalar(select(Variant.sku).where(Variant.id == variant_id))
            await db.rollback()
            raise ConflictError(f"Insufficient stock for variant {sku}", code="insufficient_stock")
