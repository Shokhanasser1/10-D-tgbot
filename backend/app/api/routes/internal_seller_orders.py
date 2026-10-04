from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminPrincipal, require_permission
from app.db.session import get_db
from app.models.enums import Permission
from app.schemas.payouts import LedgerOut
from app.schemas.seller_orders import SellerOrderOut, SellerOrderPage
from app.services import earnings_service, seller_order_service

router = APIRouter(prefix="/internal/seller", tags=["internal"])

_prepare = require_permission(Permission.orders_prepare)


async def _seller_id(principal: AdminPrincipal = Depends(_prepare)) -> int:
    # Platform staff have the full order views; these are a seller's own, without customers.
    if principal.seller_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only for sellers")
    return principal.seller_id


@router.get("/orders", response_model=SellerOrderPage)
async def list_orders(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    seller_id: int = Depends(_seller_id),
    db: AsyncSession = Depends(get_db),
):
    return await seller_order_service.list_orders(db, seller_id, limit=limit, offset=offset)


@router.get("/orders/{order_id}", response_model=SellerOrderOut)
async def get_order(
    order_id: int, seller_id: int = Depends(_seller_id), db: AsyncSession = Depends(get_db)
):
    return await seller_order_service.get_order(db, seller_id, order_id)


@router.get("/earnings", response_model=LedgerOut)
async def my_earnings(seller_id: int = Depends(_seller_id), db: AsyncSession = Depends(get_db)):
    """The seller's own money (Spec 11): balance, earnings by order, payouts."""
    return await earnings_service.ledger(db, seller_id)
