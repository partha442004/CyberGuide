"""
Notification API schemas.
"""

from datetime import datetime
from typing import Dict, List, Optional

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
    last_notified: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NotificationTestRequest(BaseModel):
    """Test notification request."""
    channels: List[str]
    message: str = "Test notification from InternTrack"


class NotificationTestResponse(BaseModel):
    """Test notification response."""
    results: Dict[str, bool]
    configured_channels: List[str]


class NotificationChannelsResponse(BaseModel):
    """Available channels response."""
    channels: List[str]


class NotificationHistoryItem(BaseModel):
    """Notification history item."""
    id: str
    channel: str
    subject: Optional[str] = None
    sent_at: datetime
    success: bool


class NotificationHistoryResponse(BaseModel):
    """Notification history response."""
    history: List[NotificationHistoryItem]
    total: int
