import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

TEST_BOT_TOKEN = "123456:TEST-bot-token-for-unit-tests"


def make_init_data(
    telegram_id: int = 111222333,
    username: str = "testuser",
    first_name: str = "Test",
    language_code: str = "en",
    bot_token: str = TEST_BOT_TOKEN,
    auth_date: int | None = None,
) -> str:
    """Build a validly-signed Telegram initData query string for tests."""
    user = {
        "id": telegram_id,
        "username": username,
        "first_name": first_name,
        "language_code": language_code,
    }
    data = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAtestqueryid",
        "user": json.dumps(user, separators=(",", ":")),
    }

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    data["hash"] = computed_hash
    return urlencode(data)
