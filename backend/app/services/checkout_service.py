from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError, ConflictError
from app.core.i18n import translations_for
from app.core.money import from_minor_units
from app.core.pricing import calculate_shipping_cost
from app.models.cart import Cart, CartItem
from app.models.enums import CartStatus, OrderStatus, PaymentStatus
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.variant import Variant
from app.schemas.checkout import CheckoutResponse, DeliveryAddressIn
from app.services import stripe_service


async def create_order_from_cart(
    db: AsyncSession,
    telegram_id: int,
    address: DeliveryAddressIn,
    currency: str,
    locale: str,
    fallback_locale: str,
) -> CheckoutResponse:
    cart_stmt = select(Cart).where(
        Cart.telegram_id == telegram_id, Cart.status == CartStatus.active
    )
    cart = (await db.execute(cart_stmt)).scalar_one_or_none()
    if cart is None:
        raise BadRequestError("Cart is empty")

    items_stmt = (
        select(CartItem)
        .where(CartItem.cart_id == cart.id)
        .options(selectinload(CartItem.variant).selectinload(Variant.product))
    )
    cart_items = (await db.execute(items_stmt)).scalars().all()

    if not cart_items:
        raise BadRequestError("Cart is empty")

    for item in cart_items:
        if item.variant.stock_qty < item.qty:
            raise ConflictError(f"Insufficient stock for variant {item.variant.sku}")

    product_ids = [item.variant.product_id for item in cart_items]
    names = await translations_for(db, "product", product_ids, ["name"], locale, fallback_locale)

    subtotal = sum((item.variant.price * item.qty for item in cart_items), Decimal("0"))
    shipping_cost = calculate_shipping_cost(subtotal)
    total = subtotal + shipping_cost

    order = Order(
        telegram_id=telegram_id,
        status=OrderStatus.pending_payment,
        currency=currency,
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        total=total,
        delivery_address=address.model_dump(),
    )
    db.add(order)
    await db.flush()

    for item in cart_items:
        db.add(
            OrderItem(
                order_id=order.id,
                variant_id=item.variant_id,
                product_name_snapshot=names.get(
                    (item.variant.product_id, "name"), item.variant.product.base_sku
                ),
                qty=item.qty,
                unit_price_snapshot=item.variant.price,
            )
        )

    intent = await stripe_service.create_payment_intent(
        total, currency, metadata={"order_id": str(order.id)}
    )
    db.add(
        Payment(
            order_id=order.id,
            stripe_payment_intent_id=intent.id,
            status=PaymentStatus.requires_payment_method,
            amount=from_minor_units(intent.amount),
            currency=currency,
        )
    )

    cart.status = CartStatus.checked_out

    await db.commit()

    return CheckoutResponse(
        order_id=order.id, client_secret=intent.client_secret, total=total, currency=currency
    )
