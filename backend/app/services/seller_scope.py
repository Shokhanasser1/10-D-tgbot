"""Spec 9 §4: what a seller's account may reach in the catalog.

`scope` is the caller's seller id (`AdminPrincipal.seller_id`), None for platform staff and the
internal token. This module is the only place that turns it into filters and refusals, so the
catalog services below stay unaware of who is calling. Another seller's rows answer 404, not
403, so a seller cannot probe which ids exist.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.seller import Seller
from app.models.variant import Variant
from app.schemas.internal import ProductUpdate


async def product_in_scope(db: AsyncSession, scope: int | None, product_id: int) -> None:
    if scope is None:
        return
    owner = await db.scalar(select(Product.seller_id).where(Product.id == product_id))
    if owner != scope:
        raise NotFoundError("Product not found")


async def variant_in_scope(db: AsyncSession, scope: int | None, variant_id: int) -> None:
    if scope is None:
        return
    owner = await db.scalar(
        select(Product.seller_id)
        .join(Variant, Variant.product_id == Product.id)
        .where(Variant.id == variant_id)
    )
    if owner != scope:
        raise NotFoundError("Variant not found")


async def image_in_scope(db: AsyncSession, scope: int | None, image_id: int) -> None:
    if scope is None:
        return
    owner = await db.scalar(
        select(Product.seller_id)
        .join(ProductImage, ProductImage.product_id == Product.id)
        .where(ProductImage.id == image_id)
    )
    if owner != scope:
        raise NotFoundError("Image not found")


async def translation_in_scope(
    db: AsyncSession, scope: int | None, entity_type: str, entity_id: int
) -> None:
    if scope is None:
        return
    # Category and attribute names are platform data, like the categories themselves.
    if entity_type != "product":
        raise ForbiddenError("Sellers only translate their own products", code="platform_data")
    await product_in_scope(db, scope, entity_id)


async def _check_seller_exists(db: AsyncSession, seller_id: int) -> None:
    if await db.scalar(select(Seller.id).where(Seller.id == seller_id)) is None:
        raise NotFoundError("Seller not found")


async def seller_for_new_product(db: AsyncSession, scope: int | None, requested: int | None) -> int:
    """A seller's new products are always their own; platform staff must say whose it is."""
    if scope is not None:
        if requested is not None and requested != scope:
            raise NotFoundError("Seller not found")
        return scope
    if requested is None:
        raise BadRequestError("seller_id is required")
    await _check_seller_exists(db, requested)
    return requested


async def check_product_update(db: AsyncSession, scope: int | None, data: ProductUpdate) -> None:
    """Only platform staff move a product to another seller."""
    if "seller_id" not in data.model_fields_set:
        return
    if scope is not None:
        raise ForbiddenError("A seller cannot move products", code="seller_change")
    if data.seller_id is None:
        raise BadRequestError("seller_id cannot be empty")
    await _check_seller_exists(db, data.seller_id)


def seller_filter(scope: int | None, requested: int | None) -> int | None:
    """A seller always lists their own products, whatever they ask for."""
    return scope if scope is not None else requested
