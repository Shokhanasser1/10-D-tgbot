from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ShipmentStatus
from app.schemas.geo import Coordinates


class TrackingCourierOut(BaseModel):
    """What a customer may know about their courier: a name, never contact details or IDs."""

    name: str


class TrackingLocationOut(BaseModel):
    latitude: float
    longitude: float
    updated_at: datetime
    # Computed on the server so every client agrees on what "stale" means.
    is_stale: bool


class TrackingOut(BaseModel):
    status: ShipmentStatus | None  # None until the order has a shipment (i.e. until it is paid)
    courier: TrackingCourierOut | None
    courier_location: TrackingLocationOut | None
    destination: Coordinates | None
    picked_up_at: datetime | None
    delivered_at: datetime | None
