"""Telegram Payments (Spec 6 §4.1): invoice links with Click or Payme as the provider.

Invoices are created with Bot API `createInvoiceLink`; the Mini App opens them with
`Telegram.WebApp.openInvoice`. Telegram then asks the bot to confirm (`pre_checkout_query`, answered
from the webhook response) and reports the result (`successful_payment`).
"""

from decimal import Decimal
from typing import Any

import httpx

from app.config import get_settings
from app.core.exceptions import PaymentUnavailableError
from app.core.money import to_minor_units

TELEGRAM_API = "https://api.telegram.org"
PAYLOAD_PREFIX = "order:"
_TITLE_LIMIT = 32
_DESCRIPTION_LIMIT = 255
_LABEL_LIMIT = 64


def order_payload(order_id: int) -> str:
    return f"{PAYLOAD_PREFIX}{order_id}"


def order_id_from_payload(payload: str | None) -> int | None:
    if not payload or not payload.startswith(PAYLOAD_PREFIX):
        return None
    number = payload.removeprefix(PAYLOAD_PREFIX)
    return int(number) if number.isdigit() else None


def build_invoice(
    *,
    order_id: int,
    currency: str,
    lines: list[tuple[str, int, Decimal]],
    shipping_cost: Decimal,
    shipping_label: str,
) -> dict[str, Any]:
    """The createInvoiceLink parameters. `lines` are (name, qty, unit price)."""
    prices = [
        {"label": f"{name} × {qty}"[:_LABEL_LIMIT], "amount": to_minor_units(price * qty)}
        for name, qty, price in lines
    ]
    if shipping_cost > 0:
        prices.append({"label": shipping_label, "amount": to_minor_units(shipping_cost)})
    description = ", ".join(f"{name} × {qty}" for name, qty, _ in lines)
    return {
        "title": f"Order #{order_id}"[:_TITLE_LIMIT],
        "description": description[:_DESCRIPTION_LIMIT] or f"Order #{order_id}",
        "payload": order_payload(order_id),
        "provider_token": get_settings().telegram_payment_provider_token,
        "currency": currency.upper(),
        "prices": prices,
    }


async def create_invoice_link(params: dict[str, Any]) -> str:
    token = get_settings().telegram_bot_token
    try:
        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"{TELEGRAM_API}/bot{token}/createInvoiceLink", json=params, timeout=15
            )
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise PaymentUnavailableError(f"could not reach Telegram: {type(exc).__name__}") from None
    if not isinstance(body, dict) or not body.get("ok"):
        description = body.get("description") if isinstance(body, dict) else None
        raise PaymentUnavailableError(str(description or f"HTTP {response.status_code}")[:300])
    return str(body["result"])
