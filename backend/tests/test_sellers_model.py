"""Spec 9 §3: every product has a seller; only seller accounts point at one."""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Admin, Category, Product, Seller
from app.models.enums import AdminRole, ProductStatus
from tests.admin_factories import add_admin
from tests.factories import add_seller, default_seller_id


async def _category(db: AsyncSession) -> Category:
    category = Category(slug="sellers-model", sort_order=0)
    db.add(category)
    await db.flush()
    return category


async def test_a_product_belongs_to_its_seller(db_session: AsyncSession) -> None:
    seller = await add_seller(db_session, "Lola Beauty")
    category = await _category(db_session)
    product = Product(
        category_id=category.id,
        seller_id=seller.id,
        base_sku="SELLER-P-1",
        base_price=Decimal("10.00"),
        status=ProductStatus.active,
    )
    db_session.add(product)
    await db_session.flush()

    await db_session.refresh(product, ["seller"])
    assert product.seller.name == "Lola Beauty"
    assert product.seller.is_active is True


async def test_a_product_without_a_seller_is_refused(db_session: AsyncSession) -> None:
    category = await _category(db_session)
    db_session.add(
        Product(category_id=category.id, base_sku="SELLER-P-2", base_price=Decimal("1.00"))
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_a_seller_account_needs_a_seller(db_session: AsyncSession) -> None:
    db_session.add(Admin(telegram_id=830_001, role=AdminRole.seller, display_name="Lola"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_only_seller_accounts_may_point_at_a_seller(db_session: AsyncSession) -> None:
    seller_id = await default_seller_id(db_session)
    db_session.add(
        Admin(
            telegram_id=830_002,
            role=AdminRole.manager,
            display_name="Manager",
            seller_id=seller_id,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_add_admin_gives_a_seller_account_its_own_seller(db_session: AsyncSession) -> None:
    admin = await add_admin(db_session, 830_003, AdminRole.seller)

    seller = await db_session.get(Seller, admin.seller_id)
    assert seller is not None and seller.is_active


async def test_default_seller_is_shared_within_a_test(db_session: AsyncSession) -> None:
    assert await default_seller_id(db_session) == await default_seller_id(db_session)
