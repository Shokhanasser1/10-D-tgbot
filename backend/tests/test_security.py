import time

import pytest

from app.core.exceptions import InvalidInitDataError
from app.core.security import validate_init_data
from tests.factories import TEST_BOT_TOKEN, make_init_data


def test_valid_init_data_is_accepted() -> None:
    raw = make_init_data(telegram_id=42, username="alice")
    result = validate_init_data(raw, TEST_BOT_TOKEN, max_age_seconds=86400)
    assert result.user.id == 42
    assert result.user.username == "alice"


def test_tampered_hash_is_rejected() -> None:
    raw = make_init_data(telegram_id=42, first_name="Test")
    tampered = raw.replace("Test", "Hack", 1)
    with pytest.raises(InvalidInitDataError):
        validate_init_data(tampered, TEST_BOT_TOKEN, max_age_seconds=86400)


def test_wrong_bot_token_is_rejected() -> None:
    raw = make_init_data(telegram_id=42)
    with pytest.raises(InvalidInitDataError):
        validate_init_data(raw, "wrong-bot-token", max_age_seconds=86400)


def test_expired_auth_date_is_rejected() -> None:
    raw = make_init_data(telegram_id=42, auth_date=int(time.time()) - 100_000)
    with pytest.raises(InvalidInitDataError):
        validate_init_data(raw, TEST_BOT_TOKEN, max_age_seconds=86400)


def test_missing_hash_is_rejected() -> None:
    with pytest.raises(InvalidInitDataError):
        validate_init_data("auth_date=123&user=%7B%7D", TEST_BOT_TOKEN, max_age_seconds=86400)


def test_empty_init_data_is_rejected() -> None:
    with pytest.raises(InvalidInitDataError):
        validate_init_data("", TEST_BOT_TOKEN, max_age_seconds=86400)
