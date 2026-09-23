from dataclasses import dataclass, field
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import to_minor_units
from app.models.category import Category
from app.models.enums import ProductStatus
from app.models.product import Product
from app.models.variant import Variant
from app.services import stripe_service
from tests.factories import make_init_data

VALID_ADDRESS = {
    "street": "Alexanderplatz 1",
    "city": "Berlin",
    "postal_code": "10178",
    "country": "DE",
    "phone": "+491234567",
}


def _auth_headers(telegram_id: int) -> dict[str, str]:
    return {"Authorization": f"tma {make_init_data(telegram_id=telegram_id)}"}


@dataclass
class FakePaymentIntent:
    id: str
    amount: int
    currency: str
    metadata: dict[str, str] = field(default_factory=dict)
    client_secret: str = ""

    def __post_init__(self) -> None:
        if not self.client_secret:
            self.client_secret = f"{self.id}_secret_test"


@pytest.fixture
def fake_stripe(monkeypatch: pytest.MonkeyPatch) -> list[FakePaymentIntent]:
    created: list[FakePaymentIntent] = []

    async def _fake_create_payment_intent(amount: Decimal, currency: str, metadata: dict):
        intent = FakePaymentIntent(
            id=f"pi_test_{len(created)}",
            amount=to_minor_units(amount),
            currency=currency,
            metadata=metadata,
        )
        created.append(intent)
        return intent

    monkeypatch.setattr(stripe_service, "create_payment_intent", _fake_create_payment_intent)
    return created


async def _make_variant(db_session: AsyncSession, *, sku: str, price: str, stock: int) -> Variant:
    category = Category(slug=f"cat-{sku}", sort_order=0)
    db_session.add(category)
    await db_session.flush()
    product = Product(
        category_id=category.id,
        base_sku=f"PROD-{sku}",
        base_price=Decimal(price),
        status=ProductStatus.active,
    )
    db_session.add(product)
    await db_session.flush()
    variant = Variant(product_id=product.id, sku=sku, price=Decimal(price), stock_qty=stock)
    db_session.add(variant)
    await db_session.commit()
    await db_session.refresh(variant)
    return variant


async def _place_order(
    client: AsyncClient, db_session: AsyncSession, telegram_id: int, sku_suffix: str
) -> int:
    variant = await _make_variant(db_session, sku=f"ORD-{sku_suffix}", price="10.00", stock=5)
    headers = _auth_headers(telegram_id)
    await client.post("/cart/items", json={"variant_id": variant.id, "qty": 1}, headers=headers)
    response = await client.post(
        "/checkout", json={"delivery_address": VALID_ADDRESS}, headers=headers
    )
    return response.json()["order_id"]


async def test_list_orders_only_returns_current_users_orders(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: list[FakePaymentIntent]
) -> None:
    await _place_order(client, db_session, telegram_id=5001, sku_suffix="A")
    await _place_order(client, db_session, telegram_id=5002, sku_suffix="B")

    response = await client.get("/orders", headers=_auth_headers(5001))
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_get_order_detail_reflects_paid_status_after_webhook(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: list[FakePaymentIntent],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order_id = await _place_order(client, db_session, telegram_id=5003, sku_suffix="C")

    payment_intent_id = fake_stripe[0].id
    event = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": payment_intent_id, "metadata": {"order_id": str(order_id)}}},
    }
    monkeypatch.setattr(stripe_service, "construct_webhook_event", lambda p, s: event)
    await client.post("/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t"})

    response = await client.get(f"/orders/{order_id}", headers=_auth_headers(5003))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "paid"
    assert body["payment_status"] == "succeeded"
    assert body["shipment_status"] == "processing"
    assert len(body["items"]) == 1


async def test_get_order_detail_404s_for_other_users_order(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: list[FakePaymentIntent]
) -> None:
    order_id = await _place_order(client, db_session, telegram_id=5004, sku_suffix="D")

    response = await client.get(f"/orders/{order_id}", headers=_auth_headers(5005))
    assert response.status_code == 404
