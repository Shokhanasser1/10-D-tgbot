"""Spec 10 §6: what a seller sees of an order. Deliberately no customer: no name, phone,
address or notes; the platform delivers."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import OrderStatus, PaymentMethod, ShipmentStatus


class SellerOrderListItem(BaseModel):
    id: int
    status: OrderStatus
    placed_at: datetime
    # The goods; shipping belongs to the platform.
    subtotal: Decimal
    currency: str
    payment_method: PaymentMethod
    item_count: int
    shipment_status: ShipmentStatus
    # Null while the order waits for the seller to have it ready.
    ready_at: datetime | None


class SellerOrderPage(BaseModel):
    items: list[SellerOrderListItem]
    total: int


class SellerOrderItemOut(BaseModel):
    product_name: str
    sku: str
    qty: int
    unit_price: Decimal
    line_total: Decimal


class SellerOrderOut(SellerOrderListItem):
    items: list[SellerOrderItemOut]
