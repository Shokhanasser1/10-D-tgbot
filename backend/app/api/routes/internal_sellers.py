from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminPrincipal, get_admin_principal, require_permission
from app.db.session import get_db
from app.models.enums import Permission
from app.schemas.payouts import LedgerOut, PayoutCreate, PayoutOut
from app.schemas.seller import SellerCreate, SellerOut, SellerUpdate
from app.services import earnings_service, seller_service

router = APIRouter(prefix="/internal", tags=["internal"])

_manage = require_permission(Permission.sellers_manage)
# Reading money needs no password; recording a payout does (Spec 11, like refunds).
_money_read = require_permission(Permission.payouts_manage, confirm=False)
_money_write = require_permission(Permission.payouts_manage)


async def _may_list(principal: AdminPrincipal = Depends(get_admin_principal)) -> AdminPrincipal:
    # The product editor offers a seller list, so catalog readers may see it too (Spec 9 §5);
    # so do those who pay sellers out (Spec 11).
    if not any(
        principal.can(p)
        for p in (Permission.sellers_manage, Permission.catalog_view, Permission.payouts_manage)
    ):
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
        with_balances=principal.can(Permission.payouts_manage),
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


@router.get("/sellers/{seller_id}/ledger", response_model=LedgerOut)
async def get_ledger(
    seller_id: int,
    _: AdminPrincipal = Depends(_money_read),
    db: AsyncSession = Depends(get_db),
):
    return await earnings_service.ledger(db, seller_id)


@router.post(
    "/sellers/{seller_id}/payouts", response_model=PayoutOut, status_code=status.HTTP_201_CREATED
)
async def record_payout(
    seller_id: int,
    data: PayoutCreate,
    principal: AdminPrincipal = Depends(_money_write),
    db: AsyncSession = Depends(get_db),
):
    """Money sent to the seller by hand; the balance can never go below zero."""
    return await earnings_service.record_payout(db, seller_id, data, principal.telegram_id)
