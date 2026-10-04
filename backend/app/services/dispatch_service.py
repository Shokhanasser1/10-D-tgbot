"""The delivery state machine.

    processing --claim--> assigned --pickup--> shipped --deliver--> delivered
        ^                    |
        +------release-------+          (no release after pickup)

Every transition is a single guarded UPDATE ... WHERE status = <expected> [AND courier_id = <me>],
so concurrent requests cannot both win, and Order.status moves in the same transaction.
Services here return schemas, never ORM instances: the guarded UPDATEs bypass the session's
identity map.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.courier import Courier
from app.models.enums import (
    ACTIVE_SHIPMENT_STATUSES,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ShipmentStatus,
)
from app.models.order import Order
from app.models.payment import Payment
from app.models.shipment import Shipment
from app.schemas.courier import ShipmentActionOut
from app.services import courier_state, earnings_service, notification_events

settings = get_settings()

_INVALID_STATE = "This delivery is not in a state that allows that action"


@dataclass(frozen=True)
class _Transition:
    from_status: ShipmentStatus
    to_status: ShipmentStatus
    order_from: OrderStatus
    order_to: OrderStatus
    stamp: str | None  # Shipment column set to now()
    clears_courier: bool = False
    purges_location: bool = False


_RELEASE = _Transition(
    ShipmentStatus.assigned,
    ShipmentStatus.processing,
    OrderStatus.processing,
    OrderStatus.paid,
    stamp=None,
    clears_courier=True,
    purges_location=True,
)
_PICKUP = _Transition(
    ShipmentStatus.assigned,
    ShipmentStatus.shipped,
    OrderStatus.processing,
    OrderStatus.shipped,
    stamp="picked_up_at",
)
_DELIVER = _Transition(
    ShipmentStatus.shipped,
    ShipmentStatus.delivered,
    OrderStatus.shipped,
    OrderStatus.delivered,
    stamp="delivered_at",
    purges_location=True,
)


async def _move_order(
    db: AsyncSession, order_id: int, from_statuses: Sequence[OrderStatus], to_status: OrderStatus
) -> None:
    moved = await db.scalar(
        update(Order)
        .where(Order.id == order_id, Order.status.in_(from_statuses))
        .values(status=to_status)
        .returning(Order.id)
        .execution_options(synchronize_session=False)
    )
    if moved is None:
        # The shipment was already updated in this transaction; undo it so the two never disagree.
        await db.rollback()
        raise ConflictError(_INVALID_STATE, code="invalid_state")


async def claim(db: AsyncSession, courier: Courier, shipment_id: int) -> ShipmentActionOut:
    await courier_state.lock_courier(db, courier.id)

    active = await courier_state.count_active(db, courier.id)
    if active >= settings.max_active_deliveries_per_courier:
        raise ConflictError(
            "You already have the maximum number of active deliveries",
            code="delivery_limit_reached",
        )

    # Under READ COMMITTED a second racer blocks on this row, re-checks the WHERE against the
    # committed row, and matches nothing. That, not the courier lock, is what makes a claim atomic.
    order_id = await db.scalar(
        update(Shipment)
        .where(
            Shipment.id == shipment_id,
            Shipment.status == ShipmentStatus.processing,
            Shipment.courier_id.is_(None),
            Shipment.ready_at.is_not(None),
        )
        .values(status=ShipmentStatus.assigned, courier_id=courier.id, assigned_at=func.now())
        .returning(Shipment.order_id)
        .execution_options(synchronize_session=False)
    )
    if order_id is None:
        # A shipment still waiting for its seller is invisible to couriers (Spec 10).
        ready_at = await db.execute(select(Shipment.ready_at).where(Shipment.id == shipment_id))
        row = ready_at.first()
        if row is None or row.ready_at is None:
            raise NotFoundError("Shipment not found")
        raise ConflictError("This delivery was already taken", code="shipment_taken")

    await _move_order(db, order_id, (OrderStatus.paid,), OrderStatus.processing)

    if active == 0:
        # An idle courier has no business having a stored position; drop any leftover.
        await courier_state.clear_location(db, courier.id)

    await notification_events.order_claimed(db, order_id, courier.name)
    await db.commit()
    return ShipmentActionOut(
        shipment_id=shipment_id, order_id=order_id, status=ShipmentStatus.assigned
    )


async def _transition(
    db: AsyncSession, courier: Courier, shipment_id: int, transition: _Transition
) -> ShipmentActionOut:
    await courier_state.lock_courier(db, courier.id)

    values: dict[str, object] = {"status": transition.to_status}
    if transition.stamp:
        values[transition.stamp] = func.now()
    if transition.clears_courier:
        values |= {"courier_id": None, "assigned_at": None, "picked_up_at": None}

    order_id = await db.scalar(
        update(Shipment)
        .where(
            Shipment.id == shipment_id,
            Shipment.courier_id == courier.id,
            Shipment.status == transition.from_status,
        )
        .values(**values)
        .returning(Shipment.order_id)
        .execution_options(synchronize_session=False)
    )
    if order_id is None:
        # Someone else's shipment and an unknown one are deliberately indistinguishable (404).
        owned = await db.scalar(
            select(Shipment.id).where(Shipment.id == shipment_id, Shipment.courier_id == courier.id)
        )
        if owned is None:
            raise NotFoundError("Shipment not found")
        raise ConflictError(_INVALID_STATE, code="invalid_state")

    await _move_order(db, order_id, (transition.order_from,), transition.order_to)

    if transition.purges_location:
        await courier_state.purge_location_if_idle(db, courier.id)

    if transition is _PICKUP:
        await notification_events.order_picked_up(db, order_id)
    elif transition is _DELIVER:
        # Cash on delivery: handing the order over is when the money is collected.
        await db.execute(
            update(Payment)
            .where(Payment.order_id == order_id, Payment.method == PaymentMethod.cash)
            .values(status=PaymentStatus.succeeded)
            .execution_options(synchronize_session=False)
        )
        # The seller's share is earned on delivery (Spec 11).
        await earnings_service.record_earning(db, order_id)
        await notification_events.order_delivered(db, order_id)
    elif transition is _RELEASE:
        await notification_events.order_back_in_pool(
            db, order_id, released_by_courier_id=courier.id
        )
    await db.commit()
    return ShipmentActionOut(
        shipment_id=shipment_id, order_id=order_id, status=transition.to_status
    )


async def release(db: AsyncSession, courier: Courier, shipment_id: int) -> ShipmentActionOut:
    return await _transition(db, courier, shipment_id, _RELEASE)


async def pickup(db: AsyncSession, courier: Courier, shipment_id: int) -> ShipmentActionOut:
    return await _transition(db, courier, shipment_id, _PICKUP)


async def deliver(db: AsyncSession, courier: Courier, shipment_id: int) -> ShipmentActionOut:
    return await _transition(db, courier, shipment_id, _DELIVER)


async def force_release(db: AsyncSession, shipment_id: int) -> ShipmentActionOut:
    """Owner override: return any assigned or shipped delivery to the pool.

    The escape hatch for a courier who vanished or was deactivated mid-delivery. Not a returns
    flow: it just makes the order claimable again.
    """
    # Read the courier without locking, then lock it *before* touching the shipment, matching
    # the courier's own lock order. The guarded UPDATE re-checks that nothing changed meanwhile.
    row = (
        await db.execute(
            select(Shipment.courier_id, Shipment.status).where(Shipment.id == shipment_id)
        )
    ).first()
    if row is None:
        raise NotFoundError("Shipment not found")
    courier_id, status = row
    if courier_id is None or status not in ACTIVE_SHIPMENT_STATUSES:
        raise ConflictError(_INVALID_STATE, code="invalid_state")

    await courier_state.lock_courier(db, courier_id, require_active=False)

    order_id = await db.scalar(
        update(Shipment)
        .where(
            Shipment.id == shipment_id,
            Shipment.courier_id == courier_id,
            Shipment.status.in_(ACTIVE_SHIPMENT_STATUSES),
        )
        .values(
            status=ShipmentStatus.processing, courier_id=None, assigned_at=None, picked_up_at=None
        )
        .returning(Shipment.order_id)
        .execution_options(synchronize_session=False)
    )
    if order_id is None:
        await db.rollback()
        raise ConflictError(_INVALID_STATE, code="invalid_state")

    await _move_order(
        db, order_id, (OrderStatus.processing, OrderStatus.shipped), OrderStatus.paid
    )
    await courier_state.purge_location_if_idle(db, courier_id)

    # The courier it was taken from does not need telling that it is back in the pool.
    await notification_events.order_back_in_pool(db, order_id, released_by_courier_id=courier_id)
    await db.commit()
    return ShipmentActionOut(
        shipment_id=shipment_id, order_id=order_id, status=ShipmentStatus.processing
    )
