"""The slice of Telegram's Update object we read: Live Location, /start and payments.

Deliberately lenient: unknown fields are ignored and nearly everything is optional, because
Telegram sends many kinds of update to the same endpoint and only one carries a position.
"""

from pydantic import BaseModel, ConfigDict, Field


class TelegramSender(BaseModel):
    id: int
    is_bot: bool = False
    language_code: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str


class TelegramLocation(BaseModel):
    latitude: float
    longitude: float


class TelegramSuccessfulPayment(BaseModel):
    currency: str
    total_amount: int
    invoice_payload: str
    telegram_payment_charge_id: str
    provider_payment_charge_id: str


class TelegramMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sender: TelegramSender | None = Field(default=None, alias="from")
    chat: TelegramChat | None = None
    location: TelegramLocation | None = None
    text: str | None = None
    successful_payment: TelegramSuccessfulPayment | None = None


class TelegramPreCheckoutQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    sender: TelegramSender = Field(alias="from")
    currency: str
    total_amount: int
    invoice_payload: str


class TelegramUpdate(BaseModel):
    update_id: int
    # A live location arrives first as `message`; every later position as `edited_message`.
    message: TelegramMessage | None = None
    edited_message: TelegramMessage | None = None
    # Telegram asks the bot to confirm an order right before charging the customer.
    pre_checkout_query: TelegramPreCheckoutQuery | None = None
