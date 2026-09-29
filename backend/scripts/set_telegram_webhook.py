"""Register, inspect or remove the Telegram webhook (couriers' Live Location and /start).

Registering also sets the bot's menu button to open the Mini App at the same origin, so the
@BotFather "Menu Button" step is not needed (skip it with --no-menu-button).

Usage (from backend/):
    python -m scripts.set_telegram_webhook https://shop.example.com   # register
    python -m scripts.set_telegram_webhook --info                     # what Telegram sees
    python -m scripts.set_telegram_webhook --delete                   # stop receiving updates

The argument is the public origin of the site; the API path (/api/webhooks/telegram, where nginx
proxies to the backend) is appended, or override it with --path. Telegram only accepts https://.
Needs TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET in the environment / backend/.env.

A bot has one update consumer: registering a webhook stops getUpdates polling on the same token.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

from app.config import get_settings

DEFAULT_PATH = "/api/webhooks/telegram"
# Only these two kinds of update carry a Live Location; asking for nothing else keeps traffic low.
ALLOWED_UPDATES = ["message", "edited_message"]
TELEGRAM_API = "https://api.telegram.org"


def build_webhook_url(origin: str, path: str = DEFAULT_PATH) -> str:
    origin = origin.strip()
    if not origin.startswith("https://") or origin == "https://":
        raise ValueError("Telegram only delivers webhooks to https:// URLs")
    if not path.startswith("/"):
        raise ValueError("--path must start with /")
    return origin.rstrip("/") + path


def build_set_payload(
    url: str, secret: str, *, max_connections: int | None = None, drop_pending: bool = False
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "url": url,
        "secret_token": secret,
        "allowed_updates": ALLOWED_UPDATES,
    }
    if max_connections is not None:
        payload["max_connections"] = max_connections
    if drop_pending:
        payload["drop_pending_updates"] = True
    return payload


def build_menu_button_payload(origin: str, text: str = "Shop") -> dict[str, Any]:
    return {
        "menu_button": {
            "type": "web_app",
            "text": text,
            "web_app": {"url": origin.strip().rstrip("/") + "/"},
        }
    }


def call_telegram(token: str, method: str, payload: dict[str, Any] | None = None) -> Any:
    """POST to the Bot API. Errors are re-raised without the URL, which contains the token."""
    request = urllib.request.Request(
        f"{TELEGRAM_API}/bot{token}/{method}",
        data=json.dumps(payload or {}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            body = json.load(exc)  # Telegram explains failures in a JSON body
        except ValueError:
            raise RuntimeError(f"Telegram answered HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Telegram: {exc.reason}") from None

    if not body.get("ok"):
        raise RuntimeError(body.get("description") or "Telegram reported a failure")
    return body.get("result")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "origin", nargs="?", help="public site origin, e.g. https://shop.example.com"
    )
    parser.add_argument(
        "--path", default=DEFAULT_PATH, help=f"webhook path (default {DEFAULT_PATH})"
    )
    parser.add_argument("--info", action="store_true", help="show Telegram's view of the webhook")
    parser.add_argument("--delete", action="store_true", help="remove the webhook")
    parser.add_argument("--max-connections", type=int, help="concurrent connections, 1-100")
    parser.add_argument("--drop-pending", action="store_true", help="discard queued updates")
    parser.add_argument(
        "--no-menu-button", action="store_true", help="leave the bot's menu button as it is"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()
    if not settings.telegram_bot_token:
        print("error: TELEGRAM_BOT_TOKEN is not set", file=sys.stderr)
        return 2

    try:
        if args.info:
            info = call_telegram(settings.telegram_bot_token, "getWebhookInfo")
            for key in ("url", "pending_update_count", "last_error_date", "last_error_message"):
                print(f"{key}: {info.get(key)!r}")
        elif args.delete:
            call_telegram(
                settings.telegram_bot_token,
                "deleteWebhook",
                {"drop_pending_updates": args.drop_pending},
            )
            print("Webhook removed.")
        else:
            if not args.origin:
                print(
                    "error: give the public https:// origin, or use --info / --delete",
                    file=sys.stderr,
                )
                return 2
            if not settings.telegram_webhook_secret:
                print("error: TELEGRAM_WEBHOOK_SECRET is not set", file=sys.stderr)
                return 2
            url = build_webhook_url(args.origin, args.path)
            payload = build_set_payload(
                url,
                settings.telegram_webhook_secret,
                max_connections=args.max_connections,
                drop_pending=args.drop_pending,
            )
            call_telegram(settings.telegram_bot_token, "setWebhook", payload)
            print(f"Webhook set to {url}")
            if not args.no_menu_button:
                button = build_menu_button_payload(args.origin)
                call_telegram(settings.telegram_bot_token, "setChatMenuButton", button)
                print(f"Menu button opens {button['menu_button']['web_app']['url']}")
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
