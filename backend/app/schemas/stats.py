from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.models.enums import OrderStatus

StatsPeriod = Literal["today", "7d", "30d"]


class LowStockOut(BaseModel):
    variant_id: int
    product_id: int
    sku: str
    name: str
    stock_qty: int


class TopProductOut(BaseModel):
    product_id: int
    name: str
    qty: int
    revenue: Decimal


class SummaryOut(BaseModel):
    period: StatsPeriod
    currency: str
    revenue: Decimal
    orders_count: int
    average_order: Decimal
    status_counts: dict[OrderStatus, int]
    low_stock: list[LowStockOut]
    top_products: list[TopProductOut]
