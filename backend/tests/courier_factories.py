import itertools
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.courier import Courier
from app.models.enums import OrderStatus, PaymentStatus, ProductStatus, ShipmentStatus
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.shipment import Shipment
from app.models.telegram_user import TelegramUser
from app.models.variant import Variant
from tests.factories import default_seller_id, make_init_data

INTERNAL_HEADERS = {"X-Internal-Token": "test-internal-token"}

_sequence = itertools.count(1)


async def add_courier(
    db: AsyncSession,
    telegram_id: int,
    *,
    name: str = "Ali",
    phone: str | None = "+998900000000",
    is_active: bool = True,
) -> Courier:
    courier = Courier(telegram_id=telegram_id, name=name, phone=phone, is_active=is_active)
    db.add(courier)
    await db.commit()
    await db.refresh(courier)
    return courier


async def add_customer(db: AsyncSession, telegram_id: int) -> None:
    if await db.get(TelegramUser, telegram_id) is None:
        db.add(TelegramUser(telegram_id=telegram_id, locale="en"))
        await db.commit()


async def add_paid_order(
    db: AsyncSession,
    *,
    customer_id: int = 900_001,
    qty: int = 1,
    pin: tuple[float, float] | None = None,
    city: str = "Berlin",
    street: str = "Alexanderplatz 1",
    notes: str | None = "Ring twice",
    ready: bool = True,
    seller_id: int | None = None,
) -> tuple[Order, Shipment]:
    """A paid order sitting in the courier pool, with the rows checkout and the webhook create.

    `ready=False` leaves it waiting for its seller (Spec 10) instead of in the pool.
    """
    n = next(_sequence)
    seller_id = seller_id if seller_id is not None else await default_seller_id(db)
    await add_customer(db, customer_id)

    category = Category(slug=f"courier-cat-{n}", sort_order=0)
    db.add(category)
    await db.flush()
    product = Product(
        seller_id=seller_id,
        category_id=category.id,
        base_sku=f"COURIER-P-{n}",
        base_price=Decimal("10.00"),
        status=ProductStatus.active,
    )
    db.add(product)
    await db.flush()
    variant = Variant(
        product_id=product.id, sku=f"COURIER-V-{n}", price=Decimal("10.00"), stock_qty=99
    )
    db.add(variant)

    address: dict[str, str | float | None] = {
        "street": street,
        "city": city,
        "postal_code": "10178",
        "country": "DE",
        "phone": "+491234567",
        "notes": notes,
    }
    if pin is not None:
        address["latitude"], address["longitude"] = pin

    order = Order(
        telegram_id=customer_id,
        seller_id=seller_id,
        status=OrderStatus.paid,
        currency="EUR",
        subtotal=Decimal("10.00") * qty,
        shipping_cost=Decimal("4.99"),
        total=Decimal("10.00") * qty + Decimal("4.99"),
        delivery_address=address,
    )
    db.add(order)
    await db.flush()
    db.add_all(
        [
            OrderItem(
                order_id=order.id,
                variant_id=variant.id,
                product_name_snapshot="Velvet Lipstick",
                qty=qty,
                unit_price_snapshot=Decimal("10.00"),
            ),
            Payment(
                order_id=order.id,
                stripe_payment_intent_id=f"pi_courier_{n}",
                status=PaymentStatus.succeeded,
                amount=order.total,
                currency="EUR",
            ),
        ]
    )
    shipment = Shipment(
        order_id=order.id,
        status=ShipmentStatus.processing,
        ready_at=datetime.now(UTC) if ready else None,
    )
    db.add(shipment)
    await db.commit()
    await db.refresh(order)
    await db.refresh(shipment)
    return order, shipment


def tma_headers(telegram_id: int) -> dict[str, str]:
    """Authorization header for a Telegram user, signed the way the real client signs it."""
    return {"Authorization": f"tma {make_init_data(telegram_id=telegram_id)}"}
