from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.exceptions import BadRequestError, ConflictError
from app.core.i18n import translations_for
from app.core.money import from_minor_units
from app.core.pricing import calculate_shipping_cost
from app.models.cart import Cart, CartItem
from app.models.enums import CartStatus, OrderStatus, PaymentMethod, PaymentStatus
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.seller import Seller
from app.models.variant import Variant
from app.schemas.checkout import CheckoutResponse, DeliveryAddressIn
from app.services import (
    order_service,
    payment_methods,
    reservation_service,
    stock_service,
    stripe_service,
    telegram_payments,
)

_SHIPPING_LABEL = {"ru": "Доставка", "uz": "Yetkazib berish"}


async def create_order_from_cart(
    db: AsyncSession,
    telegram_id: int,
    address: DeliveryAddressIn,
    currency: str,
    locale: str,
    fallback_locale: str,
    requested_method: PaymentMethod | None = None,
) -> CheckoutResponse:
    method = payment_methods.choose(requested_method)
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
    # One seller per cart (Spec 9), so one per order (Spec 10); checked again here because the
    # order's seller decides who prepares it.
    sellers = {item.variant.product.seller_id for item in cart_items}
    if len(sellers) != 1:
        raise ConflictError("The cart holds several sellers' products", code="cart_other_seller")

    product_ids = [item.variant.product_id for item in cart_items]
    names = await translations_for(db, "product", product_ids, ["name"], locale, fallback_locale)

    subtotal = sum((item.variant.price * item.qty for item in cart_items), Decimal("0"))
    shipping_cost = calculate_shipping_cost(subtotal)
    total = subtotal + shipping_cost
    reserved_until = datetime.now(UTC) + timedelta(minutes=get_settings().reservation_ttl_minutes)

    seller_id = sellers.pop()
    order = Order(
        telegram_id=telegram_id,
        seller_id=seller_id,
        # The seller's rate today; a later change never alters this order (Spec 11).
        commission_percent=await db.scalar(
            select(Seller.commission_percent).where(Seller.id == seller_id)
        ),
        status=OrderStatus.pending_payment,
        currency=currency,
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        total=total,
        delivery_address=address.model_dump(),
        reserved_until=reserved_until,
        payment_method=method,
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

    # Step 1: hold the stock and close the cart. Commit before calling a payment provider so no
    # variant row stays locked during a network call.
    await db.flush()
    order_id = order.id
    lines = [
        (
            names.get((item.variant.product_id, "name"), item.variant.product.base_sku),
            item.qty,
            item.variant.price,
        )
        for item in cart_items
    ]
    await stock_service.reserve(db, order_id)  # rolls back and raises 409 on a short line
    cart.status = CartStatus.checked_out

    if method == PaymentMethod.cash:
        # Nothing to pay now: the order goes to the couriers together with the reservation.
        db.add(_payment(order_id, method, total, currency))
        await order_service.confirm_cash_order(db, order_id)
        await db.commit()
        return _response(order_id, method, total, currency, reserved_until)
    await db.commit()

    # Step 2: ask the provider for a way to pay. If it fails, undo the hold so the customer
    # keeps their cart.
    try:
        if method == PaymentMethod.telegram:
            invoice_url = await telegram_payments.create_invoice_link(
                telegram_payments.build_invoice(
                    order_id=order_id,
                    currency=currency,
                    lines=lines,
                    shipping_cost=shipping_cost,
                    shipping_label=_SHIPPING_LABEL.get(locale, "Delivery"),
                )
            )
        else:
            intent = await stripe_service.create_payment_intent(
                total, currency, metadata={"order_id": str(order_id)}
            )
    except Exception:
        await _undo_reservation(db, order_id)
        raise

    # Step 3: record the payment. If the process dies before this, the order has no payment
    # row and the sweeper expires it like any other.
    if method == PaymentMethod.telegram:
        db.add(_payment(order_id, method, total, currency))
        await db.commit()
        return _response(order_id, method, total, currency, reserved_until, invoice_url=invoice_url)

    db.add(
        _payment(
            order_id,
            method,
            from_minor_units(intent.amount),
            currency,
            stripe_payment_intent_id=intent.id,
        )
    )
    await db.commit()
    return _response(
        order_id, method, total, currency, reserved_until, client_secret=intent.client_secret
    )


def _payment(
    order_id: int, method: PaymentMethod, amount: Decimal, currency: str, **extra: str
) -> Payment:
    return Payment(
        order_id=order_id,
        method=method,
        status=PaymentStatus.requires_payment_method,
        amount=amount,
        currency=currency,
        **extra,
    )


def _response(
    order_id: int,
    method: PaymentMethod,
    total: Decimal,
    currency: str,
    reserved_until: datetime,
    **links: str,
) -> CheckoutResponse:
    return CheckoutResponse(
        order_id=order_id,
        payment_method=method,
        total=total,
        currency=currency,
        reserved_until=reserved_until,
        **links,
    )


async def _undo_reservation(db: AsyncSession, order_id: int) -> None:
    await db.rollback()
    cancelled = await db.scalar(
        update(Order)
        .where(Order.id == order_id, Order.status == OrderStatus.pending_payment)
        .values(
            status=OrderStatus.cancelled,
            cancelled_at=func.now(),
            cancel_reason=reservation_service.SETUP_FAILED_REASON,
        )
        .returning(Order.id)
        .execution_options(synchronize_session=False)
    )
    if cancelled is not None:
        await reservation_service.release_unpaid_order(db, order_id)
    await db.commit()
