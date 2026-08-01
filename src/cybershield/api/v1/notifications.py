"""
Notifications API Router

Endpoints for notification configuration and testing.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.dependencies import get_notification_orchestrator, get_session
from cybershield.notifications.base import (
    NotificationMessage,
    NotificationPriority,
    NotificationType,
)
from cybershield.schemas.notification import (
    NotificationConfig,
    NotificationResponse,
    NotificationSendRequest,
    NotificationTest,
)

router = APIRouter()


@router.get("/config/{user_id}", response_model=NotificationConfig)
async def get_notification_config(
    user_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get user's notification configuration."""
    from cybershield.domain.models import NotificationConfig as NotificationConfigModel

    result = await session.execute(
        select(NotificationConfigModel).where(NotificationConfigModel.user_id == user_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        # Return default config
        return {
            "telegram_enabled": False,
            "email_enabled": True,
            "discord_enabled": False,
            "slack_enabled": False,
            "push_enabled": False,
            "instant_alerts": True,
            "daily_digest": True,
            "weekly_report": True,
            "monthly_report": True,
        }

    return config


@router.put("/config/{user_id}", response_model=NotificationConfig)
async def update_notification_config(
    user_id: str,
    config_data: NotificationConfig,
    session: AsyncSession = Depends(get_session),
):
    """Update user's notification configuration."""
    from cybershield.domain.models import NotificationConfig as NotificationConfigModel

    result = await session.execute(
        select(NotificationConfigModel).where(NotificationConfigModel.user_id == user_id)
    )
    config = result.scalar_one_or_none()

    if config:
        # Update existing
        for key, value in config_data.model_dump(exclude_unset=True).items():
            setattr(config, key, value)
    else:
        # Create new
        config = NotificationConfigModel(
            user_id=user_id,
            **config_data.model_dump(),
        )
        session.add(config)

    await session.flush()
    return config


@router.post("/test", response_model=NotificationResponse)
async def test_notification(
    test_data: NotificationTest,
    session: AsyncSession = Depends(get_session),
):
    """Send a test notification."""
    orchestrator = get_notification_orchestrator()
    channel = orchestrator.get_channel(test_data.channel)

    if not channel:
        raise HTTPException(
            status_code=400,
            detail=f"Notification channel '{test_data.channel}' is not configured",
        )

    message = NotificationMessage(
        title="🧪 Test Notification",
        content=test_data.message or "This is a test notification from CyberGuide.",
        notification_type=NotificationType.INSTANT_ALERT,
        priority=NotificationPriority.LOW,
    )

    success = await orchestrator.send_to_channel(test_data.channel, message)

    return {
        "success": success,
        "message": f"Test notification sent via {test_data.channel}" if success else f"Failed to send via {test_data.channel}",
        "channel": test_data.channel,
        "sent_at": datetime.now(timezone.utc) if success else None,
    }


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    notification: NotificationSendRequest,
    session: AsyncSession = Depends(get_session),
):
    """Send a notification (internal use)."""
    orchestrator = get_notification_orchestrator()
    channel_name = notification.channel

    # Map priority string to enum
    priority_map = {
        "low": NotificationPriority.LOW,
        "normal": NotificationPriority.NORMAL,
        "high": NotificationPriority.HIGH,
        "urgent": NotificationPriority.URGENT,
    }
    priority = priority_map.get(notification.priority or "normal", NotificationPriority.NORMAL)

    message = NotificationMessage(
        title=notification.title,
        content=notification.content,
        notification_type=NotificationType.INSTANT_ALERT,
        priority=priority,
        data=notification.data,
        url=notification.url,
    )

    # If a specific channel is requested, send to it; otherwise send to all
    if channel_name != "unknown":
        success = await orchestrator.send_to_channel(channel_name, message)
    else:
        results = await orchestrator.send_to_all(message)
        success = any(results.values()) if results else False

    return {
        "success": success,
        "message": "Notification sent" if success else "Failed to send notification",
        "channel": channel_name,
        "sent_at": datetime.now(timezone.utc) if success else None,
    }
