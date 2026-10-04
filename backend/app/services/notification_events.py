"""Who hears about what (Spec 5 §3): one function per event, called before the caller commits.

Each function reads what it needs with column selects, finds the recipients, renders the text
in each recipient's language and enqueues. Events that can be reported twice for the same fact
(Stripe redelivers webhooks, refunds are reported by the API answer and by a webhook) use a
dedupe key naming that fact; courier actions happen once per request and may legitimately repeat
(claimed, released, claimed again), so their keys carry a unique suffix.
"""

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import roles_with
from app.models.admin import Admin
from app.models.courier import Courier
from app.models.enums import PaymentMethod, Permission
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.seller import Seller
from app.models.telegram_user import TelegramUser
from app.services import notification_service
from app.services.notification_templates import items, money, render


async def _locales(db: AsyncSession, telegram_ids: list[int]) -> dict[int, str]:
    if not telegram_ids:
        return {}
    rows = await db.execute(
        select(TelegramUser.telegram_id, TelegramUser.locale).where(
            TelegramUser.telegram_id.in_(telegram_ids)
        )
    )
    return dict(rows.all())


async def _customer(db: AsyncSession, order_id: int) -> tuple[int, str | None] | None:
    row = (
        await db.execute(
            select(Order.telegram_id, TelegramUser.locale)
            .outerjoin(TelegramUser, TelegramUser.telegram_id == Order.telegram_id)
            .where(Order.id == order_id)
        )
    ).first()
    return (row.telegram_id, row.locale) if row else None


async def _to_customer(
    db: AsyncSession,
    order_id: int,
    kind: str,
    dedupe_key: str,
    *,
    button: tuple[str, str] | None = None,
    template: str | None = None,
    with_total: bool = False,
    **values: object,
) -> None:
    """Enqueue `template` (default: `kind`); `with_total` adds the order total as `{total}`."""
    customer = await _customer(db, order_id)
    if customer is None:
        return
    chat_id, locale = customer
    if with_total:
        total, currency = (
            await db.execute(select(Order.total, Order.currency).where(Order.id == order_id))
        ).one()
        values["total"] = money(total, currency, locale)
    markup = (
        notification_service.web_app_button(render(button[0], locale), button[1])
        if button
        else None
    )
    await notification_service.enqueue(
        db,
        chat_id=chat_id,
        kind=kind,
        dedupe_key=dedupe_key,
        text=render(template or kind, locale, order_id=order_id, **values),
        reply_markup=markup,
    )


def _order_button(order_id: int) -> tuple[str, str]:
    return ("button_order", f"orders/{order_id}")


# --- payment ---------------------------------------------------------------------------------


async def _pool_message(
    db: AsyncSession, order_id: int, kind: str, key: str, exclude_courier_id: int | None = None
) -> None:
    """Tell every active courier (but one) that an order is waiting: city, street, item count."""
    address = await db.scalar(select(Order.delivery_address).where(Order.id == order_id)) or {}
    count = int(
        await db.scalar(select(func.sum(OrderItem.qty)).where(OrderItem.order_id == order_id)) or 0
    )
    place = ", ".join(str(address.get(k)) for k in ("city", "street") if address.get(k))
    order = (
        await db.execute(
            select(Order.total, Order.currency, Order.payment_method).where(Order.id == order_id)
        )
    ).one()
    # A courier collecting cash needs to know how much (and to bring change).
    cash = order.payment_method == PaymentMethod.cash
    pickup = await _pickup(db, order_id)
    stmt = select(Courier.id, Courier.telegram_id).where(Courier.is_active)
    if exclude_courier_id is not None:
        stmt = stmt.where(Courier.id != exclude_courier_id)
    couriers = (await db.execute(stmt)).all()
    locales = await _locales(db, [c.telegram_id for c in couriers])
    for courier in couriers:
        locale = locales.get(courier.telegram_id)
        await notification_service.enqueue(
            db,
            chat_id=courier.telegram_id,
            kind=kind,
            dedupe_key=f"{key}:{courier.telegram_id}",
            text=render(kind, locale, place=place, items=items(count, locale))
            + (
                render("pool_cash", locale, total=money(order.total, order.currency, locale))
                if cash
                else ""
            )
            + render("pool_pickup", locale, pickup=pickup),
            reply_markup=notification_service.web_app_button(
                render("button_courier", locale), "courier"
            ),
        )


async def order_paid(db: AsyncSession, order_id: int) -> None:
    """Paid online, or confirmed for cash on delivery: the order is now in the courier pool."""
    method = await db.scalar(select(Order.payment_method).where(Order.id == order_id))
    cash = method == PaymentMethod.cash
    await _to_customer(
        db,
        order_id,
        "order_paid",
        f"order_paid:{order_id}",
        button=_order_button(order_id),
        template="order_confirmed_cash" if cash else None,
        with_total=cash,
    )
    # Couriers hear about it once the seller has it ready (order_ready, Spec 10).
    await _to_seller(db, order_id)

    order = (
        await db.execute(
            select(Order.total, Order.currency, Order.stock_shortfall).where(Order.id == order_id)
        )
    ).one()
    admins = list(
        await db.scalars(
            select(Admin.telegram_id).where(
                Admin.is_active, Admin.role.in_(roles_with(Permission.orders_cancel_unpaid))
            )
        )
    )
    locales = await _locales(db, admins)
    for telegram_id in admins:
        locale = locales.get(telegram_id)
        text = render(
            "admin_new_order",
            locale,
            order_id=order_id,
            total=money(order.total, order.currency, locale),
        )
        if order.stock_shortfall:
            text += render("admin_shortfall", locale)
        await notification_service.enqueue(
            db,
            chat_id=telegram_id,
            kind="admin_new_order",
            dedupe_key=f"admin_new_order:{order_id}:{telegram_id}",
            text=text,
            reply_markup=notification_service.web_app_button(
                render("button_admin", locale), f"admin/orders/{order_id}"
            ),
        )


async def _pickup(db: AsyncSession, order_id: int) -> str:
    """Where the courier collects the order: the seller's name and pickup address."""
    seller = (
        await db.execute(
            select(Seller.name, Seller.pickup_address)
            .join(Order, Order.seller_id == Seller.id)
            .where(Order.id == order_id)
        )
    ).one()
    return ", ".join(part for part in (seller.name, seller.pickup_address) if part)


async def _to_seller(db: AsyncSession, order_id: int) -> None:
    """A paid order is the seller's to prepare: tell each of their active accounts."""
    seller_id = await db.scalar(select(Order.seller_id).where(Order.id == order_id))
    accounts = list(
        await db.scalars(
            select(Admin.telegram_id).where(Admin.is_active, Admin.seller_id == seller_id)
        )
    )
    count = int(
        await db.scalar(select(func.sum(OrderItem.qty)).where(OrderItem.order_id == order_id)) or 0
    )
    locales = await _locales(db, accounts)
    for telegram_id in accounts:
        locale = locales.get(telegram_id)
        await notification_service.enqueue(
            db,
            chat_id=telegram_id,
            kind="seller_new_order",
            dedupe_key=f"seller_new_order:{order_id}:{telegram_id}",
            text=render("seller_new_order", locale, order_id=order_id, items=items(count, locale)),
            reply_markup=notification_service.web_app_button(
                render("button_seller_order", locale), f"admin/orders/{order_id}"
            ),
        )


async def order_ready(db: AsyncSession, order_id: int) -> None:
    """The seller has the order ready: now it is the couriers' to take."""
    await _pool_message(db, order_id, "pool_new", f"pool_new:{order_id}")


# --- courier actions -------------------------------------------------------------------------


async def order_claimed(db: AsyncSession, order_id: int, courier_name: str) -> None:
    first_name = courier_name.split()[0] if courier_name.strip() else courier_name
    await _to_customer(
        db,
        order_id,
        "order_claimed",
        f"order_claimed:{order_id}:{uuid4().hex}",
        button=_order_button(order_id),
        courier=first_name,
    )


async def order_picked_up(db: AsyncSession, order_id: int) -> None:
    await _to_customer(
        db,
        order_id,
        "order_picked_up",
        f"order_picked_up:{order_id}:{uuid4().hex}",
        button=_order_button(order_id),
    )


async def order_delivered(db: AsyncSession, order_id: int) -> None:
    await _to_customer(db, order_id, "order_delivered", f"order_delivered:{order_id}")


async def order_back_in_pool(
    db: AsyncSession, order_id: int, released_by_courier_id: int | None = None
) -> None:
    await _pool_message(
        db,
        order_id,
        "pool_again",
        f"pool_again:{order_id}:{uuid4().hex}",
        exclude_courier_id=released_by_courier_id,
    )


# --- cancellations and refunds ---------------------------------------------------------------


async def order_expired(db: AsyncSession, order_id: int) -> None:
    await _to_customer(
        db, order_id, "order_expired", f"order_expired:{order_id}", button=("button_cart", "cart")
    )


async def order_cancelled(
    db: AsyncSession, order_id: int, reason: str, *, refunded: bool = True
) -> None:
    """`refunded` is False when no money was taken (cash before delivery)."""
    await _to_customer(
        db,
        order_id,
        "order_cancelled",
        f"order_cancelled:{order_id}",
        button=_order_button(order_id),
        template=None if refunded else "order_cancelled_unpaid",
        reason=reason,
    )


async def refund_succeeded(db: AsyncSession, order_id: int) -> None:
    # Refunds are always in full, so there is at most one successful refund per order.
    await _to_customer(db, order_id, "refund_succeeded", f"refund_succeeded:{order_id}")


async def refund_failed(db: AsyncSession, order_id: int, ref: str) -> None:
    """`ref` names this failure: the Stripe refund ID, or the attempt's idempotency key."""
    owners = list(
        await db.scalars(
            select(Admin.telegram_id).where(
                Admin.is_active, Admin.role.in_(roles_with(Permission.refunds_manage))
            )
        )
    )
    locales = await _locales(db, owners)
    for telegram_id in owners:
        locale = locales.get(telegram_id)
        await notification_service.enqueue(
            db,
            chat_id=telegram_id,
            kind="refund_failed",
            dedupe_key=f"refund_failed:{order_id}:{ref}:{telegram_id}",
            text=render("refund_failed", locale, order_id=order_id),
            reply_markup=notification_service.web_app_button(
                render("button_admin", locale), f"admin/orders/{order_id}"
            ),
        )


async def refund_manual_required(db: AsyncSession, order_id: int) -> None:
    """A Telegram (Click/Payme) payment must be refunded by hand: tell the owners how."""
    payment = (
        await db.execute(
            select(Payment.amount, Payment.currency, Payment.provider_payment_charge_id).where(
                Payment.order_id == order_id
            )
        )
    ).first()
    if payment is None:
        return
    owners = list(
        await db.scalars(
            select(Admin.telegram_id).where(
                Admin.is_active, Admin.role.in_(roles_with(Permission.refunds_manage))
            )
        )
    )
    locales = await _locales(db, owners)
    for telegram_id in owners:
        locale = locales.get(telegram_id)
        await notification_service.enqueue(
            db,
            chat_id=telegram_id,
            kind="refund_manual",
            dedupe_key=f"refund_manual:{order_id}:{telegram_id}",
            text=render(
                "refund_manual",
                locale,
                order_id=order_id,
                total=money(payment.amount, payment.currency, locale),
                charge=payment.provider_payment_charge_id or "—",
            ),
            reply_markup=notification_service.web_app_button(
                render("button_admin", locale), f"admin/orders/{order_id}"
            ),
        )
