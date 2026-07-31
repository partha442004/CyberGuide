"""
Application configuration management using Pydantic Settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "InternTrack"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key_header: str = "X-API-Key"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/interntrack.db"

    # Redis (Optional)
    redis_url: Optional[str] = None

    # AI Services
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-pro"

    # Telegram Notifications
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # Discord Notifications
    discord_webhook_url: Optional[str] = None

    # Slack Notifications
    slack_webhook_url: Optional[str] = None

    # Email (SMTP)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: str = "InternTrack <noreply@interntrack.local>"

    # Scraper Settings
    scrape_interval_minutes: int = 30
    max_concurrent_scrapers: int = 5
    request_timeout: int = 30
    user_agent: str = "InternTrack/1.0"

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
    def is_ai_configured(self) -> bool:
        return bool(self.gemini_api_key) or bool(self.ollama_base_url)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
