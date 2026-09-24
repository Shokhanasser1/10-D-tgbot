from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AdminRole


class AdminMeOut(BaseModel):
    telegram_id: int | None  # None when authenticated with the internal token
    display_name: str
    role: AdminRole


class TelegramLoginIn(BaseModel):
    """Telegram Login Widget payload, passed through exactly as the widget produced it."""

    model_config = ConfigDict(extra="allow")

    id: int
    auth_date: int
    hash: str
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None


class AdminCreate(BaseModel):
    telegram_id: int = Field(gt=0)
    role: AdminRole
    display_name: str = Field(min_length=1, max_length=100)


class AdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: AdminRole | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None

    @model_validator(mode="after")
    def _fields_cannot_be_nulled(self) -> "AdminUpdate":
        for field in ("role", "display_name", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    role: AdminRole
    display_name: str
    is_active: bool
    created_at: datetime
    created_by: int | None
