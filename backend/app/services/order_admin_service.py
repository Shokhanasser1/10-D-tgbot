"""Orders as the owner and dispatchers see them: listing, detail, cancellation with a refund.

Cancellation follows the dispatch rules (see dispatch_service): guarded UPDATEs in the lock
order courier -> shipment -> order -> variants, and schemas built from fresh reads, never from
possibly stale ORM entities.
"""

import logging
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import stripe
from sqlalchemy import Select, and_, false, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.courier import Courier
from app.models.enums import (
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    RefundStatus,
    ShipmentStatus,
)
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.shipment import Shipment
from app.models.telegram_user import TelegramUser
from app.models.variant import Variant
from app.schemas.order_admin import (
    OrderAdminCustomerOut,
    OrderAdminDetailOut,
    OrderAdminItemOut,
    OrderAdminListItem,
    OrderAdminPage,
    OrderAdminPaymentOut,
    OrderAdminShipmentOut,
)
from app.services import courier_state, notification_events, stock_service, stripe_service

settings = get_settings()
logger = logging.getLogger(__name__)

_INVALID_STATE = "This order can no longer be cancelled"
_CANCEL_ATTEMPTS = 3
CANCELLABLE_ORDER = (OrderStatus.paid, OrderStatus.processing)
CANCELLABLE_SHIPMENT = (ShipmentStatus.processing, ShipmentStatus.assigned)


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=ZoneInfo(settings.shop_timezone))


# --- listing ---------------------------------------------------------------------------------


def _filtered(
    stmt: Select,
    statuses: Sequence[OrderStatus] | None,
    q: str | None,
    date_from: date | None,
    date_to: date | None,
    shortfall: bool | None,
) -> Select:
    if statuses:
        stmt = stmt.where(Order.status.in_(statuses))
    if q and q.strip().isdigit():
        number = int(q.strip())
        stmt = stmt.where(or_(Order.id == number, Order.telegram_id == number))
    elif q and q.strip():
        stmt = stmt.where(false())  # only numbers are searchable: an order number or telegram ID
    if date_from is not None:
        stmt = stmt.where(Order.placed_at >= _day_start(date_from))
    if date_to is not None:  # inclusive: up to the start of the following day
        stmt = stmt.where(Order.placed_at < _day_start(date_to + timedelta(days=1)))
    if shortfall is not None:
        stmt = stmt.where(Order.stock_shortfall.is_(shortfall))
    return stmt


async def list_orders(
    db: AsyncSession,
    *,
    statuses: Sequence[OrderStatus] | None = None,
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    shortfall: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> OrderAdminPage:
    total = await db.scalar(
        _filtered(
            select(func.count()).select_from(Order), statuses, q, date_from, date_to, shortfall
        )
    )
    rows = (
        await db.execute(
            _filtered(
                select(
                    Order.id,
                    Order.status,
                    Order.currency,
                    Order.total,
                    Order.placed_at,
                    Order.telegram_id,
                    Order.stock_shortfall,
                    TelegramUser.first_name,
                    TelegramUser.last_name,
                    Shipment.status.label("shipment_status"),
                    Payment.refund_status,
                    Order.payment_method,
                )
                .join(TelegramUser, TelegramUser.telegram_id == Order.telegram_id)
                .outerjoin(Shipment, Shipment.order_id == Order.id)
                .outerjoin(Payment, Payment.order_id == Order.id),
                statuses,
                q,
                date_from,
                date_to,
                shortfall,
            )
            .order_by(Order.placed_at.desc(), Order.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return OrderAdminPage(
        total=total or 0,
        items=[
            OrderAdminListItem(
                id=r.id,
                status=r.status,
                currency=r.currency,
                total=r.total,
                placed_at=r.placed_at,
                telegram_id=r.telegram_id,
                customer_name=" ".join(n for n in (r.first_name, r.last_name) if n) or None,
                shipment_status=r.shipment_status,
                stock_shortfall=r.stock_shortfall,
                refund_status=r.refund_status,
                payment_method=r.payment_method,
            )
            for r in rows
        ],
    )


# --- detail ----------------------------------------------------------------------------------


async def get_order(db: AsyncSession, order_id: int) -> OrderAdminDetailOut:
    order = (
        await db.execute(
            select(Order).where(Order.id == order_id).execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if order is None:
        raise NotFoundError("Order not found")

    customer = await db.get(TelegramUser, order.telegram_id)
    items = (
        await db.execute(
            select(OrderItem, Variant.sku, Variant.product_id)
            .join(Variant, Variant.id == OrderItem.variant_id)
            .where(OrderItem.order_id == order_id)
            .order_by(OrderItem.id)
        )
    ).all()
    payment = (
        await db.execute(
            select(
                Payment.method,
                Payment.status,
                Payment.amount,
                Payment.refund_status,
                Payment.telegram_payment_charge_id,
                Payment.provider_payment_charge_id,
            ).where(Payment.order_id == order_id)
        )
    ).first()
    shipment = (
        await db.execute(
            select(
                Shipment.id,
                Shipment.status,
                Shipment.courier_id,
                Courier.name,
                Shipment.assigned_at,
                Shipment.picked_up_at,
                Shipment.delivered_at,
            )
            .outerjoin(Courier, Courier.id == Shipment.courier_id)
            .where(Shipment.order_id == order_id)
        )
    ).first()

    return OrderAdminDetailOut(
        id=order.id,
        status=order.status,
        currency=order.currency,
        subtotal=order.subtotal,
        shipping_cost=order.shipping_cost,
        total=order.total,
        delivery_address=order.delivery_address,
        placed_at=order.placed_at,
        customer=OrderAdminCustomerOut(
            telegram_id=order.telegram_id,
            first_name=customer.first_name if customer else None,
            last_name=customer.last_name if customer else None,
            username=customer.username if customer else None,
        ),
        items=[
            OrderAdminItemOut(
                id=item.id,
                variant_id=item.variant_id,
                sku=sku,
                product_id=product_id,
                product_name_snapshot=item.product_name_snapshot,
                qty=item.qty,
                unit_price_snapshot=item.unit_price_snapshot,
            )
            for item, sku, product_id in items
        ],
        payment=(
            OrderAdminPaymentOut(
                method=payment.method,
                status=payment.status,
                amount=payment.amount,
                refund_status=payment.refund_status,
                telegram_payment_charge_id=payment.telegram_payment_charge_id,
                provider_payment_charge_id=payment.provider_payment_charge_id,
            )
            if payment
            else None
        ),
        shipment=(
            OrderAdminShipmentOut(
                id=shipment.id,
                status=shipment.status,
                courier_id=shipment.courier_id,
                courier_name=shipment.name,
                assigned_at=shipment.assigned_at,
                picked_up_at=shipment.picked_up_at,
                delivered_at=shipment.delivered_at,
            )
            if shipment
            else None
        ),
        stock_shortfall=order.stock_shortfall,
        reserved_until=order.reserved_until,
        cancelled_at=order.cancelled_at,
        cancelled_by=order.cancelled_by,
        cancel_reason=order.cancel_reason,
        can_cancel=(
            order.status in CANCELLABLE_ORDER
            and shipment is not None
            and shipment.status in CANCELLABLE_SHIPMENT
        ),
    )


# --- cancellation and refund -----------------------------------------------------------------


async def _cancel_rows(
    db: AsyncSession, order_id: int, reason: str, cancelled_by: int | None
) -> int | None | bool:
    """One attempt at cancelling the shipment and order rows, locks included.

    Returns the courier_id the shipment had (None if it was in the pool), or False when a
    concurrent courier action changed the shipment between the read and the guarded UPDATE.
    """
    row = (
        await db.execute(
            select(Order.status, Shipment.id, Shipment.status, Shipment.courier_id)
            .outerjoin(Shipment, Shipment.order_id == Order.id)
            .where(Order.id == order_id)
        )
    ).first()
    if row is None:
        raise NotFoundError("Order not found")
    order_status, shipment_id, shipment_status, courier_id = row
    if (
        order_status not in CANCELLABLE_ORDER
        or shipment_id is None
        or shipment_status not in CANCELLABLE_SHIPMENT
    ):
        raise ConflictError(_INVALID_STATE, code="invalid_state")

    # Courier first, as everywhere: their own claim/pickup/release take this lock too.
    if courier_id is not None:
        await courier_state.lock_courier(db, courier_id, require_active=False)

    # Re-check under the row lock: the courier may have claimed, released or picked it up.
    same_courier = (
        Shipment.courier_id.is_(None) if courier_id is None else Shipment.courier_id == courier_id
    )
    cancelled_shipment = await db.scalar(
        update(Shipment)
        .where(
            and_(
                Shipment.id == shipment_id,
                Shipment.status.in_(CANCELLABLE_SHIPMENT),
                same_courier,
            )
        )
        .values(status=ShipmentStatus.cancelled, courier_id=None)
        .returning(Shipment.id)
        .execution_options(synchronize_session=False)
    )
    if cancelled_shipment is None:
        await db.rollback()
        return False

    cancelled_order = await db.scalar(
        update(Order)
        .where(Order.id == order_id, Order.status.in_(CANCELLABLE_ORDER))
        .values(
            status=OrderStatus.cancelled,
            cancelled_at=func.now(),
            cancelled_by=cancelled_by,
            cancel_reason=reason,
        )
        .returning(Order.id)
        .execution_options(synchronize_session=False)
    )
    if cancelled_order is None:
        await db.rollback()
        return False
    return courier_id


async def cancel_order(
    db: AsyncSession, order_id: int, reason: str, cancelled_by: int | None
) -> OrderAdminDetailOut:
    """Cancel a paid order before pickup, put its stock back and refund it in full."""
    # A courier claiming or releasing the order at the same moment changes who holds it but
    # not whether it can be cancelled, so look again rather than failing the owner's request.
    for _ in range(_CANCEL_ATTEMPTS):
        courier_id = await _cancel_rows(db, order_id, reason, cancelled_by)
        if courier_id is not False:
            break
    else:
        raise ConflictError(_INVALID_STATE, code="invalid_state")

    await stock_service.put_back(db, order_id)
    if courier_id is not None:
        await courier_state.purge_location_if_idle(db, courier_id)

    stripe_refund = await _start_refund(db, order_id, reason)
    # Commit before talking to Stripe: money must never go back for an order the database
    # still shows as on its way.
    await db.commit()

    if stripe_refund is not None:
        await refund_payment(db, order_id, stripe_refund, f"refund-order-{order_id}")
    return await get_order(db, order_id)


async def _start_refund(db: AsyncSession, order_id: int, reason: str) -> str | None:
    """Settle the money of a cancelled order (no commit), by how it was paid.

    Returns the Stripe PaymentIntent to refund after committing, if any. Telegram Payments has
    no refund API, so an owner refunds by hand; cash was never collected before pickup.
    """
    method = await db.scalar(select(Payment.method).where(Payment.order_id == order_id))
    if method == PaymentMethod.cash:
        await db.execute(
            update(Payment)
            .where(Payment.order_id == order_id, Payment.status != PaymentStatus.succeeded)
            .values(status=PaymentStatus.canceled)
            .execution_options(synchronize_session=False)
        )
        await notification_events.order_cancelled(db, order_id, reason, refunded=False)
        return None

    manual = method == PaymentMethod.telegram
    refunded = await db.scalar(
        update(Payment)
        .where(Payment.order_id == order_id, Payment.status == PaymentStatus.succeeded)
        .values(refund_status=RefundStatus.manual_required if manual else RefundStatus.pending)
        .returning(Payment.stripe_payment_intent_id)
        .execution_options(synchronize_session=False)
    )
    await notification_events.order_cancelled(db, order_id, reason, refunded=True)
    if manual:
        await notification_events.refund_manual_required(db, order_id)
        return None
    return refunded


async def confirm_manual_refund(db: AsyncSession, order_id: int) -> OrderAdminDetailOut:
    """An owner refunded a Telegram payment in the provider's cabinet and says so."""
    confirmed = await db.scalar(
        update(Payment)
        .where(Payment.order_id == order_id, Payment.refund_status == RefundStatus.manual_required)
        .values(refund_status=RefundStatus.succeeded)
        .returning(Payment.id)
        .execution_options(synchronize_session=False)
    )
    if confirmed is None:
        if await db.scalar(select(Order.id).where(Order.id == order_id)) is None:
            raise NotFoundError("Order not found")
        raise ConflictError("There is no manual refund to confirm", code="invalid_state")
    await notification_events.refund_succeeded(db, order_id)
    await db.commit()
    return await get_order(db, order_id)


async def retry_refund(db: AsyncSession, order_id: int) -> OrderAdminDetailOut:
    payment_intent = await db.scalar(
        update(Payment)
        .where(Payment.order_id == order_id, Payment.refund_status == RefundStatus.failed)
        .values(refund_status=RefundStatus.pending)
        .returning(Payment.stripe_payment_intent_id)
        .execution_options(synchronize_session=False)
    )
    if payment_intent is None:
        if await db.scalar(select(Order.id).where(Order.id == order_id)) is None:
            raise NotFoundError("Order not found")
        raise ConflictError("There is no failed refund to retry", code="invalid_state")
    await db.commit()

    # A new key: Stripe replays a stored error for a reused key for 24 h, which would make the
    # retry pointless. Paying back twice is still impossible, since Stripe caps refunds at the
    # charged amount.
    key = f"refund-order-{order_id}-retry-{uuid4().hex}"
    await refund_payment(db, order_id, payment_intent, key)
    return await get_order(db, order_id)


def _refund_status(stripe_status: str | None) -> RefundStatus:
    if stripe_status == "succeeded":
        return RefundStatus.succeeded
    if stripe_status in ("failed", "canceled"):
        return RefundStatus.failed
    return RefundStatus.pending


async def refund_payment(db: AsyncSession, order_id: int, payment_intent: str, key: str) -> None:
    """Ask Stripe for a full refund and record the outcome (refund_status must be pending)."""
    try:
        refund = await stripe_service.create_refund(
            payment_intent, idempotency_key=key, metadata={"order_id": str(order_id)}
        )
    except stripe.StripeError:
        logger.exception("refund for order %s failed", order_id)
        values: dict[str, object] = {"refund_status": RefundStatus.failed}
        ref = key  # Stripe refused before creating a refund: this attempt names the failure
    else:
        values = {"refund_status": _refund_status(refund.status), "stripe_refund_id": refund.id}
        ref = refund.id
    await db.execute(
        update(Payment)
        .where(Payment.order_id == order_id)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    await _notify_refund(db, order_id, values["refund_status"], ref)
    await db.commit()


async def _notify_refund(db: AsyncSession, order_id: int, status: object, ref: str | None) -> None:
    if status == RefundStatus.succeeded:
        await notification_events.refund_succeeded(db, order_id)
    elif status == RefundStatus.failed:
        await notification_events.refund_failed(db, order_id, ref or "unknown")


async def apply_refund_event(
    db: AsyncSession, payment_intent: str | None, refund_id: str | None, stripe_status: str | None
) -> None:
    """Record what Stripe says about a refund (from refund.* webhooks)."""
    if not payment_intent:
        return
    values: dict[str, object] = {"refund_status": _refund_status(stripe_status)}
    if refund_id:
        values["stripe_refund_id"] = refund_id
    order_id = await db.scalar(
        update(Payment)
        .where(
            Payment.stripe_payment_intent_id == payment_intent,
            Payment.refund_status.is_not(None),  # only refunds this shop started
            # A final "succeeded" is never downgraded by an older, reordered event.
            Payment.refund_status != RefundStatus.succeeded,
        )
        .values(**values)
        .returning(Payment.order_id)
        .execution_options(synchronize_session=False)
    )
    if order_id is not None:
        await _notify_refund(db, order_id, values["refund_status"], refund_id)
    await db.commit()
