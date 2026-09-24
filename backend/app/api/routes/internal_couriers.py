from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DISPATCH_ROLES, require_admin
from app.db.session import get_db
from app.models.enums import ACTIVE_SHIPMENT_STATUSES, ShipmentStatus
from app.schemas.courier import ShipmentActionOut
from app.schemas.courier_admin import (
    CourierAdminListItem,
    CourierAdminOut,
    CourierCreate,
    CourierLocationAdminOut,
    CourierUpdate,
    ShipmentAdminOut,
)
from app.services import courier_admin_service, dispatch_service

router = APIRouter(
    prefix="/internal", tags=["internal"], dependencies=[Depends(require_admin(*DISPATCH_ROLES))]
)


@router.post("/couriers", response_model=CourierAdminOut, status_code=status.HTTP_201_CREATED)
async def create_courier(data: CourierCreate, db: AsyncSession = Depends(get_db)):
    return await courier_admin_service.create_courier(db, data)


@router.patch("/couriers/{courier_id}", response_model=CourierAdminOut)
async def update_courier(courier_id: int, data: CourierUpdate, db: AsyncSession = Depends(get_db)):
    return await courier_admin_service.update_courier(db, courier_id, data)


@router.get("/couriers/locations", response_model=list[CourierLocationAdminOut])
async def list_courier_locations(db: AsyncSession = Depends(get_db)):
    return await courier_admin_service.list_locations(db)


@router.get("/couriers", response_model=list[CourierAdminListItem])
async def list_couriers(db: AsyncSession = Depends(get_db)):
    return await courier_admin_service.list_couriers(db)


@router.get("/shipments", response_model=list[ShipmentAdminOut])
async def list_shipments(
    # Repeat the parameter to select several: ?status=assigned&status=shipped. The default is
    # the deliveries a courier is currently holding, which is what you look for when stuck.
    shipment_status: list[ShipmentStatus] | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    return await courier_admin_service.list_shipments(
        db, shipment_status or ACTIVE_SHIPMENT_STATUSES
    )


@router.post("/shipments/{shipment_id}/release", response_model=ShipmentActionOut)
async def release_shipment(shipment_id: int, db: AsyncSession = Depends(get_db)):
    return await dispatch_service.force_release(db, shipment_id)
