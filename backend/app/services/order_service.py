from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.enums import OrderStatus, PaymentStatus, ShipmentStatus
from app.models.order import Order
from app.models.shipment import Shipment


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

    if order.status == OrderStatus.paid:
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
