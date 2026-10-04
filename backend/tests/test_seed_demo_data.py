"""The demo seed is the first thing a new student runs, so it must keep working."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.seller import Seller
from app.models.variant import Variant
from scripts.seed_demo_data import seed_into


async def test_the_demo_catalog_seeds(db_session: AsyncSession) -> None:
    await seed_into(db_session)

    assert await db_session.scalar(select(func.count()).select_from(Product)) == 2
    assert await db_session.scalar(select(func.count()).select_from(Variant)) == 4
    assert await db_session.scalar(select(func.count()).select_from(ProductImage)) == 2

    # Spec 9: every product has a seller; the demo has one shop with a pickup address.
    (shop,) = (await db_session.execute(select(Seller))).scalars().all()
    assert (shop.name, shop.pickup_address is not None) == ("Demo shop", True)
    sellers = (await db_session.execute(select(Product.seller_id))).scalars().all()
    assert set(sellers) == {shop.id}
