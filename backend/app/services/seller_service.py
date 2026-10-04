"""Spec 9 §5: sellers and their accounts, managed by the owner and the manager."""

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.admin import Admin
from app.models.enums import AdminRole
from app.models.product import Product
from app.models.seller import Seller
from app.schemas.seller import SellerAccountOut, SellerCreate, SellerOut, SellerUpdate
from app.services import earnings_service

_DUPLICATE = "An admin with this Telegram ID already exists"


async def list_sellers(
    db: AsyncSession,
    *,
    only_id: int | None = None,
    with_accounts: bool = True,
    with_balances: bool = False,
) -> list[SellerOut]:
    stmt = select(Seller).order_by(Seller.name, Seller.id).execution_options(populate_existing=True)
    if only_id is not None:
        stmt = stmt.where(Seller.id == only_id)
    sellers = (await db.execute(stmt)).scalars().all()
    ids = [s.id for s in sellers]

    accounts: dict[int, list[SellerAccountOut]] = defaultdict(list)
    counts: dict[int, int] = {}
    if ids:
        if with_accounts:
            rows = await db.execute(
                select(Admin)
                .where(Admin.seller_id.in_(ids))
                .order_by(Admin.id)
                .execution_options(populate_existing=True)
            )
            for admin in rows.scalars():
                accounts[admin.seller_id].append(SellerAccountOut.model_validate(admin))
        counted = await db.execute(
            select(Product.seller_id, func.count())
            .where(Product.seller_id.in_(ids))
            .group_by(Product.seller_id)
        )
        counts = dict(counted.tuples().all())
    money = await earnings_service.balances(db, ids) if with_balances else {}

    return [
        SellerOut(
            id=s.id,
            name=s.name,
            phone=s.phone,
            pickup_address=s.pickup_address,
            is_active=s.is_active,
            accounts=accounts[s.id],
            product_count=counts.get(s.id, 0),
            commission_percent=s.commission_percent,
            balances=money.get(s.id, []),
        )
        for s in sellers
    ]


async def _one(db: AsyncSession, seller_id: int) -> SellerOut:
    found = await list_sellers(db, only_id=seller_id)
    if not found:
        raise NotFoundError("Seller not found")
    return found[0]


async def create_seller(db: AsyncSession, data: SellerCreate, created_by: int | None) -> SellerOut:
    if await db.scalar(select(Admin.id).where(Admin.telegram_id == data.telegram_id)):
        raise ConflictError(_DUPLICATE, code="already_exists")

    seller = Seller(
        name=data.name,
        phone=data.phone,
        pickup_address=data.pickup_address,
        commission_percent=data.commission_percent,
    )
    db.add(seller)
    await db.flush()
    db.add(
        Admin(
            telegram_id=data.telegram_id,
            role=AdminRole.seller,
            display_name=data.display_name,
            seller_id=seller.id,
            created_by=created_by,
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:  # lost a race with a concurrent create
        await db.rollback()
        raise ConflictError(_DUPLICATE, code="already_exists") from exc
    return await _one(db, seller.id)


async def update_seller(db: AsyncSession, seller_id: int, data: SellerUpdate) -> SellerOut:
    seller = await db.get(Seller, seller_id, populate_existing=True)
    if seller is None:
        raise NotFoundError("Seller not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(seller, field, value)
    await db.commit()
    return await _one(db, seller_id)
