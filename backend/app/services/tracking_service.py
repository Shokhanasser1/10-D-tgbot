from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.geo import destination_from_address
from app.models.courier import Courier, CourierLocation
from app.models.enums import ACTIVE_SHIPMENT_STATUSES, ShipmentStatus
from app.models.order import Order
from app.models.shipment import Shipment
from app.schemas.tracking import TrackingCourierOut, TrackingLocationOut, TrackingOut

settings = get_settings()


async def get_order_tracking(db: AsyncSession, telegram_id: int, order_id: int) -> TrackingOut:
    # Columns, not entities: dispatch updates shipments with statements that bypass the
    # session's identity map, so an entity read could return a stale status.
    order = (
        await db.execute(
            select(Order.delivery_address).where(
                Order.id == order_id, Order.telegram_id == telegram_id
            )
        )
    ).first()
    if order is None:
        # Someone else's order and a non-existent one look identical on purpose.
        raise NotFoundError("Order not found")
    destination = destination_from_address(order.delivery_address)

    shipment = (
        await db.execute(
            select(
                Shipment.status,
                Shipment.courier_id,
                Shipment.picked_up_at,
                Shipment.delivered_at,
            ).where(Shipment.order_id == order_id)
        )
    ).first()
    if shipment is None:
        return TrackingOut(
            status=None,
            courier=None,
            courier_location=None,
            destination=destination,
            picked_up_at=None,
            delivered_at=None,
        )

    courier = None
    if shipment.status in ACTIVE_SHIPMENT_STATUSES and shipment.courier_id is not None:
        name = await db.scalar(select(Courier.name).where(Courier.id == shipment.courier_id))
        courier = TrackingCourierOut(name=name) if name else None

    # The courier's position is shared with the customer only while their order is out for
    # delivery, and only if a fix has actually arrived.
    location = None
    if shipment.status == ShipmentStatus.shipped and shipment.courier_id is not None:
        fix = (
            await db.execute(
                select(
                    CourierLocation.latitude,
                    CourierLocation.longitude,
                    CourierLocation.updated_at,
                ).where(CourierLocation.courier_id == shipment.courier_id)
            )
        ).first()
        if fix is not None:
            age = datetime.now(UTC) - fix.updated_at
            location = TrackingLocationOut(
                latitude=fix.latitude,
                longitude=fix.longitude,
                updated_at=fix.updated_at,
                is_stale=age > timedelta(seconds=settings.location_stale_seconds),
            )

    return TrackingOut(
        status=shipment.status,
        courier=courier,
        courier_location=location,
        destination=destination,
        picked_up_at=shipment.picked_up_at,
        delivered_at=shipment.delivered_at,
    )
