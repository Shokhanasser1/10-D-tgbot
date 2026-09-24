"""Create a courier and a paid order waiting in the pool, for trying the delivery flow by hand.

Usage (from backend/), after `python -m scripts.seed_demo_data`:
    python -m scripts.seed_courier_demo --courier 222 --customer 111 [--lat 52.52 --lng 13.405]

Safe to repeat: the courier and customer are reused, and each run adds one more order.
"""

import argparse
import asyncio
import sys
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models import Courier, Order, OrderItem, Payment, Shipment, TelegramUser, Variant
from app.models.enums import OrderStatus, PaymentStatus, ShipmentStatus


async def seed(
    courier_telegram_id: int, customer_telegram_id: int, pin: tuple[float, float] | None
):
    async with async_session_factory() as db:
        variant = (
            await db.execute(select(Variant).order_by(Variant.id).limit(1))
        ).scalar_one_or_none()
        if variant is None:
            sys.exit("No products yet — run `python -m scripts.seed_demo_data` first.")

        for telegram_id in (courier_telegram_id, customer_telegram_id):
            if await db.get(TelegramUser, telegram_id) is None:
                db.add(TelegramUser(telegram_id=telegram_id, locale="en"))
        await db.flush()

        courier = (
            await db.execute(select(Courier).where(Courier.telegram_id == courier_telegram_id))
        ).scalar_one_or_none()
        if courier is None:
            courier = Courier(telegram_id=courier_telegram_id, name="Demo")
            db.add(courier)

        address: dict[str, str | float | None] = {
            "street": "Alexanderplatz 1",
            "city": "Berlin",
            "postal_code": "10178",
            "country": "DE",
            "phone": "+491234567",
            "notes": "Ring twice",
        }
        if pin is not None:
            address["latitude"], address["longitude"] = pin

        order = Order(
            telegram_id=customer_telegram_id,
            status=OrderStatus.paid,
            currency="EUR",
            subtotal=variant.price,
            shipping_cost=Decimal("4.99"),
            total=variant.price + Decimal("4.99"),
            delivery_address=address,
        )
        db.add(order)
        await db.flush()
        db.add_all(
            [
                OrderItem(
                    order_id=order.id,
                    variant_id=variant.id,
                    product_name_snapshot=f"Demo item {variant.sku}",
                    qty=1,
                    unit_price_snapshot=variant.price,
                ),
                Payment(
                    order_id=order.id,
                    stripe_payment_intent_id=f"pi_demo_{uuid.uuid4().hex}",
                    status=PaymentStatus.succeeded,
                    amount=order.total,
                    currency="EUR",
                ),
            ]
        )
        shipment = Shipment(order_id=order.id, status=ShipmentStatus.processing)
        db.add(shipment)
        await db.commit()
        return courier.id, order.id, shipment.id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--courier", type=int, required=True, help="courier's Telegram user ID")
    parser.add_argument("--customer", type=int, required=True, help="customer's Telegram user ID")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lng", type=float)
    args = parser.parse_args()
    if (args.lat is None) != (args.lng is None):
        parser.error("give both --lat and --lng, or neither")

    pin = (args.lat, args.lng) if args.lat is not None else None
    courier_id, order_id, shipment_id = asyncio.run(seed(args.courier, args.customer, pin))
    print(f"courier_id={courier_id} order_id={order_id} shipment_id={shipment_id}")


if __name__ == "__main__":
    main()
