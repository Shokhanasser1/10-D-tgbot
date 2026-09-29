from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator


class DeliveryAddressIn(BaseModel):
    street: str
    city: str
    postal_code: str
    country: str
    phone: str
    notes: str | None = None
    # Optional pin the customer drops on the map. `strict` keeps `true` and "52.5" from being
    # coerced into a coordinate. The range bounds also reject NaN and Infinity, which Python's
    # json accepts but PostgreSQL's JSONB cannot store.
    latitude: float | None = Field(default=None, ge=-90, le=90, strict=True)
    longitude: float | None = Field(default=None, ge=-180, le=180, strict=True)

    @model_validator(mode="after")
    def _pin_is_both_or_neither(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be given together")
        return self


class CheckoutRequest(BaseModel):
    delivery_address: DeliveryAddressIn


class CheckoutResponse(BaseModel):
    order_id: int
    client_secret: str
    total: Decimal
    currency: str
    # Stock is held until then; an unpaid order is cancelled afterwards.
    reserved_until: datetime
