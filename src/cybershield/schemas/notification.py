"""
Notification Schemas

Pydantic models for notification configuration and testing.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NotificationConfig(BaseModel):
    """Schema for user notification configuration."""
    telegram_enabled: bool = False
    telegram_chat_id: Optional[str] = None
    email_enabled: bool = True
    email_address: Optional[str] = None
    discord_enabled: bool = False
    discord_webhook_url: Optional[str] = None
    slack_enabled: bool = False
    slack_webhook_url: Optional[str] = None
    push_enabled: bool = False
    push_token: Optional[str] = None
    instant_alerts: bool = True
    daily_digest: bool = True
    weekly_report: bool = True
    monthly_report: bool = True
    deadline_reminders: bool = True
    reminder_hours_before: int = 24
    scam_alerts: bool = True
    watchlist_alerts: bool = True


class NotificationTest(BaseModel):
    """Schema for testing notification channels."""
    channel: str = Field(..., pattern="^(telegram|email|discord|slack|push)$")
    message: Optional[str] = "This is a test notification from CyberGuide."


class NotificationResponse(BaseModel):
    """Schema for notification send response."""
    success: bool
    message: str
    channel: str
    sent_at: Optional[datetime] = None


class NotificationHistory(BaseModel):
    """Schema for notification history."""
    id: str
    channel: str
    notification_type: str
    subject: Optional[str] = None
    sent_at: Optional[datetime] = None
    status: str  # "sent", "failed", "pending"
