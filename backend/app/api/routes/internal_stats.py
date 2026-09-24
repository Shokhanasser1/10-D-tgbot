from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.enums import AdminRole
from app.schemas.stats import StatsPeriod, SummaryOut
from app.services import stats_service

# Revenue is the owner's business alone.
router = APIRouter(
    prefix="/internal", tags=["internal"], dependencies=[Depends(require_admin(AdminRole.owner))]
)


@router.get("/stats/summary", response_model=SummaryOut)
async def summary(period: StatsPeriod = Query(default="today"), db: AsyncSession = Depends(get_db)):
    return await stats_service.summary(db, period)
