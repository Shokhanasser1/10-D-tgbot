"""Print a validly signed Telegram initData string for developing outside Telegram.

Usage (from backend/):  python -m scripts.make_dev_init_data [telegram_id] [language_code]

Paste the output into frontend/.env as VITE_DEV_MOCK_INIT_DATA. It is signed with
TELEGRAM_BOT_TOKEN from backend/.env, so the backend accepts it, and it expires after
TELEGRAM_INIT_DATA_MAX_AGE_SECONDS (24h by default) — rerun when it does. The frontend only
reads it in `npm run dev`; production builds ignore it.
"""

import hashlib
import hmac
import json
import sys
import time
from urllib.parse import urlencode

from app.config import get_settings


def make_init_data(bot_token: str, telegram_id: int, language_code: str) -> str:
    user = {
        "id": telegram_id,
        "username": "devtester",
        "first_name": "Dev",
        "language_code": language_code,
    }
    data = {
        "auth_date": str(int(time.time())),
        "query_id": "AAdevquery",
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def main() -> None:
    bot_token = get_settings().telegram_bot_token
    if not bot_token:
        sys.exit("TELEGRAM_BOT_TOKEN is empty — set it in backend/.env first.")

    telegram_id = int(sys.argv[1]) if len(sys.argv) > 1 else 999000111
    language_code = sys.argv[2] if len(sys.argv) > 2 else "en"
    print(make_init_data(bot_token, telegram_id, language_code))


if __name__ == "__main__":
    main()
