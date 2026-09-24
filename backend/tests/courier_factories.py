from sqlalchemy.ext.asyncio import AsyncSession

from app.models.courier import Courier
from tests.factories import make_init_data

INTERNAL_HEADERS = {"X-Internal-Token": "test-internal-token"}


async def add_courier(
    db: AsyncSession,
    telegram_id: int,
    *,
    name: str = "Ali",
    phone: str | None = "+998900000000",
    is_active: bool = True,
) -> Courier:
    courier = Courier(telegram_id=telegram_id, name=name, phone=phone, is_active=is_active)
    db.add(courier)
    await db.commit()
    await db.refresh(courier)
    return courier


def tma_headers(telegram_id: int) -> dict[str, str]:
    """Authorization header for a Telegram user, signed the way the real client signs it."""
    return {"Authorization": f"tma {make_init_data(telegram_id=telegram_id)}"}
