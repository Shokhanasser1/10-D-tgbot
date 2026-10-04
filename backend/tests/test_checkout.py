from dataclasses import dataclass, field
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import to_minor_units
from app.models.category import Category
from app.models.enums import ProductStatus
from app.models.order import Order
from app.models.product import Product
from app.models.variant import Variant
from app.services import stripe_service
from tests.factories import add_seller, default_seller_id, make_init_data

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
        seller_id=await default_seller_id(db_session),
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


async def _checkout_with(
    client: AsyncClient, db_session: AsyncSession, *, telegram_id: int, sku: str, address: dict
):
    variant = await _make_variant(db_session, sku=sku, price="10.00", stock=5)
    headers = _auth_headers(telegram_id)
    await client.post("/cart/items", json={"variant_id": variant.id, "qty": 1}, headers=headers)
    return await client.post("/checkout", json={"delivery_address": address}, headers=headers)


async def test_checkout_stores_the_delivery_pin(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: list[FakePaymentIntent]
) -> None:
    pin = {"latitude": 52.520008, "longitude": 13.404954}

    response = await _checkout_with(
        client, db_session, telegram_id=3010, sku="PIN-1", address={**VALID_ADDRESS, **pin}
    )

    assert response.status_code == 200
    order = await db_session.get(Order, response.json()["order_id"])
    assert order is not None
    assert order.delivery_address["latitude"] == pin["latitude"]
    assert order.delivery_address["longitude"] == pin["longitude"]


async def test_checkout_without_a_pin_still_works_and_stores_none(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: list[FakePaymentIntent]
) -> None:
    response = await _checkout_with(
        client, db_session, telegram_id=3011, sku="PIN-2", address=VALID_ADDRESS
    )

    assert response.status_code == 200
    order = await db_session.get(Order, response.json()["order_id"])
    assert order is not None
    assert order.delivery_address["latitude"] is None
    assert order.delivery_address["longitude"] is None


@pytest.mark.parametrize(
    "pin",
    [
        {"latitude": 52.5},
        {"longitude": 13.4},
        {"latitude": 52.5, "longitude": None},
        {"latitude": None, "longitude": 13.4},
        {"latitude": 91, "longitude": 13.4},
        {"latitude": -91, "longitude": 13.4},
        {"latitude": 52.5, "longitude": 181},
        {"latitude": 52.5, "longitude": -181},
        {"latitude": "52.5", "longitude": "13.4"},  # coordinates are numbers, not text
        {"latitude": True, "longitude": True},  # a bool must not become the point (1, 1)
        {"latitude": [52.5], "longitude": 13.4},
    ],
)
async def test_checkout_rejects_an_invalid_pin(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: list[FakePaymentIntent],
    pin: dict,
) -> None:
    response = await _checkout_with(
        client, db_session, telegram_id=3012, sku="PIN-3", address={**VALID_ADDRESS, **pin}
    )

    assert response.status_code == 422
    assert fake_stripe == []  # nothing was charged for a request we refused


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
async def test_checkout_rejects_non_finite_coordinates_instead_of_failing_in_the_database(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_stripe: list[FakePaymentIntent],
    literal: str,
) -> None:
    variant = await _make_variant(db_session, sku="PIN-4", price="10.00", stock=5)
    headers = _auth_headers(3013)
    await client.post("/cart/items", json={"variant_id": variant.id, "qty": 1}, headers=headers)
    # Python's json (and so a hand-rolled client) may emit these; JSON proper cannot.
    body = (
        '{"delivery_address": {"street": "s", "city": "c", "postal_code": "1", "country": "DE",'
        f' "phone": "1", "latitude": {literal}, "longitude": 13.4}}}}'
    )

    response = await client.post(
        "/checkout", content=body, headers={**headers, "content-type": "application/json"}
    )

    assert response.status_code == 422
    assert fake_stripe == []


async def test_a_rejected_request_reports_where_and_why_but_never_echoes_the_input(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: list[FakePaymentIntent]
) -> None:
    address = {**VALID_ADDRESS, "latitude": 91.5, "longitude": 13.4}

    response = await _checkout_with(
        client, db_session, telegram_id=3014, sku="PIN-5", address=address
    )

    assert response.status_code == 422
    (error,) = response.json()["detail"]
    assert set(error) == {"type", "loc", "msg"}
    assert error["loc"][-1] == "latitude"


async def test_checkout_records_the_cart_seller(
    client: AsyncClient, db_session: AsyncSession, fake_stripe: list[FakePaymentIntent]
) -> None:
    """Spec 10: an order knows its seller, taken from the cart's products."""
    shop = await add_seller(db_session, "Lola Beauty")
    variant = await _make_variant(db_session, sku="SELLER-ORDER", price="10.00", stock=5)
    await db_session.execute(
        update(Product).where(Product.id == variant.product_id).values(seller_id=shop.id)
    )
    await db_session.commit()
    headers = _auth_headers(7_101)
    await client.post("/cart/items", json={"variant_id": variant.id, "qty": 1}, headers=headers)

    response = await client.post(
        "/checkout", json={"delivery_address": VALID_ADDRESS}, headers=headers
    )

    assert response.status_code == 200, response.text
    order = await db_session.get(Order, response.json()["order_id"], populate_existing=True)
    assert order is not None and order.seller_id == shop.id
