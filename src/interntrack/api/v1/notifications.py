"""
Notifications API endpoints.
"""


from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.notification import (
    NotificationChannelsResponse,
    NotificationTestRequest,
    NotificationTestResponse,
)
from interntrack.database.session import get_db
from interntrack.services.notification_service import NotificationManager

router = APIRouter()


@router.get("/channels", response_model=NotificationChannelsResponse)
async def get_channels():
    """Get configured notification channels."""
    from interntrack.config import get_settings

    settings = get_settings()
    channels = []
    if settings.is_telegram_configured:
        channels.append("telegram")
    if settings.is_email_configured:
        channels.append("email")
    if settings.is_discord_configured:
        channels.append("discord")
    if settings.is_slack_configured:
        channels.append("slack")

    return NotificationChannelsResponse(channels=channels)


@router.post("/test", response_model=NotificationTestResponse)
async def test_notification(
    test_request: NotificationTestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Test notification channels."""
    manager = NotificationManager(db)
    results = await manager.notify(
        channels=test_request.channels,
        message=test_request.message,
        subject="Test Notification",
    )
    return NotificationTestResponse(
        results=results,
        configured_channels=manager.get_configured_channels(),
    )


@router.post("/send")
async def send_notification(
    channels: list[str],
    message: str,
    subject: str = "InternTrack Notification",
    db: AsyncSession = Depends(get_db),
):
    """Send notification to specified channels."""
    manager = NotificationManager(db)
    results = await manager.notify(channels, message, subject)
    return {"results": results}
