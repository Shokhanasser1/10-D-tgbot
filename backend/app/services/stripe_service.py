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
