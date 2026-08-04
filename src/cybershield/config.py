"""
Application configuration management using Pydantic Settings.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cybershield import __version__

# Resolve project root (2 levels up from src/cybershield/config.py)
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "CyberGuide"
    # Single source of truth: package __version__ (kept in sync with CHANGELOG)
    app_version: str = __version__
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # API Server
    api_host: str = "0.0.0.0"  # nosec B104 (dev default, env-overridable)
    api_port: int = 8000
    api_key_header: str = "X-API-Key"

    # Database — falls back to the shared DATABASE_URL env var so the
    # cybershield resume endpoints work when mounted on the Vercel app.
    database_url: str = "sqlite+aiosqlite:///./data/cybershield.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def resolve_database_url(cls, v: str) -> str:
        """Allow the parent app's DATABASE_URL to override the default."""
        if v == "sqlite+aiosqlite:///./data/cybershield.db":
            shared = os.environ.get("DATABASE_URL")
            if shared:
                return shared
        return v

    # Redis (Optional)
    redis_url: Optional[str] = None

    # Elasticsearch (Optional)
    elasticsearch_url: str = "http://localhost:9200"

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
    email_from: str = "CyberGuide <noreply@cybershield.dev>"

    # Scraper Settings
    scrape_interval_minutes: int = 30
    max_concurrent_scrapers: int = 5
    request_timeout: int = 30
    user_agent: str = f"CyberGuide/{__version__} (+https://github.com/partha442004/CyberGuide)"

    # Dashboard
    dashboard_port: int = 8501

    # Security
    scam_score_threshold: int = 70
    dedup_similarity_threshold: float = 0.85

    # Rate Limiting
    rate_limit_per_minute: int = 100
    rate_limit_api_key_per_minute: int = 1000

    # API Authentication
    api_keys: Optional[list[str]] = None  # Set via API_KEYS env var as comma-separated string
    require_api_key: bool = False

    @field_validator("api_keys", mode="before")
    @classmethod
    def parse_api_keys(cls, v):
        """Parse comma-separated API keys from env var string."""
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return v

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
