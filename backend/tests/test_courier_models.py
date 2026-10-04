from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Courier, CourierLocation, Order, Shipment, TelegramUser
from app.models.enums import ACTIVE_SHIPMENT_STATUSES, OrderStatus, ShipmentStatus
from tests.factories import default_seller_id


async def _order(db: AsyncSession, telegram_id: int) -> Order:
    db.add(TelegramUser(telegram_id=telegram_id, locale="en"))
    await db.flush()
    order = Order(
        seller_id=await default_seller_id(db),
        telegram_id=telegram_id,
        status=OrderStatus.paid,
        currency="EUR",
        subtotal=Decimal("10.00"),
        shipping_cost=Decimal("4.99"),
        total=Decimal("14.99"),
        delivery_address={"city": "Berlin"},
    )
    db.add(order)
    await db.flush()
    return order


async def test_courier_defaults_to_active(db_session: AsyncSession) -> None:
    courier = Courier(telegram_id=1001, name="Ali")
    db_session.add(courier)
    await db_session.flush()
    await db_session.refresh(courier)

    assert courier.is_active is True
    assert courier.phone is None


async def test_courier_telegram_id_is_unique(db_session: AsyncSession) -> None:
    db_session.add(Courier(telegram_id=1002, name="Ali"))
    await db_session.flush()

    db_session.add(Courier(telegram_id=1002, name="Duplicate"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_courier_with_a_shipment_cannot_be_deleted(db_session: AsyncSession) -> None:
    courier = Courier(telegram_id=1003, name="Ali")
    db_session.add(courier)
    order = await _order(db_session, 2001)
    await db_session.flush()
    db_session.add(
        Shipment(order_id=order.id, status=ShipmentStatus.assigned, courier_id=courier.id)
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(delete(Courier).where(Courier.id == courier.id))


async def test_deleting_a_courier_removes_their_location(db_session: AsyncSession) -> None:
    courier = Courier(telegram_id=1004, name="Ali")
    db_session.add(courier)
    await db_session.flush()
    db_session.add(CourierLocation(courier_id=courier.id, latitude=52.5, longitude=13.4))
    await db_session.flush()

    await db_session.execute(delete(Courier).where(Courier.id == courier.id))

    remaining = await db_session.scalar(select(func.count()).select_from(CourierLocation))
    assert remaining == 0


@pytest.mark.parametrize(("latitude", "longitude"), [(90.5, 0.0), (-91.0, 0.0), (0.0, 180.5)])
async def test_location_outside_valid_range_is_rejected(
    db_session: AsyncSession, latitude: float, longitude: float
) -> None:
    courier = Courier(telegram_id=1005, name="Ali")
    db_session.add(courier)
    await db_session.flush()

    db_session.add(CourierLocation(courier_id=courier.id, latitude=latitude, longitude=longitude))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_every_shipment_status_round_trips(db_session: AsyncSession) -> None:
    order = await _order(db_session, 2002)
    shipment = Shipment(order_id=order.id)
    db_session.add(shipment)
    await db_session.flush()

    for status in ShipmentStatus:
        shipment.status = status
        await db_session.flush()
        await db_session.refresh(shipment)
        assert shipment.status is status


def test_active_shipment_statuses_are_the_courier_holding_states() -> None:
    assert set(ACTIVE_SHIPMENT_STATUSES) == {ShipmentStatus.assigned, ShipmentStatus.shipped}
