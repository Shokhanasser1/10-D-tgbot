from decimal import Decimal

from pydantic import BaseModel


class DeliveryAddressIn(BaseModel):
    street: str
    city: str
    postal_code: str
    country: str
    phone: str
    notes: str | None = None


class CheckoutRequest(BaseModel):
    delivery_address: DeliveryAddressIn


class CheckoutResponse(BaseModel):
    order_id: int
    client_secret: str
    total: Decimal
    currency: str
