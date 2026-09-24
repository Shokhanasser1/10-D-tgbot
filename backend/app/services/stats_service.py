from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.i18n import translations_for
from app.core.money import quantize
from app.models.enums import OrderStatus, PaymentStatus, ProductStatus, RefundStatus
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.variant import Variant
from app.schemas.stats import LowStockOut, StatsPeriod, SummaryOut, TopProductOut

settings = get_settings()

_PERIOD_DAYS = {"today": 1, "7d": 7, "30d": 30}
_LOW_STOCK_LIMIT = 20
_TOP_LIMIT = 5


def period_start(period: StatsPeriod, now: datetime | None = None) -> datetime:
    """Local midnight in SHOP_TIMEZONE, `days - 1` days back, so every period includes today."""
    zone = ZoneInfo(settings.shop_timezone)
    today = (now or datetime.now(zone)).astimezone(zone).date()
    first_day = today - timedelta(days=_PERIOD_DAYS[period] - 1)
    return datetime.combine(first_day, time.min, tzinfo=zone)


def _sold_orders(start: datetime) -> Select:
    """Ids of orders placed since `start` whose money the shop has and is keeping."""
    return (
        select(Order.id)
        .join(Payment, Payment.order_id == Order.id)
        .where(
            Order.placed_at >= start,
            Payment.status == PaymentStatus.succeeded,
            or_(Payment.refund_status.is_(None), Payment.refund_status == RefundStatus.failed),
        )
    )


async def _names(db: AsyncSession, product_ids: list[int]) -> dict[int, str]:
    texts = await translations_for(
        db, "product", product_ids, ["name"], settings.default_locale, settings.default_locale
    )
    return {pid: name for (pid, _), name in texts.items()}


async def summary(db: AsyncSession, period: StatsPeriod) -> SummaryOut:
    sold = _sold_orders(period_start(period)).subquery()

    revenue, count = (
        await db.execute(
            select(func.coalesce(func.sum(Order.total), 0), func.count(Order.id)).where(
                Order.id.in_(select(sold.c.id))
            )
        )
    ).one()
    revenue = Decimal(revenue)

    status_counts = {status: 0 for status in OrderStatus}
    for status, n in await db.execute(select(Order.status, func.count()).group_by(Order.status)):
        status_counts[status] = n

    top_rows = (
        await db.execute(
            select(
                Variant.product_id,
                func.sum(OrderItem.qty).label("qty"),
                func.sum(OrderItem.qty * OrderItem.unit_price_snapshot).label("revenue"),
            )
            .join(Variant, Variant.id == OrderItem.variant_id)
            .where(OrderItem.order_id.in_(select(sold.c.id)))
            .group_by(Variant.product_id)
            .order_by(func.sum(OrderItem.qty).desc(), Variant.product_id)
            .limit(_TOP_LIMIT)
        )
    ).all()

    low_rows = (
        await db.execute(
            select(Variant.id, Variant.product_id, Variant.sku, Variant.stock_qty, Product.base_sku)
            .join(Product, Product.id == Variant.product_id)
            .where(
                Product.status != ProductStatus.archived,
                Variant.stock_qty <= settings.low_stock_threshold,
            )
            .order_by(Variant.stock_qty, Variant.id)
            .limit(_LOW_STOCK_LIMIT)
        )
    ).all()

    names = await _names(
        db, list({r.product_id for r in top_rows} | {r.product_id for r in low_rows})
    )

    return SummaryOut(
        period=period,
        currency=settings.default_currency,
        revenue=quantize(revenue),
        orders_count=count,
        average_order=quantize(revenue / count) if count else Decimal("0.00"),
        status_counts=status_counts,
        top_products=[
            TopProductOut(
                product_id=r.product_id,
                name=names.get(r.product_id, str(r.product_id)),
                qty=r.qty,
                revenue=quantize(Decimal(r.revenue)),
            )
            for r in top_rows
        ],
        low_stock=[
            LowStockOut(
                variant_id=r.id,
                product_id=r.product_id,
                sku=r.sku,
                name=names.get(r.product_id, r.base_sku),
                stock_qty=r.stock_qty,
            )
            for r in low_rows
        ],
    )
