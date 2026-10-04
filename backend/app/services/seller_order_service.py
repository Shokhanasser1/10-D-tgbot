"""Spec 10 §6: a seller's orders, built only from the columns selected here, so customer data
never reaches a seller. An order is the seller's to see once it was paid: from then on it has a
shipment (an unpaid or never-paid order has none)."""

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.order import Order, OrderItem
from app.models.shipment import Shipment
from app.models.variant import Variant
from app.schemas.seller_orders import (
    SellerOrderItemOut,
    SellerOrderListItem,
    SellerOrderOut,
    SellerOrderPage,
)


def _item_count():
    return (
        select(func.coalesce(func.sum(OrderItem.qty), 0))
        .where(OrderItem.order_id == Order.id)
        .scalar_subquery()
    )


def _orders(seller_id: int) -> Select:
    return (
        select(
            Order.id,
            Order.status,
            Order.placed_at,
            Order.subtotal,
            Order.currency,
            Order.payment_method,
            _item_count().label("item_count"),
            Shipment.status.label("shipment_status"),
            Shipment.ready_at,
        )
        .join(Shipment, Shipment.order_id == Order.id)
        .where(Order.seller_id == seller_id)
    )


def _list_item(row) -> SellerOrderListItem:
    return SellerOrderListItem(
        id=row.id,
        status=row.status,
        placed_at=row.placed_at,
        subtotal=row.subtotal,
        currency=row.currency,
        payment_method=row.payment_method,
        item_count=int(row.item_count),
        shipment_status=row.shipment_status,
        ready_at=row.ready_at,
    )


async def list_orders(
    db: AsyncSession, seller_id: int, *, limit: int = 50, offset: int = 0
) -> SellerOrderPage:
    total = await db.scalar(
        select(func.count())
        .select_from(Order)
        .join(Shipment, Shipment.order_id == Order.id)
        .where(Order.seller_id == seller_id)
    )
    rows = await db.execute(
        _orders(seller_id)
        .order_by(Order.placed_at.desc(), Order.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return SellerOrderPage(items=[_list_item(row) for row in rows], total=total or 0)


async def get_order(db: AsyncSession, seller_id: int, order_id: int) -> SellerOrderOut:
    row = (await db.execute(_orders(seller_id).where(Order.id == order_id))).first()
    if row is None:  # another seller's, or not paid yet
        raise NotFoundError("Order not found")
    items = await db.execute(
        select(
            OrderItem.product_name_snapshot,
            Variant.sku,
            OrderItem.qty,
            OrderItem.unit_price_snapshot,
        )
        .join(Variant, Variant.id == OrderItem.variant_id)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.id)
    )
    return SellerOrderOut(
        **_list_item(row).model_dump(),
        items=[
            SellerOrderItemOut(
                product_name=item.product_name_snapshot,
                sku=item.sku,
                qty=item.qty,
                unit_price=item.unit_price_snapshot,
                line_total=item.unit_price_snapshot * item.qty,
            )
            for item in items
        ],
    )
