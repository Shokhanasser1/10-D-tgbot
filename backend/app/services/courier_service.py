from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo import destination_from_address
from app.models.courier import Courier, CourierLocation
from app.models.enums import ACTIVE_SHIPMENT_STATUSES, OrderStatus, PaymentMethod, ShipmentStatus
from app.models.order import Order, OrderItem
from app.models.shipment import Shipment
from app.schemas.courier import (
    CourierAddressOut,
    CourierDeliveriesOut,
    CourierDeliveryOut,
    DeliveryItemOut,
    PoolItemOut,
)

POOL_LIMIT = 100


def _cash(method: PaymentMethod, total: Decimal) -> Decimal | None:
    return total if method == PaymentMethod.cash else None


def _text(address: dict, key: str) -> str:
    # Addresses are stored JSON; tolerate a missing or null field rather than failing the list.
    return str(address.get(key) or "")


async def get_pool(db: AsyncSession) -> list[PoolItemOut]:
    rows = (
        await db.execute(
            select(
                Shipment.id,
                Shipment.order_id,
                Order.placed_at,
                Order.delivery_address,
                Order.payment_method,
                Order.total,
                Order.currency,
            )
            .join(Order, Order.id == Shipment.order_id)
            .where(
                Shipment.status == ShipmentStatus.processing,
                Shipment.courier_id.is_(None),
                Order.status == OrderStatus.paid,
            )
            .order_by(Shipment.created_at, Shipment.id)
            .limit(POOL_LIMIT)
        )
    ).all()
    if not rows:
        return []

    order_ids = [row.order_id for row in rows]
    counts = dict(
        (
            await db.execute(
                select(OrderItem.order_id, func.sum(OrderItem.qty))
                .where(OrderItem.order_id.in_(order_ids))
                .group_by(OrderItem.order_id)
            )
        ).all()
    )

    return [
        PoolItemOut(
            shipment_id=row.id,
            order_id=row.order_id,
            city=_text(row.delivery_address, "city"),
            street=_text(row.delivery_address, "street"),
            item_count=int(counts.get(row.order_id, 0)),
            placed_at=row.placed_at,
            cash_to_collect=_cash(row.payment_method, row.total),
            currency=row.currency,
        )
        for row in rows
    ]


async def get_deliveries(db: AsyncSession, courier: Courier) -> CourierDeliveriesOut:
    # Columns, not entities: dispatch changes shipments with guarded UPDATEs that bypass the
    # session's identity map, so an entity read could hand back a stale status.
    rows = (
        await db.execute(
            select(
                Shipment.id,
                Shipment.status,
                Shipment.assigned_at,
                Shipment.picked_up_at,
                Order.id.label("order_id"),
                Order.delivery_address,
                Order.payment_method,
                Order.total,
                Order.currency,
            )
            .join(Order, Order.id == Shipment.order_id)
            .where(
                Shipment.courier_id == courier.id,
                Shipment.status.in_(ACTIVE_SHIPMENT_STATUSES),
            )
            .order_by(Shipment.assigned_at, Shipment.id)
        )
    ).all()

    items_by_order: dict[int, list[DeliveryItemOut]] = {}
    if rows:
        items = (
            await db.execute(
                select(OrderItem.order_id, OrderItem.product_name_snapshot, OrderItem.qty)
                .where(OrderItem.order_id.in_([row.order_id for row in rows]))
                .order_by(OrderItem.id)
            )
        ).all()
        for item in items:
            items_by_order.setdefault(item.order_id, []).append(
                DeliveryItemOut(name=item.product_name_snapshot, qty=item.qty)
            )

    location_updated_at = await db.scalar(
        select(CourierLocation.updated_at).where(CourierLocation.courier_id == courier.id)
    )

    return CourierDeliveriesOut(
        location_updated_at=location_updated_at,
        deliveries=[
            CourierDeliveryOut(
                shipment_id=row.id,
                order_id=row.order_id,
                status=row.status,
                address=CourierAddressOut(
                    street=_text(row.delivery_address, "street"),
                    city=_text(row.delivery_address, "city"),
                    postal_code=_text(row.delivery_address, "postal_code"),
                    country=_text(row.delivery_address, "country"),
                    phone=_text(row.delivery_address, "phone"),
                    notes=row.delivery_address.get("notes") or None,
                ),
                destination=destination_from_address(row.delivery_address),
                items=items_by_order.get(row.order_id, []),
                assigned_at=row.assigned_at,
                picked_up_at=row.picked_up_at,
                cash_to_collect=_cash(row.payment_method, row.total),
                currency=row.currency,
            )
            for row in rows
        ],
    )
