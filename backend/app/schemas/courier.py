from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import ShipmentStatus
from app.schemas.geo import Coordinates


class CourierProfileOut(BaseModel):
    id: int
    name: str
    bot_username: str | None
    max_active_deliveries: int


class PickupOut(BaseModel):
    """Where the courier collects the order: the seller's shop (Spec 10)."""

    name: str
    address: str | None
    phone: str | None


class PoolItemOut(BaseModel):
    """A claimable order. Deliberately just enough to decide: no phone, notes or coordinates."""

    shipment_id: int
    order_id: int
    city: str
    street: str
    item_count: int
    placed_at: datetime
    # Cash on delivery: what the courier collects. Null for orders paid online.
    cash_to_collect: Decimal | None = None
    currency: str = "EUR"
    pickup: PickupOut


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
    """A delivery the courier holds. Money only for cash on delivery: what to collect."""

    shipment_id: int
    order_id: int
    status: ShipmentStatus
    address: CourierAddressOut
    destination: Coordinates | None
    items: list[DeliveryItemOut]
    assigned_at: datetime | None
    picked_up_at: datetime | None
    cash_to_collect: Decimal | None = None
    currency: str = "EUR"
    pickup: PickupOut


class CourierDeliveriesOut(BaseModel):
    # When the courier's GPS last reached us: one value per courier, not per delivery.
    location_updated_at: datetime | None
    deliveries: list[CourierDeliveryOut]


class ShipmentActionOut(BaseModel):
    shipment_id: int
    order_id: int
    status: ShipmentStatus
