import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.images import ImageRejectedError, to_webp
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.variant import Variant
from app.schemas.internal import ProductImageCreate, ProductImageOut, ProductImageUpdate

settings = get_settings()
logger = logging.getLogger(__name__)

MEDIA_URL_PREFIX = "/media/"


def _path_for(storage_key: str) -> Path:
    root = Path(settings.media_root).resolve()
    path = (root / storage_key).resolve()
    if root not in path.parents:  # storage keys are ours, but never trust a path blindly
        raise ValueError(f"storage key escapes MEDIA_ROOT: {storage_key!r}")
    return path


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _remove(storage_key: str) -> None:
    try:
        _path_for(storage_key).unlink(missing_ok=True)
    except (OSError, ValueError):
        # The row is already gone; an orphaned file is harmless, a 500 here would not be.
        logger.warning("could not remove media file %s", storage_key, exc_info=True)


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
    await asyncio.to_thread(_write, _path_for(storage_key), webp)

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
        await asyncio.to_thread(_remove, storage_key)
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
        await asyncio.to_thread(_remove, storage_key)
