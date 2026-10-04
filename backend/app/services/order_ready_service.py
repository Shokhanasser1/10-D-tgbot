"""Spec 10 §4: the seller has an order ready for pickup; from then on couriers see it."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import ShipmentStatus
from app.models.order import Order
from app.models.shipment import Shipment
from app.schemas.order_admin import OrderReadyOut
from app.services import notification_events


async def mark_ready(db: AsyncSession, order_id: int, scope: int | None) -> OrderReadyOut:
    """`scope` is the caller's seller (None for platform staff): another seller's order is 404.

    One guarded UPDATE, so two presses (or a seller and a dispatcher at once) notify the
    couriers once; a repeat answers with the time it became ready.
    """
    owner = await db.scalar(select(Order.seller_id).where(Order.id == order_id))
    if owner is None or (scope is not None and owner != scope):
        raise NotFoundError("Order not found")

    ready_at = await db.scalar(
        update(Shipment)
        .where(
            Shipment.order_id == order_id,
            Shipment.status == ShipmentStatus.processing,
            Shipment.ready_at.is_(None),
        )
        .values(ready_at=func.now())
        .returning(Shipment.ready_at)
        .execution_options(synchronize_session=False)
    )
    if ready_at is None:
        row = (
            await db.execute(
                select(Shipment.status, Shipment.ready_at).where(Shipment.order_id == order_id)
            )
        ).first()
        # Unpaid (no shipment yet) or cancelled: nothing to prepare.
        if row is None or row.status == ShipmentStatus.cancelled or row.ready_at is None:
            raise ConflictError("This order is not waiting for its seller", code="invalid_state")
        return OrderReadyOut(order_id=order_id, ready_at=row.ready_at)

    await notification_events.order_ready(db, order_id)
    await db.commit()
    return OrderReadyOut(order_id=order_id, ready_at=ready_at)
