from pydantic import BaseModel


class CourierProfileOut(BaseModel):
    id: int
    name: str
    bot_username: str | None
    max_active_deliveries: int
