from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.models.enums import PaymentMethod


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
    # Omitted: the first method the shop has switched on.
    payment_method: PaymentMethod | None = None


class PaymentMethodsOut(BaseModel):
    methods: list[PaymentMethod]
    currency: str


class CheckoutResponse(BaseModel):
    order_id: int
    payment_method: PaymentMethod
    # Stripe: confirm the PaymentIntent with this. Telegram: open this invoice. Cash: neither.
    client_secret: str | None = None
    invoice_url: str | None = None
    total: Decimal
    currency: str
    # Stock is held until then; an unpaid order is cancelled afterwards.
    reserved_until: datetime
