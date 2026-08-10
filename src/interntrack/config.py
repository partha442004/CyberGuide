"""
Application configuration management using Pydantic Settings.
"""

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from interntrack import __version__


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "InternTrack"
    # Single source of truth: package __version__ (kept in sync with CHANGELOG)
    app_version: str = __version__
    debug: bool = False
    secret_key: str = "change-me-in-production"  # noqa: S105 (dev default)

    # API Server
    api_host: str = "0.0.0.0"  # noqa: S104 # nosec B104 (dev default)
    api_port: int = 8000
    api_key_header: str = "X-API-Key"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/interntrack.db"

    # Redis optional
    redis_url: str | None = None

    # Elasticsearch optional
    elasticsearch_url: str | None = None

    # AI Services
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-pro"

    # Telegram Notifications
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # Discord Notifications
    discord_webhook_url: str | None = None

    # Slack Notifications
    slack_webhook_url: str | None = None

    # SMS Notifications (Twilio)
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None
    # Optional default recipient (the account owner's phone, E.164) used when
    # a message targets the shared/owner channel with no per-user recipient.
    twilio_default_to: str | None = None
    # Twilio WhatsApp sender (e.g. "whatsapp:+14155238886" — the sandbox or a
    # verified business number). Same SID/token as SMS; messages go out with
    # the whatsapp: prefix on both From and To.
    twilio_whatsapp_number: str | None = None

    # Email - Resend (HTTP API; preferred over SMTP when configured)
    resend_api_key: str | None = None
    # Sender for Resend; falls back to ``email_from`` when unset.
    resend_from: str | None = None

    # Email - SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str = "InternTrack <noreply@interntrack.local>"

    # Scraper Settings
    scrape_interval_minutes: int = 30
    max_concurrent_scrapers: int = 5
    request_timeout: int = 30
    user_agent: str = f"InternTrack/{__version__}"

    # CORS
    cors_origins: list[str] = ["*"]
    cors_allow_all: bool = True
    cors_methods: list[str] = ["*"]
    cors_headers: list[str] = ["*"]

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 100
    rate_limit_api_key_per_minute: int = 1000

    # JWT Authentication
    jwt_secret_key: str = "change-me-in-production"  # noqa: S105 (dev default)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # API Usage Quotas (per user)
    api_daily_quota: int = 500
    api_monthly_quota: int = 10000

    @field_validator("cors_origins", "cors_methods", "cors_headers", mode="before")
    @classmethod
    def _parse_csv_lists(cls, value: Any) -> Any:
        """Accept comma-separated env values (e.g. CORS_ORIGINS=https://a,https://b)."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    # Dashboard
    dashboard_port: int = 8501

    @property
    def is_telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def is_discord_configured(self) -> bool:
        return bool(self.discord_webhook_url)

    @property
    def is_slack_configured(self) -> bool:
        return bool(self.slack_webhook_url)

    @property
    def is_email_configured(self) -> bool:
        return bool(self.smtp_user and self.smtp_password)

    @property
    def is_twilio_configured(self) -> bool:
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_phone_number
        )

    @property
    def is_whatsapp_configured(self) -> bool:
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_whatsapp_number
        )

    @property
    def is_resend_configured(self) -> bool:
        return bool(self.resend_api_key)

    @property
    def is_ai_configured(self) -> bool:
        return bool(self.gemini_api_key) or bool(self.ollama_base_url)

    @property
    def is_production(self) -> bool:
        return not self.debug

    def validate_security(self) -> list[str]:
        """Return a list of security configuration warnings."""
        warnings: list[str] = []
        if self.secret_key == "change-me-in-production":  # noqa: S105 (dev default)
            warnings.append(
                "SECRET_KEY is still the default value. Set a strong secret in .env.",
            )
        if self.cors_allow_all and self.cors_origins == ["*"]:
            warnings.append(
                "CORS allows all origins. Restrict CORS_ORIGINS in production.",
            )
        return warnings


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
