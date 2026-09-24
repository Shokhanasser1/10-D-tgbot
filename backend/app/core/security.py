import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from app.core.exceptions import InvalidInitDataError
from app.schemas.telegram import TelegramInitData

_WEB_APP_DATA_KEY = b"WebAppData"


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int) -> TelegramInitData:
    """Validate a Telegram Mini App `initData` payload per Telegram's documented scheme.

    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        raise InvalidInitDataError("Missing init data")

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    data: dict[str, str] = dict(pairs)

    received_hash = data.pop("hash", None)
    if not received_hash:
        raise InvalidInitDataError("Missing hash")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))

    secret_key = hmac.new(_WEB_APP_DATA_KEY, bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InvalidInitDataError("Invalid hash")

    auth_date = int(data.get("auth_date", "0"))
    if auth_date <= 0:
        raise InvalidInitDataError("Missing auth_date")
    if time.time() - auth_date > max_age_seconds:
        raise InvalidInitDataError("Init data expired")

    user_raw = data.get("user")
    if not user_raw:
        raise InvalidInitDataError("Missing user")

    try:
        user_dict = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise InvalidInitDataError("Malformed user payload") from exc

    return TelegramInitData(auth_date=auth_date, query_id=data.get("query_id"), user=user_dict)


def validate_login_widget(fields: dict[str, str], bot_token: str, max_age_seconds: int) -> int:
    """Validate a Telegram Login Widget payload and return the user's telegram_id.

    Differs from initData on purpose: the key is SHA256(bot_token), not an HMAC with
    "WebAppData". https://core.telegram.org/widgets/login#checking-authorization
    """
    data = dict(fields)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise InvalidInitDataError("Missing hash")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash.encode(), received_hash.encode()):
        raise InvalidInitDataError("Invalid hash")

    try:
        auth_date = int(data.get("auth_date", "0"))
        telegram_id = int(data.get("id", "0"))
    except ValueError as exc:
        raise InvalidInitDataError("Malformed login payload") from exc
    if auth_date <= 0 or telegram_id <= 0:
        raise InvalidInitDataError("Malformed login payload")
    if time.time() - auth_date > max_age_seconds:
        raise InvalidInitDataError("Login expired")
    return telegram_id
