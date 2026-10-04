from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.payouts import BalanceOut

_RATE = {"ge": 0, "le": 100, "max_digits": 5, "decimal_places": 2}


class SellerCreate(BaseModel):
    """A seller and the account of the person who runs it, created together (Spec 9 §5)."""

    name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    pickup_address: str = Field(min_length=1, max_length=500)
    telegram_id: int = Field(gt=0)
    display_name: str = Field(min_length=1, max_length=100)
    # The platform's share of the goods (Spec 11).
    commission_percent: Decimal = Field(default=Decimal("10"), **_RATE)


class SellerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    pickup_address: str | None = Field(default=None, min_length=1, max_length=500)
    is_active: bool | None = None
    commission_percent: Decimal | None = Field(default=None, **_RATE)

    @model_validator(mode="after")
    def _required_fields_cannot_be_nulled(self) -> "SellerUpdate":
        for field in ("name", "pickup_address", "is_active", "commission_percent"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class SellerAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    display_name: str
    is_active: bool


class SellerOut(BaseModel):
    id: int
    name: str
    phone: str | None
    pickup_address: str | None
    is_active: bool
    # Empty for callers who may not manage sellers: Telegram ids are not theirs to see.
    accounts: list[SellerAccountOut]
    product_count: int
    commission_percent: Decimal
    # Empty unless the caller handles payouts (Spec 11).
    balances: list[BalanceOut] = []
