"""Catalog reads for the admin panel: every status and every language, unfiltered."""

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import translations_for
from app.models.attribute import Attribute
from app.models.category import Category
from app.models.enums import ProductStatus
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.translation import Translation
from app.models.variant import Variant
from app.schemas.internal import (
    AttributeAdminListItem,
    AttributeAdminOut,
    CategoryAdminListItem,
    ProductAdminDetailOut,
    ProductAdminListItem,
    ProductAdminPage,
    ProductImageOut,
    Translations,
    VariantAdminOut,
)

_LIKE_ESCAPE = "\\"


async def _all_translations(
    db: AsyncSession, entity_type: str, entity_ids: Sequence[int]
) -> dict[int, Translations]:
    result: dict[int, Translations] = defaultdict(dict)
    if not entity_ids:
        return result
    rows = (
        await db.execute(
            select(Translation).where(
                Translation.entity_type == entity_type, Translation.entity_id.in_(entity_ids)
            )
        )
    ).scalars()
    for row in rows:
        result[row.entity_id].setdefault(row.locale, {})[row.field] = row.value
    return result


def _name(texts: Translations, locale: str, fallback_locale: str, default: str) -> str:
    return (
        texts.get(locale, {}).get("name") or texts.get(fallback_locale, {}).get("name") or default
    )


async def list_categories(
    db: AsyncSession, locale: str, fallback_locale: str
) -> list[CategoryAdminListItem]:
    categories = (
        (await db.execute(select(Category).order_by(Category.sort_order, Category.id)))
        .scalars()
        .all()
    )
    texts = await _all_translations(db, "category", [c.id for c in categories])
    return [
        CategoryAdminListItem(
            id=c.id,
            slug=c.slug,
            parent_id=c.parent_id,
            sort_order=c.sort_order,
            name=_name(texts[c.id], locale, fallback_locale, c.slug),
            translations=texts[c.id],
        )
        for c in categories
    ]


async def list_attributes(db: AsyncSession) -> list[AttributeAdminListItem]:
    attributes = (
        (await db.execute(select(Attribute).order_by(Attribute.category_id, Attribute.key)))
        .scalars()
        .all()
    )
    texts = await _all_translations(db, "attribute", [a.id for a in attributes])
    return [
        AttributeAdminListItem(
            **AttributeAdminOut.model_validate(a).model_dump(), translations=texts[a.id]
        )
        for a in attributes
    ]


def _escape_like(value: str) -> str:
    return (
        value.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
        .replace("%", _LIKE_ESCAPE + "%")
        .replace("_", _LIKE_ESCAPE + "_")
    )


def _filtered(
    stmt: Select, status: ProductStatus | None, category_id: int | None, q: str | None
) -> Select:
    if status is not None:
        stmt = stmt.where(Product.status == status)
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        name_match = select(Translation.entity_id).where(
            Translation.entity_type == "product",
            Translation.field == "name",
            Translation.value.ilike(pattern, escape=_LIKE_ESCAPE),
        )
        sku_match = select(Variant.product_id).where(
            Variant.sku.ilike(pattern, escape=_LIKE_ESCAPE)
        )
        stmt = stmt.where(
            or_(
                Product.base_sku.ilike(pattern, escape=_LIKE_ESCAPE),
                Product.id.in_(name_match),
                Product.id.in_(sku_match),
            )
        )
    return stmt


async def list_products(
    db: AsyncSession,
    locale: str,
    fallback_locale: str,
    *,
    status: ProductStatus | None = None,
    category_id: int | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ProductAdminPage:
    total = await db.scalar(
        _filtered(select(func.count()).select_from(Product), status, category_id, q)
    )
    products = (
        (
            await db.execute(
                _filtered(select(Product), status, category_id, q)
                .order_by(Product.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    ids = [p.id for p in products]
    names = await translations_for(db, "product", ids, ["name"], locale, fallback_locale)

    stats: dict[int, tuple[int, Decimal | None, int]] = {}
    thumbnails: dict[int, str] = {}
    if ids:
        variant_stats = await db.execute(
            select(
                Variant.product_id,
                func.count(Variant.id),
                func.min(Variant.price),
                func.coalesce(func.sum(Variant.stock_qty), 0),
            )
            .where(Variant.product_id.in_(ids))
            .group_by(Variant.product_id)
        )
        for product_id, count, min_price, stock in variant_stats:
            stats[product_id] = (count, min_price, stock)
        # Product-level images first, then variant images, each by position.
        images = await db.execute(
            select(ProductImage.product_id, ProductImage.url)
            .where(ProductImage.product_id.in_(ids))
            .order_by(
                ProductImage.product_id,
                ProductImage.variant_id.is_not(None),
                ProductImage.position,
                ProductImage.id,
            )
        )
        for product_id, url in images:
            thumbnails.setdefault(product_id, url)

    items = []
    for p in products:
        count, min_price, stock = stats.get(p.id, (0, None, 0))
        items.append(
            ProductAdminListItem(
                id=p.id,
                category_id=p.category_id,
                base_sku=p.base_sku,
                base_price=p.base_price,
                status=p.status,
                name=names.get((p.id, "name"), p.base_sku),
                thumbnail_url=thumbnails.get(p.id),
                variant_count=count,
                min_price=min_price,
                total_stock=stock,
            )
        )
    return ProductAdminPage(items=items, total=total or 0)


async def get_product(
    db: AsyncSession, product_id: int, locale: str, fallback_locale: str
) -> ProductAdminDetailOut | None:
    product = await db.get(Product, product_id, populate_existing=True)
    if product is None:
        return None
    variants = (
        (
            await db.execute(
                select(Variant)
                .where(Variant.product_id == product_id)
                .order_by(Variant.id)
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )
    images = (
        (
            await db.execute(
                select(ProductImage)
                .where(ProductImage.product_id == product_id)
                .order_by(ProductImage.position, ProductImage.id)
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )
    texts = (await _all_translations(db, "product", [product_id]))[product_id]
    return ProductAdminDetailOut(
        id=product.id,
        category_id=product.category_id,
        base_sku=product.base_sku,
        base_price=product.base_price,
        status=product.status,
        name=_name(texts, locale, fallback_locale, product.base_sku),
        translations=texts,
        variants=[VariantAdminOut.model_validate(v) for v in variants],
        images=[ProductImageOut.model_validate(i) for i in images],
    )
