from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DISPATCH_ROLES, AdminPrincipal, require_admin
from app.db.session import get_db
from app.models.enums import OrderStatus
from app.schemas.order_admin import OrderAdminDetailOut, OrderAdminPage, OrderCancelIn
from app.services import order_admin_service

router = APIRouter(prefix="/internal", tags=["internal"])

_dispatch = require_admin(*DISPATCH_ROLES)


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
    _: AdminPrincipal = Depends(_dispatch),
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
    order_id: int, _: AdminPrincipal = Depends(_dispatch), db: AsyncSession = Depends(get_db)
):
    return await order_admin_service.get_order(db, order_id)


@router.post("/orders/{order_id}/cancel", response_model=OrderAdminDetailOut)
async def cancel_order(
    order_id: int,
    data: OrderCancelIn,
    principal: AdminPrincipal = Depends(_dispatch),
    db: AsyncSession = Depends(get_db),
):
    return await order_admin_service.cancel_order(
        db, order_id, data.reason.strip(), principal.telegram_id
    )


@router.post("/orders/{order_id}/refund", response_model=OrderAdminDetailOut)
async def retry_refund(
    order_id: int, _: AdminPrincipal = Depends(_dispatch), db: AsyncSession = Depends(get_db)
):
    return await order_admin_service.retry_refund(db, order_id)
