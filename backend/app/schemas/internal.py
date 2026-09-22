from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import AttributeValueType, ProductStatus


class CategoryCreate(BaseModel):
    slug: str
    parent_id: int | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    slug: str | None = None
    parent_id: int | None = None
    sort_order: int | None = None


class CategoryAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    parent_id: int | None
    sort_order: int


class AttributeCreate(BaseModel):
    key: str
    category_id: int
    value_type: AttributeValueType


class AttributeUpdate(BaseModel):
    key: str | None = None
    value_type: AttributeValueType | None = None


class AttributeAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    category_id: int
    value_type: AttributeValueType


class ProductCreate(BaseModel):
    category_id: int
    base_sku: str
    base_price: Decimal
    status: ProductStatus = ProductStatus.draft


class ProductUpdate(BaseModel):
    category_id: int | None = None
    base_sku: str | None = None
    base_price: Decimal | None = None
    status: ProductStatus | None = None


class ProductAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    base_sku: str
    base_price: Decimal
    status: ProductStatus


class VariantCreate(BaseModel):
    product_id: int
    sku: str
    price: Decimal
    stock_qty: int = 0
    attribute_values: dict[str, str] = {}


class VariantUpdate(BaseModel):
    sku: str | None = None
    price: Decimal | None = None
    stock_qty: int | None = None
    attribute_values: dict[str, str] | None = None


class VariantAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    sku: str
    price: Decimal
    stock_qty: int
    attribute_values: dict[str, str]


class ProductImageCreate(BaseModel):
    variant_id: int | None = None
    url: str
    position: int = 0


class ProductImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    variant_id: int | None
    url: str
    position: int


class TranslationUpsert(BaseModel):
    entity_type: str
    entity_id: int
    locale: str
    field: str
    value: str


class TranslationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    locale: str
    field: str
    value: str
