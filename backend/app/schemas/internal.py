from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class ProductImageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: int | None = None  # null moves the image back to the product itself
    position: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _position_cannot_be_nulled(self) -> "ProductImageUpdate":
        if "position" in self.model_fields_set and self.position is None:
            raise ValueError("position cannot be null")
        return self


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


# locale -> field -> value, e.g. {"ru": {"name": "..."}}
Translations = dict[str, dict[str, str]]


class CategoryAdminListItem(CategoryAdminOut):
    name: str
    translations: Translations


class AttributeAdminListItem(AttributeAdminOut):
    translations: Translations


class ProductAdminListItem(BaseModel):
    id: int
    category_id: int
    base_sku: str
    base_price: Decimal
    status: ProductStatus
    name: str
    thumbnail_url: str | None
    variant_count: int
    min_price: Decimal | None
    total_stock: int


class ProductAdminPage(BaseModel):
    items: list[ProductAdminListItem]
    total: int


class ProductAdminDetailOut(ProductAdminOut):
    name: str
    translations: Translations
    variants: list[VariantAdminOut]
    images: list[ProductImageOut]
