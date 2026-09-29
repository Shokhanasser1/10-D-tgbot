import re
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
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
    # Public https:// address of the Mini App; the bot's /start reply opens it with a button.
    webapp_url: str = ""

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

    # Admin panel. Comma-separated telegram IDs that get an owner account on startup.
    admin_bootstrap_telegram_ids: str = ""
    # Signs the browser session cookie. Required outside development.
    admin_session_secret: str = ""
    admin_session_max_age_seconds: int = Field(default=12 * 3600, ge=60)
    # How old a Telegram Login Widget payload may be when exchanged for a session.
    telegram_login_max_age_seconds: int = Field(default=86400, ge=60)
    # Off only for local http development; browsers drop Secure cookies on plain http elsewhere.
    admin_cookie_secure: bool = True
    admin_login_rate_limit_per_minute: int = Field(default=10, ge=1)

    media_root: str = "/data/media"
    shop_timezone: str = "UTC"
    low_stock_threshold: int = Field(default=5, ge=0)

    # Stock reservation: how long checkout holds stock for an unpaid order, and how often the
    # background sweeper expires overdue ones (0 turns the sweeper off in this process).
    reservation_ttl_minutes: int = Field(default=15, ge=1)
    reservation_sweep_seconds: int = Field(default=60, ge=0)

    # Telegram notifications (Spec 5): how often the sender delivers queued messages
    # (0 turns the sender off in this process; it also stays off without a bot token).
    notification_send_seconds: float = Field(default=2, ge=0)

    @field_validator("telegram_webhook_secret")
    @classmethod
    def _validate_webhook_secret(cls, value: str) -> str:
        if value and not WEBHOOK_SECRET_PATTERN.fullmatch(value):
            raise ValueError(
                "TELEGRAM_WEBHOOK_SECRET must be 1-256 characters of A-Z a-z 0-9 _ - "
                "(Telegram rejects anything else); generate one with "
                'python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return value

    @field_validator("shop_timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"SHOP_TIMEZONE {value!r} is not a known IANA time zone") from exc
        return value

    @field_validator("admin_bootstrap_telegram_ids")
    @classmethod
    def _validate_bootstrap_ids(cls, value: str) -> str:
        for part in value.split(","):
            if part.strip() and not part.strip().isdigit():
                raise ValueError("ADMIN_BOOTSTRAP_TELEGRAM_IDS must be comma-separated numbers")
        return value

    @model_validator(mode="after")
    def _require_session_secret_outside_development(self) -> "Settings":
        if self.env != "development" and not self.admin_session_secret:
            raise ValueError(
                "ADMIN_SESSION_SECRET is required when ENV is not development; generate one with "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return self

    @property
    def admin_bootstrap_ids(self) -> list[int]:
        return [int(p) for p in self.admin_bootstrap_telegram_ids.split(",") if p.strip()]

    @field_validator("telegram_bot_username")
    @classmethod
    def _strip_leading_at(cls, value: str) -> str:
        return value.strip().removeprefix("@")


@lru_cache
def get_settings() -> Settings:
    return Settings()
