from fastapi import APIRouter, Depends

from app.api.deps import get_current_courier
from app.config import get_settings
from app.models.courier import Courier
from app.schemas.courier import CourierProfileOut

router = APIRouter(prefix="/courier", tags=["courier"])
settings = get_settings()


@router.get("/me", response_model=CourierProfileOut)
async def get_me(courier: Courier = Depends(get_current_courier)):
    return CourierProfileOut(
        id=courier.id,
        name=courier.name,
        bot_username=settings.telegram_bot_username or None,
        max_active_deliveries=settings.max_active_deliveries_per_courier,
    )
