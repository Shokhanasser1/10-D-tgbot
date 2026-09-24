import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize("secret", ["", "abc123", "A-b_C-9", "x" * 256])
def test_valid_webhook_secrets_are_accepted(secret: str) -> None:
    assert Settings(telegram_webhook_secret=secret).telegram_webhook_secret == secret


# Telegram's setWebhook rejects these, and base64 output ("+", "/", "=") is the usual mistake.
@pytest.mark.parametrize("secret", ["abc+def", "abc/def", "abc=", "with space", "é", "x" * 257])
def test_webhook_secret_outside_telegrams_alphabet_fails_at_startup(secret: str) -> None:
    with pytest.raises(ValidationError, match="TELEGRAM_WEBHOOK_SECRET"):
        Settings(telegram_webhook_secret=secret)


def test_bot_username_is_normalised() -> None:
    assert Settings(telegram_bot_username=" @MyShopBot ").telegram_bot_username == "MyShopBot"


@pytest.mark.parametrize("field", ["max_active_deliveries_per_courier", "location_stale_seconds"])
def test_courier_limits_must_be_positive(field: str) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: 0})
