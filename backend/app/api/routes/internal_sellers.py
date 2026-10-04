from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminPrincipal, get_admin_principal, require_permission
from app.db.session import get_db
from app.models.enums import Permission
from app.schemas.seller import SellerCreate, SellerOut, SellerUpdate
from app.services import seller_service

router = APIRouter(prefix="/internal", tags=["internal"])

_manage = require_permission(Permission.sellers_manage)


async def _may_list(principal: AdminPrincipal = Depends(get_admin_principal)) -> AdminPrincipal:
    # The product editor offers a seller list, so catalog readers may see it too (Spec 9 §5).
    if not (principal.can(Permission.sellers_manage) or principal.can(Permission.catalog_view)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return principal


@router.get("/sellers", response_model=list[SellerOut])
async def list_sellers(
    principal: AdminPrincipal = Depends(_may_list), db: AsyncSession = Depends(get_db)
):
    # A seller sees only itself.
    return await seller_service.list_sellers(
        db,
        only_id=principal.seller_id,
        with_accounts=principal.can(Permission.sellers_manage),
    )


@router.post("/sellers", response_model=SellerOut, status_code=status.HTTP_201_CREATED)
async def create_seller(
    data: SellerCreate,
    principal: AdminPrincipal = Depends(_manage),
    db: AsyncSession = Depends(get_db),
):
    return await seller_service.create_seller(db, data, created_by=principal.telegram_id)


@router.patch("/sellers/{seller_id}", response_model=SellerOut)
async def update_seller(
    seller_id: int,
    data: SellerUpdate,
    _: AdminPrincipal = Depends(_manage),
    db: AsyncSession = Depends(get_db),
):
    return await seller_service.update_seller(db, seller_id, data)
