"""Spec 10 §6: a seller sees their paid orders, and nothing about the customer."""

import itertools

from httpx import AsyncClient
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AdminRole, OrderStatus
from app.models.order import Order
from app.models.shipment import Shipment
from tests.admin_factories import add_admin, admin_tma
from tests.courier_factories import add_paid_order
from tests.factories import add_seller

_ids = itertools.count(895_001)


async def _shop(db: AsyncSession, name: str) -> tuple[int, dict[str, str]]:
    seller = await add_seller(db, name)
    telegram_id = next(_ids)
    await add_admin(db, telegram_id, AdminRole.seller, seller_id=seller.id)
    return seller.id, admin_tma(telegram_id)


async def _order(db: AsyncSession, seller_id: int, **kwargs) -> Order:
    order, _ = await add_paid_order(db, customer_id=next(_ids), seller_id=seller_id, **kwargs)
    return order


async def _unpaid(db: AsyncSession, seller_id: int) -> Order:
    order, shipment = await add_paid_order(db, customer_id=next(_ids), seller_id=seller_id)
    await db.execute(delete(Shipment).where(Shipment.id == shipment.id))
    await db.execute(
        update(Order).where(Order.id == order.id).values(status=OrderStatus.pending_payment)
    )
    await db.commit()
    return order


async def test_a_seller_lists_their_paid_orders_newest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    mine, headers = await _shop(db_session, "Lola")
    theirs, _ = await _shop(db_session, "Anor")
    first = await _order(db_session, mine, ready=False)
    second = await _order(db_session, mine, qty=3)
    await _order(db_session, theirs)
    await _unpaid(db_session, mine)

    page = (await client.get("/internal/seller/orders", headers=headers)).json()

    assert [item["id"] for item in page["items"]] == [second.id, first.id]
    assert page["total"] == 2
    newest, oldest = page["items"]
    assert (newest["item_count"], newest["subtotal"], newest["shipment_status"]) == (
        3,
        "30.00",
        "processing",
    )
    assert newest["ready_at"] is not None and oldest["ready_at"] is None


async def test_nothing_about_the_customer_reaches_the_seller(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    mine, headers = await _shop(db_session, "Lola")
    order = await _order(db_session, mine)

    listed = await client.get("/internal/seller/orders", headers=headers)
    detail = await client.get(f"/internal/seller/orders/{order.id}", headers=headers)

    for response in (listed, detail):
        assert response.status_code == 200
        for secret in ("delivery_address", "customer", "telegram_id", "Alexanderplatz", "+49"):
            assert secret not in response.text, secret


async def test_the_order_page_lists_the_items(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    mine, headers = await _shop(db_session, "Lola")
    order = await _order(db_session, mine, qty=2, ready=False)

    detail = (await client.get(f"/internal/seller/orders/{order.id}", headers=headers)).json()

    (item,) = detail["items"]
    assert (item["product_name"], item["qty"], item["unit_price"], item["line_total"]) == (
        "Velvet Lipstick",
        2,
        "10.00",
        "20.00",
    )
    assert item["sku"].startswith("COURIER-V-")
    assert (detail["subtotal"], detail["status"], detail["ready_at"]) == ("20.00", "paid", None)


async def test_another_sellers_or_an_unpaid_order_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    mine, headers = await _shop(db_session, "Lola")
    theirs, _ = await _shop(db_session, "Anor")
    other = await _order(db_session, theirs)
    unpaid = await _unpaid(db_session, mine)

    for order_id in (other.id, unpaid.id):
        response = await client.get(f"/internal/seller/orders/{order_id}", headers=headers)
        assert response.status_code == 404


async def test_platform_staff_use_the_platform_order_views(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    dispatcher = next(_ids)
    await add_admin(db_session, dispatcher, AdminRole.dispatcher)

    response = await client.get("/internal/seller/orders", headers=admin_tma(dispatcher))

    assert response.status_code == 403
