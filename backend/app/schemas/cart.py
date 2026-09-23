from decimal import Decimal

from pydantic import BaseModel


class CartItemIn(BaseModel):
    variant_id: int
    qty: int


class CartItemQtyUpdate(BaseModel):
    qty: int


class CartItemOut(BaseModel):
    id: int
    variant_id: int
    sku: str
    product_name: str
    thumbnail_url: str | None
    qty: int
    unit_price_snapshot: Decimal
    line_total: Decimal


class CartOut(BaseModel):
    items: list[CartItemOut]
    subtotal: Decimal
