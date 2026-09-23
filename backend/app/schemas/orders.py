from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import OrderStatus, PaymentStatus, ShipmentStatus
from app.schemas.checkout import DeliveryAddressIn


class OrderItemOut(BaseModel):
    id: int
    variant_id: int
    product_name_snapshot: str
    qty: int
    unit_price_snapshot: Decimal


class OrderListItemOut(BaseModel):
    id: int
    status: OrderStatus
    currency: str
    total: Decimal
    placed_at: datetime


class OrderDetailOut(BaseModel):
    id: int
    status: OrderStatus
    currency: str
    subtotal: Decimal
    shipping_cost: Decimal
    total: Decimal
    delivery_address: DeliveryAddressIn
    placed_at: datetime
    items: list[OrderItemOut]
    payment_status: PaymentStatus | None
    shipment_status: ShipmentStatus | None
