import asyncio
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import media_storage
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.images import ImageRejectedError, to_webp
from app.core.media_storage import MediaStorage
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.variant import Variant
from app.schemas.internal import ProductImageCreate, ProductImageOut, ProductImageUpdate

settings = get_settings()

MEDIA_URL_PREFIX = "/media/"


def _storage() -> MediaStorage:
    # Built per call so settings patched in tests (media_root, media_storage) are honoured.
    return media_storage.from_settings(settings)


async def _check_target(db: AsyncSession, product_id: int, variant_id: int | None) -> None:
    if await db.scalar(select(Product.id).where(Product.id == product_id)) is None:
        raise NotFoundError("Product not found")
    if variant_id is not None and (
        await db.scalar(
            select(Variant.id).where(Variant.id == variant_id, Variant.product_id == product_id)
        )
        is None
    ):
        raise BadRequestError("The variant does not belong to this product")


async def add_image_by_url(
    db: AsyncSession, product_id: int, data: ProductImageCreate
) -> ProductImageOut:
    await _check_target(db, product_id, data.variant_id)
    image = ProductImage(product_id=product_id, **data.model_dump())
    db.add(image)
    await db.commit()
    return ProductImageOut.model_validate(image)


async def add_uploaded_image(
    db: AsyncSession, product_id: int, raw: bytes, variant_id: int | None, position: int
) -> ProductImageOut:
    await _check_target(db, product_id, variant_id)
    try:
        webp = await asyncio.to_thread(to_webp, raw)
    except ImageRejectedError as exc:
        raise BadRequestError(str(exc)) from exc

    storage_key = f"products/{uuid4().hex}.webp"
    storage = _storage()
    # A MediaStorageError (R2 unreachable) becomes a 502 media_unavailable in the handlers.
    await asyncio.to_thread(storage.save, storage_key, webp)

    image = ProductImage(
        product_id=product_id,
        variant_id=variant_id,
        url=f"{MEDIA_URL_PREFIX}{storage_key}",
        position=position,
        storage_key=storage_key,
    )
    db.add(image)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        await asyncio.to_thread(storage.remove, storage_key)
        raise
    return ProductImageOut.model_validate(image)


async def update_image(
    db: AsyncSession, image_id: int, data: ProductImageUpdate
) -> ProductImageOut:
    image = await db.get(ProductImage, image_id, populate_existing=True)
    if image is None:
        raise NotFoundError("Image not found")
    changes = data.model_dump(exclude_unset=True)
    if "variant_id" in changes:
        await _check_target(db, image.product_id, changes["variant_id"])
    for field, value in changes.items():
        setattr(image, field, value)
    await db.commit()
    return ProductImageOut.model_validate(image)


async def delete_image(db: AsyncSession, image_id: int) -> None:
    image = await db.get(ProductImage, image_id, populate_existing=True)
    if image is None:
        raise NotFoundError("Image not found")
    storage_key = image.storage_key
    await db.delete(image)
    await db.commit()
    # Only after the commit: a failed delete must not leave a row pointing at a missing file.
    if storage_key:
        await asyncio.to_thread(_storage().remove, storage_key)
