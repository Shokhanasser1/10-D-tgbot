from decimal import Decimal

from app.core.pricing import calculate_shipping_cost


def test_shipping_cost_applies_flat_rate_below_threshold() -> None:
    assert calculate_shipping_cost(Decimal("10.00")) == Decimal("4.99")


def test_shipping_cost_is_free_at_or_above_threshold() -> None:
    assert calculate_shipping_cost(Decimal("50.00")) == Decimal("0.00")
    assert calculate_shipping_cost(Decimal("100.00")) == Decimal("0.00")


def test_shipping_cost_just_below_threshold() -> None:
    assert calculate_shipping_cost(Decimal("49.99")) == Decimal("4.99")
