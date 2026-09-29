"""The bot webhook's payment updates (Spec 6 §4.1 steps 4-5).

`pre_checkout_query` must be answered within 10 seconds; the answer goes back as the webhook's
response body, so no outgoing call can fail. `successful_payment` confirms the order through the
same guarded transition Stripe uses.
"""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.money import to_minor_units
from app.models.enums import OrderStatus, PaymentMethod
from app.models.order import Order
from app.schemas.telegram_update import TelegramPreCheckoutQuery, TelegramSuccessfulPayment
from app.services import order_service
from app.services.telegram_payments import order_id_from_payload

logger = logging.getLogger(__name__)

# While the customer is typing card details, the sweeper must not expire the order under them.
PAYING_GRACE = timedelta(minutes=5)

_REFUSALS = {
    "expired": {
        "en": "Payment time ran out. Please place the order again.",
        "ru": "Время на оплату истекло. Оформите заказ заново.",
        "uz": "To'lov vaqti tugadi. Buyurtmani qaytadan bering.",
    },
    "invalid": {
        "en": "This order can no longer be paid.",
        "ru": "Этот заказ больше нельзя оплатить.",
        "uz": "Bu buyurtmani endi to'lab bo'lmaydi.",
    },
}


def _refusal(reason: str, language_code: str | None) -> str:
    texts = _REFUSALS[reason]
    return texts.get((language_code or "en").split("-", 1)[0], texts["en"])


async def answer_pre_checkout(db: AsyncSession, query: TelegramPreCheckoutQuery) -> dict[str, Any]:
    """The answerPreCheckoutQuery call: ok only for an unpaid, unexpired order of that amount."""
    reason = await _check(db, query)
    answer: dict[str, Any] = {
        "method": "answerPreCheckoutQuery",
        "pre_checkout_query_id": query.id,
        "ok": reason is None,
    }
    if reason is not None:
        answer["error_message"] = _refusal(reason, query.sender.language_code)
    return answer


async def _check(db: AsyncSession, query: TelegramPreCheckoutQuery) -> str | None:
    order_id = order_id_from_payload(query.invoice_payload)
    if order_id is None:
        return "invalid"
    order = (
        await db.execute(
            select(
                Order.status,
                Order.total,
                Order.currency,
                Order.payment_method,
                Order.telegram_id,
                (Order.reserved_until > func.now()).label("still_held"),
            ).where(Order.id == order_id)
        )
    ).first()
    if (
        order is None
        or order.payment_method != PaymentMethod.telegram
        or order.telegram_id != query.sender.id
        or order.currency.upper() != query.currency.upper()
        or to_minor_units(order.total) != query.total_amount
    ):
        return "invalid"
    if order.status == OrderStatus.cancelled or (
        order.status == OrderStatus.pending_payment and not order.still_held
    ):
        return "expired"
    if order.status != OrderStatus.pending_payment:
        return "invalid"  # already paid, or on its way

    # Keep the stock held for a few more minutes while the provider charges the card.
    extended = await db.scalar(
        update(Order)
        .where(Order.id == order_id, Order.status == OrderStatus.pending_payment)
        .values(reserved_until=func.greatest(Order.reserved_until, func.now() + PAYING_GRACE))
        .returning(Order.id)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    return None if extended is not None else "expired"


async def record_successful_payment(db: AsyncSession, payment: TelegramSuccessfulPayment) -> None:
    order_id = order_id_from_payload(payment.invoice_payload)
    if order_id is None:
        logger.error("successful_payment with an unknown payload %r", payment.invoice_payload)
        return
    try:
        await order_service.mark_order_paid(
            db,
            order_id,
            charge_ids={
                "telegram_payment_charge_id": payment.telegram_payment_charge_id,
                "provider_payment_charge_id": payment.provider_payment_charge_id,
            },
        )
    except NotFoundError:
        # Acknowledge anyway: Telegram would otherwise redeliver a payment we cannot place.
        logger.error("successful_payment for missing order %s", order_id)
