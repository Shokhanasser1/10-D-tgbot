from app.config import get_settings
from app.models.telegram_user import TelegramUser

settings = get_settings()


def resolve_locale(locale: str | None, user: TelegramUser) -> str:
    if locale and locale in settings.supported_locales:
        return locale
    return user.locale
