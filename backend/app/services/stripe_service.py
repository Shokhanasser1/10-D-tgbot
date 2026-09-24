from decimal import Decimal

import stripe

from app.config import get_settings
from app.core.money import to_minor_units

settings = get_settings()
stripe.api_key = settings.stripe_secret_key


async def create_payment_intent(
    amount: Decimal, currency: str, metadata: dict[str, str]
) -> stripe.PaymentIntent:
    return await stripe.PaymentIntent.create_async(
        amount=to_minor_units(amount),
        currency=currency.lower(),
        metadata=metadata,
        automatic_payment_methods={"enabled": True},
    )


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    return stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)


async def create_refund(
    payment_intent_id: str, idempotency_key: str, metadata: dict[str, str]
) -> stripe.Refund:
    """Refund the whole payment. Stripe refuses to refund more than was charged, so even a
    retry under a new idempotency key cannot pay the customer back twice."""
    return await stripe.Refund.create_async(
        payment_intent=payment_intent_id, metadata=metadata, idempotency_key=idempotency_key
    )
