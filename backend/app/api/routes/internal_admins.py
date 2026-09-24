from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminPrincipal, require_admin
from app.db.session import get_db
from app.models.enums import AdminRole
from app.schemas.admin import AdminCreate, AdminOut, AdminUpdate
from app.services import admin_service

router = APIRouter(prefix="/internal", tags=["internal"])

_owner = require_admin(AdminRole.owner)


@router.get("/admins", response_model=list[AdminOut])
async def list_admins(_: AdminPrincipal = Depends(_owner), db: AsyncSession = Depends(get_db)):
    return await admin_service.list_admins(db)


@router.post("/admins", response_model=AdminOut, status_code=status.HTTP_201_CREATED)
async def create_admin(
    data: AdminCreate,
    principal: AdminPrincipal = Depends(_owner),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.create_admin(db, data, created_by=principal.telegram_id)


@router.patch("/admins/{admin_id}", response_model=AdminOut)
async def update_admin(
    admin_id: int,
    data: AdminUpdate,
    principal: AdminPrincipal = Depends(_owner),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.update_admin(db, admin_id, data, principal.telegram_id)
