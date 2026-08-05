"""
Notifications API endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.notification import (
    AlertPreferencesResponse,
    AlertPreferencesUpdate,
    NotificationChannelsResponse,
    NotificationTestRequest,
    NotificationTestResponse,
)
from interntrack.database.session import get_db
from interntrack.scheduler.jobs import _load_alert_preferences
from interntrack.services.notification_service import NotificationManager
from interntrack.services.report_service import ReportService

router = APIRouter()

# Domain keys supported by the alert classifier (matches report_service).
_ALERT_DOMAINS = (
    "security",
    "coding",
    "data",
    "design",
    "finance",
    "marketing",
    "other",
)
# Channels the alert can be delivered through.
_ALERT_CHANNELS = ("email", "telegram", "discord", "slack")


def _normalize_domains(domains: list[str] | None) -> list[str]:
    """Keep only known domain keys (unknown entries are dropped)."""
    if not domains:
        return []
    return [d for d in domains if d in _ALERT_DOMAINS]


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
async def send_test_notification(
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


@router.get("/preferences/{user_id}", response_model=AlertPreferencesResponse)
async def get_alert_preferences(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get saved alert preferences (defaults when nothing is saved)."""
    prefs = await _load_alert_preferences(db, user_id=user_id)
    return AlertPreferencesResponse(
        user_id=user_id,
        domains=prefs.get("domains") or [],
        channels=prefs.get("channels") or [],
        min_match_score=prefs.get("min_match_score"),
        is_enabled=prefs.get("is_enabled", True),
    )


@router.put("/preferences/{user_id}", response_model=AlertPreferencesResponse)
async def update_alert_preferences(
    user_id: str,
    update: AlertPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Create or update alert preferences (upsert by user_id)."""
    from sqlalchemy import select

    from interntrack.domain.models import AlertPreferences as AlertPrefModel

    result = await db.execute(
        select(AlertPrefModel).where(AlertPrefModel.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = AlertPrefModel(user_id=user_id, is_enabled=True)
        db.add(pref)

    if update.domains is not None:
        pref.domains = _normalize_domains(update.domains)  # type: ignore[assignment]
    if update.channels is not None:
        pref.channels = [  # type: ignore[assignment]
            c for c in update.channels if c in _ALERT_CHANNELS
        ]
    if update.min_match_score is not None:
        clamped = max(0, min(100, int(update.min_match_score)))
        pref.min_match_score = clamped  # type: ignore[assignment]
    if update.is_enabled is not None:
        pref.is_enabled = update.is_enabled  # type: ignore[assignment]

    await db.commit()
    await db.refresh(pref)
    return AlertPreferencesResponse(
        user_id=user_id,
        domains=list(pref.domains or []),
        channels=list(pref.channels or []),
        min_match_score=pref.min_match_score,
        is_enabled=bool(pref.is_enabled),
    )


@router.post("/preferences/{user_id}/send-alert")
async def send_alert_now(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Build today's alert filtered by saved preferences and send it now.

    Returns the report summary, per-channel delivery results and how many
    jobs were included, so the dashboard can confirm the alert went out.
    """
    from interntrack.scheduler.jobs import build_daily_report_message

    prefs = await _load_alert_preferences(db, user_id=user_id)
    domains = prefs.get("domains") or None
    service = ReportService(db)
    report = await service.generate_daily_report(
        domains=domains,
        min_match_score=prefs.get("min_match_score"),
    )
    manager = NotificationManager(db)
    message = await build_daily_report_message(report, db, domains=domains)
    channels = prefs.get("channels") or None
    subject = "InternTrack Daily Alert"
    if domains:
        subject += f" ({', '.join(domains)})"
    if channels:
        results = await manager.notify(channels, message, subject=subject)
    else:
        results = await manager.notify_all(message, subject=subject)
    return {
        "summary": report.get("summary") or {},
        "results": results,
        "job_count": len(report.get("new_jobs") or []),
        "domains": domains or [],
        "channels": list(results.keys()),
        "min_match_score": prefs.get("min_match_score"),
    }
