"""
Notification API schemas.
"""

from datetime import datetime

from pydantic import BaseModel


class NotificationConfig(BaseModel):
    """Notification channel configuration."""

    channel: str
    is_enabled: bool = True
    config: dict = {}


class NotificationConfigResponse(BaseModel):
    """Notification configuration response."""

    id: str
    channel: str
    is_enabled: bool
    config: dict
    last_notified: datetime | None = None

    model_config = {"from_attributes": True}


class NotificationTestRequest(BaseModel):
    """Test notification request."""

    channels: list[str]
    message: str = "Test notification from InternTrack"


class InstantAlertTestRequest(BaseModel):
    """Request to send a sample instant-alert Telegram ping."""

    user_id: str
    chat_id: str | None = None


class NotificationTestResponse(BaseModel):
    """Test notification response."""

    results: dict[str, bool]
    configured_channels: list[str]


class NotificationChannelsResponse(BaseModel):
    """Available channels response."""

    channels: list[str]


class NotificationHistoryItem(BaseModel):
    """Notification history item."""

    id: str
    channel: str
    subject: str | None = None
    sent_at: datetime
    success: bool


class NotificationHistoryResponse(BaseModel):
    """Notification history response."""

    history: list[NotificationHistoryItem]
    total: int


class AlertPreferencesResponse(BaseModel):
    """Saved daily-alert preferences."""

    user_id: str
    domains: list[str] = []
    channels: list[str] = []
    min_match_score: int | None = None
    is_enabled: bool = True
    last_alert_at: datetime | None = None
    slot_domains: dict | None = None
    weekly_enabled: bool = True
    instant_alerts: bool = True
    # Whether remote / WFH / "anywhere" listings count as matching the
    # user's preferred location (see AlertPreferences.include_remote).
    include_remote: bool = True
    # Whether the compact "📭 No new jobs today" email is sent on days when
    # the digest found nothing new (off = only real job-alert emails).
    quiet_day_emails: bool = True
    # Vacation mode: when set (naive UTC), all alerts are suppressed until
    # this timestamp. ``None`` means alerts are live.
    paused_until: datetime | None = None
    # Annual minimum salary (₹/year, INR): jobs at/above this get a
    # "💰 Meets your target" marker in the digest. ``None`` = no target.
    min_salary: int | None = None
    # Highlight keywords: matching jobs get a "🎯 matches …" marker.
    keywords: list[str] = []

    model_config = {"from_attributes": True}


class AlertPreferencesUpdate(BaseModel):
    """Update payload for alert preferences (None = keep current value)."""

    domains: list[str] | None = None
    channels: list[str] | None = None
    min_match_score: int | None = None
    is_enabled: bool | None = None
    slot_domains: dict | None = None
    weekly_enabled: bool | None = None
    instant_alerts: bool | None = None
    include_remote: bool | None = None
    quiet_day_emails: bool | None = None
    # Vacation mode timestamp (naive UTC) — set to a future time to pause
    # all alerts until then.
    paused_until: datetime | None = None
    # Annual minimum salary (₹/year, INR). ``None`` = keep current value.
    min_salary: int | None = None
    # Highlight keywords (lowercased, deduped, capped at 10).
    keywords: list[str] | None = None
    # Set True to clear the pause immediately (kept separate from
    # ``paused_until`` because the update schema uses None = keep current).
    resume_alerts: bool | None = None
