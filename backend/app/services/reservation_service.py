"""Expiring unpaid orders whose stock hold ran out (Spec 4).

Checkout subtracts stock and sets `orders.reserved_until`. If the customer has not paid by then,
the sweeper cancels the order, cancels its PaymentIntent, puts the stock back and returns the
items to the customer's cart. Several API processes may sweep at once: every step is either
idempotent or a guarded UPDATE, so at most one of them expires a given order.
"""

import asyncio
import logging
from collections.abc import Callable

import stripe
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OrderStatus, PaymentStatus
from app.models.order import Order
from app.models.payment import Payment
from app.services import cart_service, notification_events, stock_service, stripe_service

logger = logging.getLogger(__name__)

EXPIRED_REASON = "payment_expired"
SETUP_FAILED_REASON = "payment_setup_failed"
_BATCH = 100


async def release_unpaid_order(db: AsyncSession, order_id: int) -> None:
    """Stock back on the shelf, payment marked cancelled, items back in the cart (no commit).

    Only for an order this caller has just moved from pending_payment to cancelled.
    """
    await stock_service.put_back(db, order_id)
    await db.execute(
        update(Payment)
        .where(Payment.order_id == order_id)
        .values(status=PaymentStatus.canceled)
        .execution_options(synchronize_session=False)
    )
    await cart_service.restore_order_items(db, order_id)


async def expire_order(db: AsyncSession, order_id: int) -> bool:
    """Expire one overdue unpaid order. Returns True if this call expired it."""
    if order_id not in await due_order_ids(db, only=order_id):
        return False  # not due yet, already paid or already expired: never touch its payment
    payment_intent = await db.scalar(
        select(Payment.stripe_payment_intent_id).where(Payment.order_id == order_id)
    )
    # Cancel the PaymentIntent first: once the order is expired the customer must not be able
    # to pay it. If Stripe says it already went through, the success webhook will mark the
    # order paid with its stock still held, so leave it alone.
    if payment_intent is not None:
        try:
            cancelled = await stripe_service.cancel_payment_intent(payment_intent)
        except stripe.StripeError:
            logger.warning("could not cancel payment for order %s; retrying later", order_id)
            return False
        if not cancelled:
            return False

    expired = await db.scalar(
        update(Order)
        .where(
            Order.id == order_id,
            Order.status == OrderStatus.pending_payment,
            Order.reserved_until < func.now(),
        )
        .values(status=OrderStatus.cancelled, cancelled_at=func.now(), cancel_reason=EXPIRED_REASON)
        .returning(Order.id)
        .execution_options(synchronize_session=False)
    )
    if expired is None:  # paid meanwhile, or another worker got there first
        await db.rollback()
        return False

    await release_unpaid_order(db, order_id)
    await notification_events.order_expired(db, order_id)
    await db.commit()
    return True


async def due_order_ids(
    db: AsyncSession, limit: int = _BATCH, only: int | None = None
) -> list[int]:
    """Unpaid orders whose hold has run out, oldest first (optionally just one order)."""
    stmt = select(Order.id).where(
        Order.status == OrderStatus.pending_payment,
        Order.reserved_until.is_not(None),
        Order.reserved_until < func.now(),
    )
    if only is not None:
        stmt = stmt.where(Order.id == only)
    rows = await db.scalars(stmt.order_by(Order.reserved_until).limit(limit))
    return list(rows)


async def sweep_once(session_factory: Callable[[], AsyncSession]) -> int:
    """Expire every overdue order found now, each in its own transaction. Returns the count."""
    async with session_factory() as db:
        order_ids = await due_order_ids(db)

    expired = 0
    for order_id in order_ids:
        try:
            async with session_factory() as db:
                expired += int(await expire_order(db, order_id))
        except Exception:
            # One broken order must not stop the others from being expired.
            logger.exception("expiring order %s failed", order_id)
    return expired


async def run_sweeper(session_factory: Callable[[], AsyncSession], interval_seconds: int) -> None:
    """Background loop started with the app; cancelled on shutdown."""
    while True:
        try:
            count = await sweep_once(session_factory)
            if count:
                logger.info("expired %s unpaid order(s)", count)
        except Exception:
            logger.exception("reservation sweep failed")
        await asyncio.sleep(interval_seconds)
