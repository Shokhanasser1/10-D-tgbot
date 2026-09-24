"""The slice of Telegram's Update object we read (Live Location messages).

Deliberately lenient: unknown fields are ignored and nearly everything is optional, because
Telegram sends many kinds of update to the same endpoint and only one carries a position.
"""

from pydantic import BaseModel, ConfigDict, Field


class TelegramSender(BaseModel):
    id: int
    is_bot: bool = False


class TelegramChat(BaseModel):
    id: int
    type: str


class TelegramLocation(BaseModel):
    latitude: float
    longitude: float


class TelegramMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sender: TelegramSender | None = Field(default=None, alias="from")
    chat: TelegramChat | None = None
    location: TelegramLocation | None = None


class TelegramUpdate(BaseModel):
    update_id: int
    # A live location arrives first as `message`; every later position as `edited_message`.
    message: TelegramMessage | None = None
    edited_message: TelegramMessage | None = None
