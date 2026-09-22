from pydantic import BaseModel


class TelegramInitDataUser(BaseModel):
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None


class TelegramInitData(BaseModel):
    auth_date: int
    query_id: str | None = None
    user: TelegramInitDataUser
