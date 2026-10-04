from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import (
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    RefundStatus,
    ShipmentStatus,
)
from app.schemas.checkout import DeliveryAddressIn


class OrderAdminListItem(BaseModel):
    id: int
    status: OrderStatus
    currency: str
    total: Decimal
    placed_at: datetime
    telegram_id: int
    customer_name: str | None
    shipment_status: ShipmentStatus | None
    stock_shortfall: bool
    refund_status: RefundStatus | None
    payment_method: PaymentMethod = PaymentMethod.stripe


class OrderAdminPage(BaseModel):
    items: list[OrderAdminListItem]
    total: int


class OrderAdminItemOut(BaseModel):
    id: int
    variant_id: int
    sku: str
    product_id: int
    product_name_snapshot: str
    qty: int
    unit_price_snapshot: Decimal


class OrderAdminCustomerOut(BaseModel):
    telegram_id: int
    first_name: str | None
    last_name: str | None
    username: str | None


class OrderAdminPaymentOut(BaseModel):
    method: PaymentMethod = PaymentMethod.stripe
    status: PaymentStatus
    amount: Decimal
    refund_status: RefundStatus | None
    # Telegram Payments: to find the payment in the Click/Payme cabinet for a manual refund.
    telegram_payment_charge_id: str | None = None
    provider_payment_charge_id: str | None = None


class OrderAdminShipmentOut(BaseModel):
    id: int
    status: ShipmentStatus
    courier_id: int | None
    courier_name: str | None
    assigned_at: datetime | None
    picked_up_at: datetime | None
    delivered_at: datetime | None


class OrderAdminDetailOut(BaseModel):
    id: int
    status: OrderStatus
    currency: str
    subtotal: Decimal
    shipping_cost: Decimal
    total: Decimal
    delivery_address: DeliveryAddressIn
    placed_at: datetime
    customer: OrderAdminCustomerOut
    items: list[OrderAdminItemOut]
    payment: OrderAdminPaymentOut | None
    shipment: OrderAdminShipmentOut | None
    stock_shortfall: bool
    reserved_until: datetime | None = None
    cancelled_at: datetime | None
    cancelled_by: int | None
    cancel_reason: str | None
    # Server-side answer to "may this order be cancelled now?", so the UI never re-derives it.
    can_cancel: bool


class OrderReadyOut(BaseModel):
    order_id: int
    ready_at: datetime


class OrderCancelIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
