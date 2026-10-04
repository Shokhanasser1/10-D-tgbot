from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.i18n import translations_for
from app.models.category import Category
from app.models.enums import ProductStatus
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.seller import Seller
from app.schemas.catalog import (
    CategoryOut,
    ProductDetailOut,
    ProductListItemOut,
    SellerBrief,
    VariantOut,
)


async def list_categories(db: AsyncSession, locale: str, fallback_locale: str) -> list[CategoryOut]:
    categories = (await db.execute(select(Category).order_by(Category.sort_order))).scalars().all()

    names = await translations_for(
        db, "category", [c.id for c in categories], ["name"], locale, fallback_locale
    )

    return [
        CategoryOut(
            id=c.id,
            slug=c.slug,
            parent_id=c.parent_id,
            sort_order=c.sort_order,
            name=names.get((c.id, "name"), c.slug),
        )
        for c in categories
    ]


async def list_products(
    db: AsyncSession,
    locale: str,
    fallback_locale: str,
    category_id: int | None = None,
    status: ProductStatus = ProductStatus.active,
    seller_id: int | None = None,
) -> list[ProductListItemOut]:
    # A deactivated seller's products leave the shop with it (Spec 9 section 6).
    stmt = (
        select(Product, Seller)
        .join(Seller, Seller.id == Product.seller_id)
        .where(Product.status == status, Seller.is_active)
    )
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if seller_id is not None:
        stmt = stmt.where(Product.seller_id == seller_id)
    rows = (await db.execute(stmt)).tuples().all()
    products = [product for product, _ in rows]
    sellers = {product.id: seller for product, seller in rows}

    product_ids = [p.id for p in products]
    names = await translations_for(db, "product", product_ids, ["name"], locale, fallback_locale)

    thumbnails: dict[int, str] = {}
    if product_ids:
        image_stmt = (
            select(ProductImage)
            .where(ProductImage.product_id.in_(product_ids), ProductImage.variant_id.is_(None))
            .order_by(ProductImage.product_id, ProductImage.position)
        )
        for image in (await db.execute(image_stmt)).scalars().all():
            thumbnails.setdefault(image.product_id, image.url)

    return [
        ProductListItemOut(
            id=p.id,
            category_id=p.category_id,
            seller=SellerBrief(id=sellers[p.id].id, name=sellers[p.id].name),
            base_sku=p.base_sku,
            base_price=p.base_price,
            name=names.get((p.id, "name"), p.base_sku),
            thumbnail_url=thumbnails.get(p.id),
        )
        for p in products
    ]


async def get_product(
    db: AsyncSession, product_id: int, locale: str, fallback_locale: str
) -> ProductDetailOut | None:
    stmt = (
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
            selectinload(Product.seller),
        )
    )
    product = (await db.execute(stmt)).scalar_one_or_none()
    if product is None or not product.seller.is_active:
        return None

    texts = await translations_for(
        db, "product", [product.id], ["name", "description"], locale, fallback_locale
    )

    product_images = sorted(
        (img for img in product.images if img.variant_id is None), key=lambda i: i.position
    )
    variant_images: dict[int, list[str]] = {}
    for img in sorted(product.images, key=lambda i: i.position):
        if img.variant_id is not None:
            variant_images.setdefault(img.variant_id, []).append(img.url)

    return ProductDetailOut(
        id=product.id,
        category_id=product.category_id,
        seller=SellerBrief(id=product.seller.id, name=product.seller.name),
        base_sku=product.base_sku,
        base_price=product.base_price,
        name=texts.get((product.id, "name"), product.base_sku),
        description=texts.get((product.id, "description")),
        image_urls=[img.url for img in product_images],
        variants=[
            VariantOut(
                id=v.id,
                sku=v.sku,
                price=v.price,
                stock_qty=v.stock_qty,
                attribute_values=v.attribute_values,
                image_urls=variant_images.get(v.id, []),
            )
            for v in product.variants
        ],
    )
