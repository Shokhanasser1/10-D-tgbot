from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.enums import OrderStatus, PaymentStatus, ShipmentStatus
from app.models.order import Order
from app.models.shipment import Shipment
from app.schemas.orders import OrderDetailOut, OrderItemOut, OrderListItemOut

# Stripe redelivers events. Once an order is past payment (a courier may already hold it), a
# replayed payment_intent.succeeded must not drag it back to "paid".
_PAST_PAYMENT = frozenset(
    {OrderStatus.paid, OrderStatus.processing, OrderStatus.shipped, OrderStatus.delivered}
)


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


async def mark_order_paid(db: AsyncSession, order_id: int) -> None:
    order = await _get_order_with_payment(db, order_id)

    if order.status in _PAST_PAYMENT:
        return

    order.status = OrderStatus.paid
    if order.payment is not None:
        order.payment.status = PaymentStatus.succeeded
    if order.shipment is None:
        db.add(Shipment(order_id=order.id, status=ShipmentStatus.processing))

    await db.commit()


async def mark_order_payment_failed(db: AsyncSession, order_id: int) -> None:
    order = await _get_order_with_payment(db, order_id)

    if order.payment is not None and order.payment.status != PaymentStatus.succeeded:
        order.payment.status = PaymentStatus.requires_payment_method

    await db.commit()


async def list_orders_for_user(db: AsyncSession, telegram_id: int) -> list[OrderListItemOut]:
    stmt = (
        select(Order)
        .where(Order.telegram_id == telegram_id)
        .order_by(Order.placed_at.desc())
    )
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
    )
