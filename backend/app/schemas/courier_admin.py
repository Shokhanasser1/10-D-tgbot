from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ShipmentStatus


class CourierCreate(BaseModel):
    telegram_id: int = Field(gt=0)
    # The customer sees this on their order, so it should be a first name only.
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)


class CourierUpdate(BaseModel):
    # telegram_id is the courier's identity and cannot be changed; extra="forbid" turns an
    # attempt into a 422 instead of silently ignoring it.
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None

    @model_validator(mode="after")
    def _required_fields_cannot_be_nulled(self) -> "CourierUpdate":
        for field in ("name", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CourierAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    name: str
    phone: str | None
    is_active: bool


class ShipmentAdminOut(BaseModel):
    id: int
    order_id: int
    status: ShipmentStatus
    courier_id: int | None
    courier_name: str | None
    assigned_at: datetime | None
    picked_up_at: datetime | None


class CourierAdminListItem(CourierAdminOut):
    active_deliveries: int


class CourierLocationAdminOut(BaseModel):
    courier_id: int
    name: str
    latitude: float
    longitude: float
    updated_at: datetime
    is_stale: bool
    active_deliveries: int
