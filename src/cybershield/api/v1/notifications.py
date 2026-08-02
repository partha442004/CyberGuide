"""
Notifications API Router

Endpoints for notification configuration and testing.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.dependencies import get_session
from cybershield.schemas.notification import (
    NotificationConfig,
    NotificationResponse,
    NotificationTest,
)

DEFAULT_CONFIG = {
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


router = APIRouter()


def _merged_config(config) -> dict:
    """Merge stored JSON preferences over the schema defaults."""
    return {**DEFAULT_CONFIG, **dict(config.config or {})}


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
        # No row yet: return default config
        return DEFAULT_CONFIG

    # The ORM model stores preferences in a JSON column, so merge the stored
    # values over the defaults for a complete response.
    return _merged_config(config)


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
        # Update existing: merge into the JSON config column
        preferences = dict(config.config or {})
        preferences.update(config_data.model_dump(exclude_unset=True))
        config.config = preferences  # type: ignore[assignment]
    else:
        # Create new: the ORM model only has channel/is_enabled/config columns,
        # so store the full preference payload in the JSON config column instead
        # of passing schema-only fields to the constructor.
        preferences = config_data.model_dump()
        config = NotificationConfigModel(
            user_id=user_id,
            channel=preferences.pop("channel", "default"),
            config=preferences,
        )
        session.add(config)

    await session.flush()
    return _merged_config(config)


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
