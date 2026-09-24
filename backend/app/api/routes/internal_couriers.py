from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_internal_token
from app.db.session import get_db
from app.schemas.courier_admin import CourierAdminOut, CourierCreate, CourierUpdate
from app.services import courier_admin_service

router = APIRouter(
    prefix="/internal", tags=["internal"], dependencies=[Depends(verify_internal_token)]
)


@router.post("/couriers", response_model=CourierAdminOut, status_code=status.HTTP_201_CREATED)
async def create_courier(data: CourierCreate, db: AsyncSession = Depends(get_db)):
    return await courier_admin_service.create_courier(db, data)


@router.patch("/couriers/{courier_id}", response_model=CourierAdminOut)
async def update_courier(courier_id: int, data: CourierUpdate, db: AsyncSession = Depends(get_db)):
    return await courier_admin_service.update_courier(db, courier_id, data)


@router.get("/couriers", response_model=list[CourierAdminOut])
async def list_couriers(db: AsyncSession = Depends(get_db)):
    return await courier_admin_service.list_couriers(db)
