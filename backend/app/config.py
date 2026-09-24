import re
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Telegram's setWebhook accepts a secret_token of 1-256 chars from this alphabet only.
WEBHOOK_SECRET_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,256}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/storefront"
    test_database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/storefront_test"

    telegram_bot_token: str = ""
    telegram_init_data_max_age_seconds: int = 86400
    # Empty disables POST /webhooks/telegram (it answers 404).
    telegram_webhook_secret: str = ""
    telegram_bot_username: str = ""

    internal_api_token: str = ""

    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    default_currency: str = "EUR"

    cors_origins: list[str] = ["http://localhost:5173"]

    shipping_flat_rate: str = "4.99"
    free_shipping_threshold: str = "50.00"

    max_active_deliveries_per_courier: int = Field(default=3, ge=1)
    location_stale_seconds: int = Field(default=120, ge=1)

    supported_locales: list[str] = ["en", "ru", "uz"]
    default_locale: str = "en"

    @field_validator("telegram_webhook_secret")
    @classmethod
    def _validate_webhook_secret(cls, value: str) -> str:
        if value and not WEBHOOK_SECRET_PATTERN.fullmatch(value):
            raise ValueError(
                "TELEGRAM_WEBHOOK_SECRET must be 1-256 characters of A-Z a-z 0-9 _ - "
                "(Telegram rejects anything else); generate one with "
                "python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return value

    @field_validator("telegram_bot_username")
    @classmethod
    def _strip_leading_at(cls, value: str) -> str:
        return value.strip().removeprefix("@")


@lru_cache
def get_settings() -> Settings:
    return Settings()
