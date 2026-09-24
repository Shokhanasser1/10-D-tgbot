from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_courier
from app.config import get_settings
from app.db.session import get_db
from app.models.courier import Courier
from app.schemas.courier import (
    CourierDeliveriesOut,
    CourierProfileOut,
    PoolItemOut,
    ShipmentActionOut,
)
from app.services import courier_service, dispatch_service

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


@router.get("/pool", response_model=list[PoolItemOut])
async def get_pool(
    _courier: Courier = Depends(get_current_courier), db: AsyncSession = Depends(get_db)
):
    return await courier_service.get_pool(db)


@router.get("/deliveries", response_model=CourierDeliveriesOut)
async def get_deliveries(
    courier: Courier = Depends(get_current_courier), db: AsyncSession = Depends(get_db)
):
    return await courier_service.get_deliveries(db, courier)


@router.post("/deliveries/{shipment_id}/claim", response_model=ShipmentActionOut)
async def claim(
    shipment_id: int,
    courier: Courier = Depends(get_current_courier),
    db: AsyncSession = Depends(get_db),
):
    return await dispatch_service.claim(db, courier, shipment_id)


@router.post("/deliveries/{shipment_id}/release", response_model=ShipmentActionOut)
async def release(
    shipment_id: int,
    courier: Courier = Depends(get_current_courier),
    db: AsyncSession = Depends(get_db),
):
    return await dispatch_service.release(db, courier, shipment_id)


@router.post("/deliveries/{shipment_id}/pickup", response_model=ShipmentActionOut)
async def pickup(
    shipment_id: int,
    courier: Courier = Depends(get_current_courier),
    db: AsyncSession = Depends(get_db),
):
    return await dispatch_service.pickup(db, courier, shipment_id)


@router.post("/deliveries/{shipment_id}/deliver", response_model=ShipmentActionOut)
async def deliver(
    shipment_id: int,
    courier: Courier = Depends(get_current_courier),
    db: AsyncSession = Depends(get_db),
):
    return await dispatch_service.deliver(db, courier, shipment_id)
