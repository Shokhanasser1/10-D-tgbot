from decimal import Decimal

from pydantic import BaseModel


class CategoryOut(BaseModel):
    id: int
    slug: str
    parent_id: int | None
    sort_order: int
    name: str


class VariantOut(BaseModel):
    id: int
    sku: str
    price: Decimal
    stock_qty: int
    attribute_values: dict[str, str]
    image_urls: list[str]


class ProductListItemOut(BaseModel):
    id: int
    category_id: int
    base_sku: str
    base_price: Decimal
    name: str
    thumbnail_url: str | None


class ProductDetailOut(BaseModel):
    id: int
    category_id: int
    base_sku: str
    base_price: Decimal
    name: str
    description: str | None
    image_urls: list[str]
    variants: list[VariantOut]
