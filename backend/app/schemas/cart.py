from decimal import Decimal

from pydantic import BaseModel

from app.schemas.catalog import SellerBrief


class CartItemIn(BaseModel):
    variant_id: int
    qty: int
    # The customer agreed to empty a cart that holds another seller's products (Spec 9).
    replace_cart: bool = False


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
    seller: SellerBrief | None = None  # whose products the cart holds; None when empty
