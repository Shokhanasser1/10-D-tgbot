from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.i18n import translations_for
from app.models.cart import Cart, CartItem
from app.models.enums import CartStatus, ProductStatus
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.variant import Variant
from app.schemas.cart import CartItemOut, CartOut


async def get_or_create_active_cart(db: AsyncSession, telegram_id: int) -> Cart:
    stmt = select(Cart).where(Cart.telegram_id == telegram_id, Cart.status == CartStatus.active)
    cart = (await db.execute(stmt)).scalar_one_or_none()
    if cart is None:
        cart = Cart(telegram_id=telegram_id, status=CartStatus.active)
        db.add(cart)
        await db.flush()
    return cart


async def restore_order_items(db: AsyncSession, order_id: int) -> None:
    """Put an unpaid order's items back into its customer's active cart (without committing).

    Quantities add onto lines already there for the same variant. Products that are no longer
    for sale are skipped. The price is the current one, as for anything added to the cart.
    """
    telegram_id = await db.scalar(select(Order.telegram_id).where(Order.id == order_id))
    if telegram_id is None:
        return
    lines = (
        await db.execute(
            select(Variant.id, Variant.price, func.sum(OrderItem.qty))
            .join(OrderItem, OrderItem.variant_id == Variant.id)
            .join(Product, Product.id == Variant.product_id)
            .where(OrderItem.order_id == order_id, Product.status == ProductStatus.active)
            .group_by(Variant.id, Variant.price)
            .order_by(Variant.id)
        )
    ).all()
    if not lines:
        return

    cart = await get_or_create_active_cart(db, telegram_id)
    existing = {
        item.variant_id: item
        for item in (
            await db.execute(select(CartItem).where(CartItem.cart_id == cart.id))
        ).scalars()
    }
    for variant_id, price, qty in lines:
        item = existing.get(variant_id)
        if item is None:
            db.add(
                CartItem(
                    cart_id=cart.id, variant_id=variant_id, qty=int(qty), unit_price_snapshot=price
                )
            )
        else:
            item.qty += int(qty)
    await db.flush()


async def _get_active_variant(db: AsyncSession, variant_id: int) -> Variant:
    stmt = (
        select(Variant).where(Variant.id == variant_id).options(selectinload(Variant.product))
    )
    variant = (await db.execute(stmt)).scalar_one_or_none()
    if variant is None or variant.product.status != ProductStatus.active:
        raise NotFoundError("Variant not found")
    return variant


async def add_item(db: AsyncSession, telegram_id: int, variant_id: int, qty: int) -> None:
    if qty <= 0:
        raise ConflictError("qty must be positive")

    variant = await _get_active_variant(db, variant_id)
    cart = await get_or_create_active_cart(db, telegram_id)

    stmt = select(CartItem).where(CartItem.cart_id == cart.id, CartItem.variant_id == variant_id)
    item = (await db.execute(stmt)).scalar_one_or_none()
    new_qty = qty + (item.qty if item is not None else 0)

    if variant.stock_qty < new_qty:
        raise ConflictError("Insufficient stock")

    if item is None:
        db.add(
            CartItem(
                cart_id=cart.id,
                variant_id=variant_id,
                qty=qty,
                unit_price_snapshot=variant.price,
            )
        )
    else:
        item.qty = new_qty

    await db.commit()


async def update_item_qty(db: AsyncSession, telegram_id: int, item_id: int, qty: int) -> None:
    if qty < 0:
        raise ConflictError("qty cannot be negative")

    item = await _get_owned_item(db, telegram_id, item_id)

    if qty == 0:
        await db.delete(item)
        await db.commit()
        return

    variant = await _get_active_variant(db, item.variant_id)
    if variant.stock_qty < qty:
        raise ConflictError("Insufficient stock")

    item.qty = qty
    await db.commit()


async def remove_item(db: AsyncSession, telegram_id: int, item_id: int) -> None:
    item = await _get_owned_item(db, telegram_id, item_id)
    await db.delete(item)
    await db.commit()


async def _get_owned_item(db: AsyncSession, telegram_id: int, item_id: int) -> CartItem:
    stmt = (
        select(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(
            CartItem.id == item_id,
            Cart.telegram_id == telegram_id,
            Cart.status == CartStatus.active,
        )
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Cart item not found")
    return item


async def _thumbnails_for(
    db: AsyncSession, product_ids: list[int], variant_ids: list[int]
) -> tuple[dict[int, str], dict[int, str]]:
    if not product_ids:
        return {}, {}

    stmt = (
        select(ProductImage)
        .where(ProductImage.product_id.in_(product_ids))
        .order_by(ProductImage.position)
    )
    images = (await db.execute(stmt)).scalars().all()

    variant_thumbnails: dict[int, str] = {}
    product_thumbnails: dict[int, str] = {}
    for image in images:
        if image.variant_id is not None and image.variant_id in variant_ids:
            variant_thumbnails.setdefault(image.variant_id, image.url)
        elif image.variant_id is None:
            product_thumbnails.setdefault(image.product_id, image.url)
    return variant_thumbnails, product_thumbnails


async def get_cart(
    db: AsyncSession, telegram_id: int, locale: str, fallback_locale: str
) -> CartOut:
    stmt = (
        select(CartItem)
        .join(Cart, Cart.id == CartItem.cart_id)
        .where(Cart.telegram_id == telegram_id, Cart.status == CartStatus.active)
        .options(selectinload(CartItem.variant).selectinload(Variant.product))
    )
    items = (await db.execute(stmt)).scalars().all()

    product_ids = [item.variant.product_id for item in items]
    variant_ids = [item.variant_id for item in items]
    names = await translations_for(db, "product", product_ids, ["name"], locale, fallback_locale)
    variant_thumbnails, product_thumbnails = await _thumbnails_for(db, product_ids, variant_ids)

    out_items = [
        CartItemOut(
            id=item.id,
            variant_id=item.variant_id,
            sku=item.variant.sku,
            product_name=names.get(
                (item.variant.product_id, "name"), item.variant.product.base_sku
            ),
            thumbnail_url=variant_thumbnails.get(item.variant_id)
            or product_thumbnails.get(item.variant.product_id),
            qty=item.qty,
            unit_price_snapshot=item.unit_price_snapshot,
            line_total=item.unit_price_snapshot * item.qty,
        )
        for item in items
    ]
    subtotal = sum((item.line_total for item in out_items), Decimal("0"))

    return CartOut(items=out_items, subtotal=subtotal)
