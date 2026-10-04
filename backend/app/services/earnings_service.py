"""Spec 11: sellers' earnings (one per delivered order) and the money paid out to them."""

from collections import defaultdict
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.order import Order
from app.models.seller import Seller
from app.models.seller_money import SellerEarning, SellerPayout
from app.schemas.payouts import BalanceOut, EarningOut, LedgerOut, PayoutCreate, PayoutOut
from app.services import notification_events

LEDGER_LIMIT = 100

CENT = Decimal("0.01")


def commission_of(goods_total: Decimal, percent: Decimal) -> Decimal:
    """The platform's part of the goods, half-up to cents (12.5% of 10.04 is 1.26)."""
    return (goods_total * percent / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)


async def record_earning(db: AsyncSession, order_id: int) -> None:
    """The seller's share of a delivered order (no commit: delivery commits it).

    Uses the rate copied onto the order at checkout. A second call for the same order (a
    replayed delivery) adds nothing.
    """
    order = (
        await db.execute(
            select(Order.seller_id, Order.currency, Order.subtotal, Order.commission_percent).where(
                Order.id == order_id
            )
        )
    ).one()
    commission = commission_of(order.subtotal, order.commission_percent)
    await db.execute(
        pg_insert(SellerEarning)
        .values(
            order_id=order_id,
            seller_id=order.seller_id,
            currency=order.currency,
            goods_total=order.subtotal,
            commission_percent=order.commission_percent,
            commission=commission,
            amount=order.subtotal - commission,
        )
        .on_conflict_do_nothing(index_elements=[SellerEarning.order_id])
    )


async def balances(db: AsyncSession, seller_ids: Iterable[int]) -> dict[int, list[BalanceOut]]:
    """Per seller and currency: earned - paid out = owed. Sellers with neither are left out."""
    ids = list(seller_ids)
    totals: dict[tuple[int, str], list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
    if not ids:
        return {}
    earned = await db.execute(
        select(SellerEarning.seller_id, SellerEarning.currency, func.sum(SellerEarning.amount))
        .where(SellerEarning.seller_id.in_(ids))
        .group_by(SellerEarning.seller_id, SellerEarning.currency)
    )
    for seller_id, currency, amount in earned:
        totals[(seller_id, currency)][0] = amount
    paid = await db.execute(
        select(SellerPayout.seller_id, SellerPayout.currency, func.sum(SellerPayout.amount))
        .where(SellerPayout.seller_id.in_(ids))
        .group_by(SellerPayout.seller_id, SellerPayout.currency)
    )
    for seller_id, currency, amount in paid:
        totals[(seller_id, currency)][1] = amount

    result: dict[int, list[BalanceOut]] = defaultdict(list)
    for (seller_id, currency), (earned_amount, paid_amount) in sorted(totals.items()):
        result[seller_id].append(
            BalanceOut(
                currency=currency,
                earned=earned_amount.quantize(CENT),
                paid_out=paid_amount.quantize(CENT),
                balance=(earned_amount - paid_amount).quantize(CENT),
            )
        )
    return result


async def ledger(db: AsyncSession, seller_id: int) -> LedgerOut:
    if await db.scalar(select(Seller.id).where(Seller.id == seller_id)) is None:
        raise NotFoundError("Seller not found")
    earnings = await db.scalars(
        select(SellerEarning)
        .where(SellerEarning.seller_id == seller_id)
        .order_by(SellerEarning.earned_at.desc(), SellerEarning.id.desc())
        .limit(LEDGER_LIMIT)
    )
    payouts = await db.scalars(
        select(SellerPayout)
        .where(SellerPayout.seller_id == seller_id)
        .order_by(SellerPayout.created_at.desc(), SellerPayout.id.desc())
        .limit(LEDGER_LIMIT)
    )
    return LedgerOut(
        balances=(await balances(db, [seller_id])).get(seller_id, []),
        earnings=[EarningOut.model_validate(e) for e in earnings],
        payouts=[PayoutOut.model_validate(p) for p in payouts],
    )


async def record_payout(
    db: AsyncSession, seller_id: int, data: PayoutCreate, created_by: int | None
) -> PayoutOut:
    """Money the owner sent by hand. Never more than the seller is owed in that currency."""
    # Lock the seller: two payouts recorded at once must not both pass the balance check.
    locked = await db.scalar(select(Seller.id).where(Seller.id == seller_id).with_for_update())
    if locked is None:
        raise NotFoundError("Seller not found")
    currency = data.currency.upper()
    owed = next(
        (
            b.balance
            for b in (await balances(db, [seller_id])).get(seller_id, [])
            if b.currency == currency
        ),
        Decimal(0),
    )
    if data.amount > owed:
        await db.rollback()
        raise ConflictError("More than the seller is owed", code="exceeds_balance")

    payout = SellerPayout(
        seller_id=seller_id,
        currency=currency,
        amount=data.amount,
        note=data.note.strip() if data.note and data.note.strip() else None,
        created_by=created_by,
    )
    db.add(payout)
    await db.flush()
    await notification_events.payout_recorded(
        db, seller_id, payout.id, data.amount, currency, owed - data.amount
    )
    await db.commit()
    await db.refresh(payout)
    return PayoutOut.model_validate(payout)
