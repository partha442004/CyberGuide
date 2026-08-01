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
