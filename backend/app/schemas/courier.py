from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ShipmentStatus
from app.schemas.geo import Coordinates


class CourierProfileOut(BaseModel):
    id: int
    name: str
    bot_username: str | None
    max_active_deliveries: int


class PoolItemOut(BaseModel):
    """A claimable order. Deliberately just enough to decide: no phone, notes or coordinates."""

    shipment_id: int
    order_id: int
    city: str
    street: str
    item_count: int
    placed_at: datetime


class DeliveryItemOut(BaseModel):
    name: str
    qty: int


class CourierAddressOut(BaseModel):
    street: str
    city: str
    postal_code: str
    country: str
    phone: str
    notes: str | None


class CourierDeliveryOut(BaseModel):
    """A delivery the courier holds. No money fields: payment was taken at checkout."""

    shipment_id: int
    order_id: int
    status: ShipmentStatus
    address: CourierAddressOut
    destination: Coordinates | None
    items: list[DeliveryItemOut]
    assigned_at: datetime | None
    picked_up_at: datetime | None


class CourierDeliveriesOut(BaseModel):
    # When the courier's GPS last reached us: one value per courier, not per delivery.
    location_updated_at: datetime | None
    deliveries: list[CourierDeliveryOut]


class ShipmentActionOut(BaseModel):
    shipment_id: int
    order_id: int
    status: ShipmentStatus
