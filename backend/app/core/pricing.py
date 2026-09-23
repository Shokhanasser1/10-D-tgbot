from decimal import Decimal

from app.config import get_settings

settings = get_settings()


def calculate_shipping_cost(subtotal: Decimal) -> Decimal:
    threshold = Decimal(settings.free_shipping_threshold)
    if subtotal >= threshold:
        return Decimal("0.00")
    return Decimal(settings.shipping_flat_rate)
