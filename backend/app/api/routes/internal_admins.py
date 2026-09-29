from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminPrincipal, require_permission
from app.db.session import get_db
from app.models.enums import Permission
from app.schemas.admin import AdminCreate, AdminOut, AdminUpdate, PasswordResetOut
from app.services import admin_service

router = APIRouter(prefix="/internal", tags=["internal"])

# Changing who is an admin needs the password re-entered; looking at the list does not.
_read = require_permission(Permission.admins_manage, confirm=False)
_manage = require_permission(Permission.admins_manage)


@router.get("/admins", response_model=list[AdminOut])
async def list_admins(_: AdminPrincipal = Depends(_read), db: AsyncSession = Depends(get_db)):
    return await admin_service.list_admins(db)


@router.post("/admins", response_model=AdminOut, status_code=status.HTTP_201_CREATED)
async def create_admin(
    data: AdminCreate,
    principal: AdminPrincipal = Depends(_manage),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.create_admin(db, data, created_by=principal.telegram_id)


@router.patch("/admins/{admin_id}", response_model=AdminOut)
async def update_admin(
    admin_id: int,
    data: AdminUpdate,
    principal: AdminPrincipal = Depends(_manage),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.update_admin(db, admin_id, data, principal.telegram_id)


@router.post("/admins/{admin_id}/password-reset", response_model=PasswordResetOut)
async def reset_admin_password(
    admin_id: int,
    principal: AdminPrincipal = Depends(_manage),
    db: AsyncSession = Depends(get_db),
):
    """A temporary password, shown once; the admin must replace it at the next sign-in."""
    admin, temporary = await admin_service.reset_password(db, admin_id, principal.telegram_id)
    return PasswordResetOut(login=admin.login or "", temporary_password=temporary)
