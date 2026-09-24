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


def test_session_secret_is_required_outside_development() -> None:
    with pytest.raises(ValidationError, match="ADMIN_SESSION_SECRET"):
        Settings(env="production", admin_session_secret="")
    assert Settings(env="production", admin_session_secret="s").admin_session_secret == "s"
    assert Settings(env="development", admin_session_secret="").admin_session_secret == ""


def test_bootstrap_ids_are_parsed() -> None:
    assert Settings(admin_bootstrap_telegram_ids=" 1, 22 ,,").admin_bootstrap_ids == [1, 22]
    assert Settings(admin_bootstrap_telegram_ids="").admin_bootstrap_ids == []


def test_bootstrap_ids_must_be_numbers() -> None:
    with pytest.raises(ValidationError, match="ADMIN_BOOTSTRAP_TELEGRAM_IDS"):
        Settings(admin_bootstrap_telegram_ids="1,@owner")


def test_shop_timezone_must_be_known() -> None:
    assert Settings(shop_timezone="Asia/Tashkent").shop_timezone == "Asia/Tashkent"
    with pytest.raises(ValidationError, match="SHOP_TIMEZONE"):
        Settings(shop_timezone="Mars/Olympus")
