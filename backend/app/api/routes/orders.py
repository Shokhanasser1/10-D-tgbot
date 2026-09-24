from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_telegram_user
from app.db.session import get_db
from app.models.telegram_user import TelegramUser
from app.schemas.orders import OrderDetailOut, OrderListItemOut
from app.schemas.tracking import TrackingOut
from app.services import order_service, tracking_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderListItemOut])
async def list_orders(
    user: TelegramUser = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
):
    return await order_service.list_orders_for_user(db, user.telegram_id)


@router.get("/{order_id}", response_model=OrderDetailOut)
async def get_order(
    order_id: int,
    user: TelegramUser = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
):
    return await order_service.get_order_detail(db, user.telegram_id, order_id)


@router.get("/{order_id}/tracking", response_model=TrackingOut)
async def get_order_tracking(
    order_id: int,
    user: TelegramUser = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
):
    return await tracking_service.get_order_tracking(db, user.telegram_id, order_id)
