"""The bot's own replies: a greeting with an "Open shop" button when someone sends /start.

The reply goes back as the body of the webhook response (Telegram executes a Bot API method
returned there), so no outgoing request and no bot token are involved.
"""

from typing import Any

from app.schemas.telegram_update import TelegramUpdate

_GREETING = {
    "en": (
        "Welcome! Tap the button below to open the shop.",
        "Open shop",
    ),
    "ru": (
        "Добро пожаловать! Нажмите кнопку ниже, чтобы открыть магазин.",
        "Открыть магазин",
    ),
    "uz": (
        "Xush kelibsiz! Do'konni ochish uchun quyidagi tugmani bosing.",
        "Do'konni ochish",
    ),
}


def _is_start(text: str | None) -> bool:
    if not text:
        return False
    command = text.split(maxsplit=1)[0]
    # In groups a command may carry the bot's name: /start@shop_bot.
    return command.split("@", 1)[0] == "/start"


def start_reply(update: TelegramUpdate, webapp_url: str) -> dict[str, Any] | None:
    """The sendMessage call answering /start in a private chat, or None for any other update."""
    message = update.message
    if message is None or message.chat is None or message.chat.type != "private":
        return None
    if message.sender is None or message.sender.is_bot or not _is_start(message.text):
        return None

    language = (message.sender.language_code or "en").split("-", 1)[0]
    text, button = _GREETING.get(language, _GREETING["en"])
    reply: dict[str, Any] = {"method": "sendMessage", "chat_id": message.chat.id, "text": text}
    # Telegram only opens Mini Apps from https:// URLs.
    if webapp_url.startswith("https://"):
        reply["reply_markup"] = {
            "inline_keyboard": [[{"text": button, "web_app": {"url": webapp_url}}]]
        }
    return reply
