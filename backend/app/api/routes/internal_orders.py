from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AdminPrincipal,
    check_permission,
    get_admin_principal,
    require_permission,
)
from app.db.session import get_db
from app.models.enums import OrderStatus, Permission
from app.schemas.order_admin import (
    OrderAdminDetailOut,
    OrderAdminPage,
    OrderCancelIn,
    OrderReadyOut,
)
from app.services import order_admin_service, order_ready_service

router = APIRouter(prefix="/internal", tags=["internal"])

_view = require_permission(Permission.orders_view)
# Money leaves the shop only after the password was re-entered (Spec 7).
_refunds = require_permission(Permission.refunds_manage)
_prepare = require_permission(Permission.orders_prepare)


@router.get("/orders", response_model=OrderAdminPage)
async def list_orders(
    # Repeat to select several: ?status=paid&status=processing
    order_status: list[OrderStatus] | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=32),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    shortfall: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: AdminPrincipal = Depends(_view),
    db: AsyncSession = Depends(get_db),
):
    return await order_admin_service.list_orders(
        db,
        statuses=order_status,
        q=q,
        date_from=date_from,
        date_to=date_to,
        shortfall=shortfall,
        limit=limit,
        offset=offset,
    )


@router.get("/orders/{order_id}", response_model=OrderAdminDetailOut)
async def get_order(
    order_id: int, _: AdminPrincipal = Depends(_view), db: AsyncSession = Depends(get_db)
):
    return await order_admin_service.get_order(db, order_id)


@router.post("/orders/{order_id}/ready", response_model=OrderReadyOut)
async def mark_ready(
    order_id: int,
    principal: AdminPrincipal = Depends(_prepare),
    db: AsyncSession = Depends(get_db),
):
    """The seller (or the platform) has the order ready: it enters the courier pool (Spec 10)."""
    return await order_ready_service.mark_ready(db, order_id, principal.seller_id)


@router.post("/orders/{order_id}/cancel", response_model=OrderAdminDetailOut)
async def cancel_order(
    order_id: int,
    data: OrderCancelIn,
    principal: AdminPrincipal = Depends(get_admin_principal),
    db: AsyncSession = Depends(get_db),
):
    # Cancelling an order whose money was taken refunds it, so it needs the stronger permission.
    check_permission(
        principal,
        Permission.orders_cancel_paid
        if await order_admin_service.money_taken(db, order_id)
        else Permission.orders_cancel_unpaid,
    )
    return await order_admin_service.cancel_order(
        db, order_id, data.reason.strip(), principal.telegram_id
    )


@router.post("/orders/{order_id}/refund", response_model=OrderAdminDetailOut)
async def retry_refund(
    order_id: int, _: AdminPrincipal = Depends(_refunds), db: AsyncSession = Depends(get_db)
):
    return await order_admin_service.retry_refund(db, order_id)


@router.post("/orders/{order_id}/refund/confirm", response_model=OrderAdminDetailOut)
async def confirm_manual_refund(
    order_id: int, _: AdminPrincipal = Depends(_refunds), db: AsyncSession = Depends(get_db)
):
    """An owner refunded a Click/Payme payment in the provider's cabinet (Spec 6 §5)."""
    return await order_admin_service.confirm_manual_refund(db, order_id)
