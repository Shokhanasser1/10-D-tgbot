from sqlalchemy import Row, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.enums import (
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    RefundStatus,
    ShipmentStatus,
)
from app.models.order import Order
from app.models.payment import Payment
from app.models.shipment import Shipment
from app.schemas.orders import OrderDetailOut, OrderItemOut, OrderListItemOut
from app.services import notification_events, order_admin_service, stock_service


async def _get_order_with_payment(db: AsyncSession, order_id: int) -> Order:
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.payment), selectinload(Order.shipment))
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise NotFoundError("Order not found")
    return order


async def _move_to_pool(db: AsyncSession, order_id: int) -> Row | None:
    """pending_payment -> paid and a shipment in the courier pool (no commit).

    A single guarded transition: a replay, or a late event for an order that has moved on,
    matches nothing and returns None.
    """
    return (
        await db.execute(
            update(Order)
            .where(Order.id == order_id, Order.status == OrderStatus.pending_payment)
            .values(status=OrderStatus.paid)
            .returning(Order.id, Order.reserved_until)
            .execution_options(synchronize_session=False)
        )
    ).first()


async def _create_shipment(db: AsyncSession, order_id: int) -> None:
    await db.execute(
        pg_insert(Shipment)
        .values(order_id=order_id, status=ShipmentStatus.processing)
        .on_conflict_do_nothing(index_elements=[Shipment.order_id])
    )


async def mark_order_paid(
    db: AsyncSession, order_id: int, charge_ids: dict[str, str] | None = None
) -> None:
    """Confirm payment: order -> paid, shipment into the courier pool.

    Stripe and Telegram redeliver events, so a replay, or a late event for an order that has
    since moved on (a courier holds it, or it was cancelled), changes nothing; in particular
    stock is never taken twice. `charge_ids` are Telegram's charge IDs, stored on the payment.
    """
    moved = await _move_to_pool(db, order_id)
    if moved is None:
        status = await db.scalar(select(Order.status).where(Order.id == order_id))
        if status is None:
            raise NotFoundError("Order not found")
        if status == OrderStatus.cancelled:
            await _refund_late_payment(db, order_id, charge_ids)
        return

    await db.execute(
        update(Payment)
        .where(Payment.order_id == order_id)
        .values(status=PaymentStatus.succeeded, **(charge_ids or {}))
        .execution_options(synchronize_session=False)
    )
    await _create_shipment(db, order_id)

    # Checkout already reserved the stock of new orders. Orders placed before reservations
    # existed (reserved_until is NULL) take it now; the sale stands even if the shelf ran out
    # meanwhile, so flag it and let the owner decide.
    if moved.reserved_until is None and await stock_service.take(db, order_id):
        await db.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(stock_shortfall=True)
            .execution_options(synchronize_session=False)
        )

    await notification_events.order_paid(db, order_id)
    await db.commit()


async def confirm_cash_order(db: AsyncSession, order_id: int) -> None:
    """Cash on delivery: the order goes to the pool at once; money is collected on delivery.

    No commit: checkout commits it together with the reservation.
    """
    if await _move_to_pool(db, order_id) is None:
        raise NotFoundError("Order not found")
    await _create_shipment(db, order_id)
    await notification_events.order_paid(db, order_id)


async def _refund_late_payment(
    db: AsyncSession, order_id: int, charge_ids: dict[str, str] | None = None
) -> None:
    """Money arrived for an order that had already expired: give all of it back.

    Only a payment that has no refund yet qualifies, so redeliveries and orders an admin
    cancelled (their refund is already under way) start nothing. Stock is untouched: it went
    back on the shelf when the order expired. Stripe refunds automatically; Telegram Payments
    has no refund API, so an owner refunds by hand in the provider's cabinet.
    """
    method = await db.scalar(select(Payment.method).where(Payment.order_id == order_id))
    manual = method == PaymentMethod.telegram
    payment_id = await db.scalar(
        update(Payment)
        .where(Payment.order_id == order_id, Payment.refund_status.is_(None))
        .values(
            status=PaymentStatus.succeeded,
            refund_status=RefundStatus.manual_required if manual else RefundStatus.pending,
            **(charge_ids or {}),
        )
        .returning(Payment.id)
        .execution_options(synchronize_session=False)
    )
    if payment_id is None:
        await db.commit()
        return
    if manual:
        await notification_events.refund_manual_required(db, order_id)
        await db.commit()
        return
    stripe_id = await db.scalar(
        select(Payment.stripe_payment_intent_id).where(Payment.order_id == order_id)
    )
    await db.commit()
    if stripe_id is not None:
        key = f"late-payment-{order_id}"
        await order_admin_service.refund_payment(db, order_id, stripe_id, key)


async def mark_order_payment_failed(db: AsyncSession, order_id: int) -> None:
    order = await _get_order_with_payment(db, order_id)

    if order.payment is not None and order.payment.status != PaymentStatus.succeeded:
        order.payment.status = PaymentStatus.requires_payment_method

    await db.commit()


async def list_orders_for_user(db: AsyncSession, telegram_id: int) -> list[OrderListItemOut]:
    stmt = select(Order).where(Order.telegram_id == telegram_id).order_by(Order.placed_at.desc())
    orders = (await db.execute(stmt)).scalars().all()
    return [
        OrderListItemOut(
            id=o.id, status=o.status, currency=o.currency, total=o.total, placed_at=o.placed_at
        )
        for o in orders
    ]


async def get_order_detail(db: AsyncSession, telegram_id: int, order_id: int) -> OrderDetailOut:
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.telegram_id == telegram_id)
        .options(
            selectinload(Order.items), selectinload(Order.payment), selectinload(Order.shipment)
        )
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise NotFoundError("Order not found")

    return OrderDetailOut(
        id=order.id,
        status=order.status,
        currency=order.currency,
        subtotal=order.subtotal,
        shipping_cost=order.shipping_cost,
        total=order.total,
        delivery_address=order.delivery_address,
        placed_at=order.placed_at,
        items=[
            OrderItemOut(
                id=item.id,
                variant_id=item.variant_id,
                product_name_snapshot=item.product_name_snapshot,
                qty=item.qty,
                unit_price_snapshot=item.unit_price_snapshot,
            )
            for item in order.items
        ],
        payment_status=order.payment.status if order.payment is not None else None,
        shipment_status=order.shipment.status if order.shipment is not None else None,
        refund_status=order.payment.refund_status if order.payment is not None else None,
        payment_method=order.payment_method,
        reserved_until=order.reserved_until,
        cancel_reason=order.cancel_reason,
    )
