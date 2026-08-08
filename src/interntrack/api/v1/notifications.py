"""
Notifications API endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.notification import (
    AlertPreferencesResponse,
    AlertPreferencesUpdate,
    InstantAlertTestRequest,
    NotificationChannelsResponse,
    NotificationTestRequest,
    NotificationTestResponse,
)
from interntrack.database.session import get_db
from interntrack.scheduler.jobs import (
    ALERT_SLOTS as _ALERT_SLOTS,
)
from interntrack.scheduler.jobs import (
    _load_alert_preferences,
    _mark_alert_sent,
    _record_alert_history,
)
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


@router.get("/telegram/chat-id")
async def discover_telegram_chat_id():
    """Discover the chat ID of the person who last messaged the bot.

    Calls Telegram's ``getUpdates`` with the configured bot token and returns
    the newest chat that messaged the bot, so a user can find their own chat
    ID by sending the bot any message (e.g. ``/start``) first. Returns a
    helpful hint when no update is available yet or Telegram is unreachable
    — never raises.
    """
    from interntrack.config import get_settings

    settings = get_settings()
    if not settings.telegram_bot_token:
        return {
            "chat_id": None,
            "hint": "No TELEGRAM_BOT_TOKEN configured on the API.",
        }
    try:
        import httpx

        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
        data = response.json()
        if not data.get("ok"):
            return {
                "chat_id": None,
                "hint": f"Telegram error: {data.get('description', 'unknown')}.",
            }
        # Newest update first; the chat id can sit under several update kinds.
        for update in reversed(data.get("result") or []):
            for key in ("message", "edited_message", "channel_post", "my_chat_member"):
                chat_id = ((update.get(key) or {}).get("chat") or {}).get("id")
                if chat_id:
                    return {
                        "chat_id": str(chat_id),
                        "hint": "Found the chat that last messaged the bot.",
                    }
        return {
            "chat_id": None,
            "hint": "No messages yet — send the bot any message (e.g. /start) "
            "and try again. Make sure *you* are the last person to message "
            "it, otherwise you may get a teammate's chat ID.",
        }
    except Exception as e:  # pragma: no cover - network path
        return {
            "chat_id": None,
            "hint": f"Could not reach Telegram: {e}",
        }


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


@router.post("/instant-alert/test")
async def send_test_instant_alert(
    payload: InstantAlertTestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a sample instant-alert Telegram ping to a user's chat.

    Mirrors what a real high-match discovery sends (one compact message with
    an Apply button) so users can verify their instant-alert path end-to-end
    from the dashboard — no waiting for a real discovery hit. The chat ID is
    taken from the request when provided, otherwise from the user's profile.
    Never raises: returns a ``results``/``hint`` dict in every case.
    """
    from interntrack.scheduler.jobs import _user_profile

    chat_id = (payload.chat_id or "").strip() or None
    if not chat_id:
        user = await _user_profile(db, payload.user_id)
        if user is not None:
            chat_id = (getattr(user, "telegram_chat_id", None) or "").strip() or None
    if not chat_id:
        return {
            "sent": False,
            "chat_id": None,
            "hint": "No Telegram chat ID for this account. Use the "
            "'Find my Telegram chat ID' helper or paste your chat ID in "
            "My Account, then try again.",
        }
    try:
        message = (
            "⚡ <b>This is a test of your instant alerts!</b> "
            "(1 job just discovered)\n"
            "When a new job matches your categories, location and match "
            "threshold, you'll get a message exactly like this one — "
            "instantly, no waiting for the daily slots.\n"
            "🔹 <b>Sample: SOC Analyst</b> @ Example Cyber Corp · "
            "Bangalore · 85% match\n"
        )
        manager = NotificationManager(db)
        results = await manager.notify(
            ["telegram"],
            message,
            subject="⚡ Test instant alert",
            buttons=[("✅ Apply — Sample job", "https://example.com/sample-job")],
            recipient={"telegram_chat_id": chat_id},
        )
        sent = bool(results.get("telegram"))
        return {
            "sent": sent,
            "chat_id": chat_id,
            "results": results,
            "hint": None
            if sent
            else "Telegram delivery failed — check the "
            "bot token and that you messaged the bot first.",
        }
    except Exception as e:  # pragma: no cover - network path
        return {
            "sent": False,
            "chat_id": chat_id,
            "hint": f"Could not send: {e}",
        }


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
        last_alert_at=prefs.get("last_alert_at"),
        slot_domains=prefs.get("slot_domains") or {},
        weekly_enabled=prefs.get("weekly_enabled", True),
        instant_alerts=prefs.get("instant_alerts", True),
        paused_until=prefs.get("paused_until"),
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
    if update.slot_domains is not None:
        cleaned = {}
        for slot_key, slot_domains in update.slot_domains.items():
            if slot_key in _ALERT_SLOTS:
                cleaned[slot_key] = _normalize_domains(slot_domains)
        pref.slot_domains = cleaned  # type: ignore[assignment]
    if update.weekly_enabled is not None:
        pref.weekly_enabled = update.weekly_enabled  # type: ignore[assignment]
    if update.instant_alerts is not None:
        pref.instant_alerts = update.instant_alerts  # type: ignore[assignment]
    if update.resume_alerts is True:
        pref.paused_until = None  # type: ignore[assignment]
    elif update.paused_until is not None:
        pref.paused_until = update.paused_until  # type: ignore[assignment]

    await db.commit()
    await db.refresh(pref)
    return AlertPreferencesResponse(
        user_id=user_id,
        domains=list(pref.domains or []),
        channels=list(pref.channels or []),
        min_match_score=pref.min_match_score,
        is_enabled=bool(pref.is_enabled),
        last_alert_at=pref.last_alert_at,
        slot_domains=dict(pref.slot_domains or {}),
        weekly_enabled=(
            bool(pref.weekly_enabled) if pref.weekly_enabled is not None else True
        ),
        instant_alerts=(
            bool(pref.instant_alerts) if pref.instant_alerts is not None else True
        ),
        paused_until=pref.paused_until,
    )


@router.post("/preferences/{user_id}/send-alert")
async def send_alert_now(
    user_id: str,
    override: AlertPreferencesUpdate | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Build today's alert and send it now.

    Uses the saved preferences, optionally overridden for this one send via
    the ``override`` body (a one-off test that never touches the saved
    preferences). Returns the report summary, per-channel delivery results
    and how many jobs were included; the send is recorded in history.
    Only jobs created since the previous alert are included (no duplicates);
    a one-off override does NOT advance the window.
    """
    from interntrack.scheduler.jobs import _deliver_alert, _user_profile

    prefs = await _load_alert_preferences(db, user_id=user_id)
    is_one_off = override is not None
    if override is not None:
        if override.domains is not None:
            prefs["domains"] = _normalize_domains(override.domains)
        if override.channels is not None:
            prefs["channels"] = [c for c in override.channels if c in _ALERT_CHANNELS]
        if override.min_match_score is not None:
            prefs["min_match_score"] = max(
                0,
                min(100, int(override.min_match_score)),
            )

    domains = prefs.get("domains") or None
    service = ReportService(db)
    report = await service.generate_daily_report(
        domains=domains,
        min_match_score=prefs.get("min_match_score"),
        since=prefs.get("last_alert_at"),
    )
    manager = NotificationManager(db)
    channels = prefs.get("channels") or None
    subject = "InternTrack Daily Alert"
    if domains:
        subject += f" ({', '.join(domains)})"
    # Route the send to the user's own email / Telegram when they have an
    # account; the legacy path (no account) uses the shared configured channels.
    user = await _user_profile(db, user_id)
    results = await _deliver_alert(
        manager,
        channels,
        report,
        db,
        domains=domains,
        subject=subject,
        user=user,
    )

    job_count = len(report.get("new_jobs") or [])
    if not is_one_off:
        await _mark_alert_sent(db, user_id=user_id)
    await _record_alert_history(
        db,
        user_id=user_id,
        subject=subject,
        channels=channels or list(results.keys()),
        domains=domains or [],
        job_count=job_count,
        results=results,
    )
    return {
        "summary": report.get("summary") or {},
        "results": results,
        "job_count": job_count,
        "domains": domains or [],
        "channels": list(results.keys()),
        "min_match_score": prefs.get("min_match_score"),
    }


@router.get("/preferences/{user_id}/history")
async def get_alert_history(
    user_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Recent alert sends for a user, newest first."""
    from sqlalchemy import select

    from interntrack.domain.models import NotificationHistory

    result = await db.execute(
        select(NotificationHistory)
        .where(NotificationHistory.user_id == user_id)
        .order_by(NotificationHistory.created_at.desc())
        .limit(min(max(int(limit), 1), 100))
    )
    rows = result.scalars().all()
    return {
        "history": [
            {
                "id": row.id,
                "sent_at": (row.created_at.isoformat() if row.created_at else None),
                "subject": row.subject,
                "channels": row.channels or [],
                "domains": row.domains or [],
                "job_count": row.job_count or 0,
                "results": row.results or {},
            }
            for row in rows
        ],
        "total": len(rows),
    }
