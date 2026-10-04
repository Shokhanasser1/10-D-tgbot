from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BalanceOut(BaseModel):
    """One currency of a seller's account: earned - paid_out = balance (owed to the seller)."""

    currency: str
    earned: Decimal
    paid_out: Decimal
    balance: Decimal


class EarningOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: int
    earned_at: datetime
    currency: str
    goods_total: Decimal
    commission_percent: Decimal
    commission: Decimal
    amount: Decimal


class PayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    currency: str
    amount: Decimal
    note: str | None


class PayoutCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    note: str | None = Field(default=None, max_length=500)


class LedgerOut(BaseModel):
    balances: list[BalanceOut]
    # Newest first, the last 100 of each.
    earnings: list[EarningOut]
    payouts: list[PayoutOut]
