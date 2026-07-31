"""
Notifications API Router

Endpoints for notification configuration and testing.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from cybershield.dependencies import get_session
from cybershield.schemas.notification import (
    NotificationConfig,
    NotificationTest,
    NotificationResponse,
)

router = APIRouter()


@router.get("/config/{user_id}", response_model=NotificationConfig)
async def get_notification_config(
    user_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get user's notification configuration."""
    from cybershield.domain.models import NotificationConfig as NotificationConfigModel
    from sqlalchemy import select

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
    from sqlalchemy import select

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
    # TODO: Implement actual notification sending
    return {
        "success": True,
        "message": f"Test notification sent via {test_data.channel}",
        "channel": test_data.channel,
    }


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    notification: dict,
    session: AsyncSession = Depends(get_session),
):
    """Send a notification (internal use)."""
    # TODO: Implement actual notification sending
    return {
        "success": True,
        "message": "Notification sent",
        "channel": notification.get("channel", "unknown"),
    }
