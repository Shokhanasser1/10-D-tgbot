"""The demo seed is the first thing a new student runs, so it must keep working."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.variant import Variant
from scripts.seed_demo_data import seed_into


async def test_the_demo_catalog_seeds(db_session: AsyncSession) -> None:
    await seed_into(db_session)

    assert await db_session.scalar(select(func.count()).select_from(Product)) == 2
    assert await db_session.scalar(select(func.count()).select_from(Variant)) == 4
    assert await db_session.scalar(select(func.count()).select_from(ProductImage)) == 2
