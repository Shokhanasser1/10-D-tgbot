from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Attribute,
    Cart,
    CartItem,
    Category,
    Order,
    OrderItem,
    Payment,
    Product,
    Shipment,
    TelegramUser,
    Translation,
    Variant,
)
from app.models.enums import (
    AttributeValueType,
    CartStatus,
    OrderStatus,
    PaymentStatus,
    ProductStatus,
    ShipmentStatus,
)


async def test_full_entity_chain_round_trip(db_session: AsyncSession) -> None:
    category = Category(slug="lipstick", sort_order=0)
    db_session.add(category)
    await db_session.flush()

    attribute = Attribute(
        key="shade", category_id=category.id, value_type=AttributeValueType.text
    )
    db_session.add(attribute)

    product = Product(
        category_id=category.id,
        base_sku="LIP-001",
        base_price=Decimal("19.99"),
        status=ProductStatus.active,
    )
    db_session.add(product)
    await db_session.flush()

    variant = Variant(
        product_id=product.id,
        sku="LIP-001-RED",
        price=Decimal("19.99"),
        stock_qty=10,
        attribute_values={"shade": "red"},
    )
    db_session.add(variant)
    await db_session.flush()

    translation = Translation(
        entity_type="product",
        entity_id=product.id,
        locale="ru",
        field="name",
        value="Помада",
    )
    db_session.add(translation)

    telegram_user = TelegramUser(telegram_id=123456789, username="testuser", locale="ru")
    db_session.add(telegram_user)
    await db_session.flush()

    cart = Cart(telegram_id=telegram_user.telegram_id, status=CartStatus.active)
    db_session.add(cart)
    await db_session.flush()

    cart_item = CartItem(
        cart_id=cart.id,
        variant_id=variant.id,
        qty=2,
        unit_price_snapshot=variant.price,
    )
    db_session.add(cart_item)

    order = Order(
        telegram_id=telegram_user.telegram_id,
        status=OrderStatus.pending_payment,
        currency="EUR",
        subtotal=Decimal("39.98"),
        shipping_cost=Decimal("4.99"),
        total=Decimal("44.97"),
        delivery_address={"city": "Berlin", "street": "Alexanderplatz 1"},
    )
    db_session.add(order)
    await db_session.flush()

    order_item = OrderItem(
        order_id=order.id,
        variant_id=variant.id,
        product_name_snapshot="Lipstick",
        qty=2,
        unit_price_snapshot=variant.price,
    )
    db_session.add(order_item)

    payment = Payment(
        order_id=order.id,
        stripe_payment_intent_id="pi_test_123",
        status=PaymentStatus.succeeded,
        amount=order.total,
        currency="EUR",
    )
    db_session.add(payment)

    shipment = Shipment(order_id=order.id, status=ShipmentStatus.processing)
    db_session.add(shipment)

    await db_session.commit()

    fetched_order = (
        await db_session.execute(select(Order).where(Order.id == order.id))
    ).scalar_one()
    assert fetched_order.total == Decimal("44.97")

    fetched_variant = (
        await db_session.execute(select(Variant).where(Variant.id == variant.id))
    ).scalar_one()
    assert fetched_variant.attribute_values == {"shade": "red"}

    fetched_translation = (
        await db_session.execute(
            select(Translation).where(
                Translation.entity_type == "product",
                Translation.entity_id == product.id,
                Translation.locale == "ru",
            )
        )
    ).scalar_one()
    assert fetched_translation.value == "Помада"
