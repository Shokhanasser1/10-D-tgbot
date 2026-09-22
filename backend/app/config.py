from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/storefront"
    test_database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/storefront_test"

    telegram_bot_token: str = ""
    telegram_init_data_max_age_seconds: int = 86400

    internal_api_token: str = ""

    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    default_currency: str = "EUR"

    cors_origins: list[str] = ["http://localhost:5173"]

    shipping_flat_rate: str = "4.99"
    free_shipping_threshold: str = "50.00"

    supported_locales: list[str] = ["en", "ru", "uz"]
    default_locale: str = "en"


@lru_cache
def get_settings() -> Settings:
    return Settings()
