"""Which payment methods this shop offers (Spec 6 §3): each is on when it is configured."""

from app.config import Settings, get_settings
from app.core.exceptions import BadRequestError
from app.models.enums import PaymentMethod


def enabled_methods(settings: Settings | None = None) -> list[PaymentMethod]:
    settings = settings or get_settings()
    methods = []
    if settings.telegram_payment_provider_token:
        methods.append(PaymentMethod.telegram)
    if settings.cash_on_delivery_enabled:
        methods.append(PaymentMethod.cash)
    if settings.stripe_secret_key and settings.stripe_publishable_key:
        methods.append(PaymentMethod.stripe)
    return methods


def choose(requested: PaymentMethod | None) -> PaymentMethod:
    """The method to use: the one asked for if it is on, else the first one that is on."""
    methods = enabled_methods()
    if not methods:
        raise BadRequestError("No payment method is configured")
    if requested is None:
        return methods[0]
    if requested not in methods:
        raise BadRequestError("This payment method is not available")
    return requested
