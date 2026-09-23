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


async def test_checkout_creates_order_with_correct_totals(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: list[FakePaymentIntent]
) -> None:
    variant = await _make_variant(db_session, sku="CHK-1", price="10.00", stock=5)
    headers = _auth_headers(3001)

    await client.post("/cart/items", json={"variant_id": variant.id, "qty": 2}, headers=headers)
    response = await client.post(
        "/checkout", json={"delivery_address": VALID_ADDRESS}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == "24.99"
    assert body["currency"] == "EUR"
    assert body["client_secret"] == "pi_test_0_secret_test"
    assert len(fake_stripe) == 1
    assert fake_stripe[0].metadata["order_id"] == str(body["order_id"])


async def test_checkout_is_free_shipping_above_threshold(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: list[FakePaymentIntent]
) -> None:
    variant = await _make_variant(db_session, sku="CHK-2", price="60.00", stock=5)
    headers = _auth_headers(3002)

    await client.post("/cart/items", json={"variant_id": variant.id, "qty": 1}, headers=headers)
    response = await client.post(
        "/checkout", json={"delivery_address": VALID_ADDRESS}, headers=headers
    )

    assert response.json()["total"] == "60.00"


async def test_checkout_with_empty_cart_returns_400(
    client: AsyncClient, fake_stripe: list[FakePaymentIntent]
) -> None:
    response = await client.post(
        "/checkout", json={"delivery_address": VALID_ADDRESS}, headers=_auth_headers(3003)
    )
    assert response.status_code == 400


async def test_checkout_stock_conflict_returns_409(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: list[FakePaymentIntent]
) -> None:
    variant = await _make_variant(db_session, sku="CHK-3", price="10.00", stock=2)
    headers = _auth_headers(3004)

    await client.post("/cart/items", json={"variant_id": variant.id, "qty": 2}, headers=headers)

    # Stock drops below what's already in the cart (e.g. sold out elsewhere) before checkout.
    variant.stock_qty = 1
    db_session.add(variant)
    await db_session.commit()

    response = await client.post(
        "/checkout", json={"delivery_address": VALID_ADDRESS}, headers=headers
    )
    assert response.status_code == 409
