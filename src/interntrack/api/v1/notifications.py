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
from interntrack.config import get_settings
from interntrack.database.session import get_db
from interntrack.scheduler.jobs import (
    ALERT_SLOTS as _ALERT_SLOTS,
)
from interntrack.scheduler.jobs import (
    DEFAULT_LOCATION,
    _job_match_score,
    _latest_resume_skill_names,
    _load_alert_preferences,
    _mark_alert_sent,
    _record_alert_history,
)
from interntrack.services.notification_service import NotificationManager
from interntrack.services.report_service import ReportService
from interntrack.utils.helpers import _domain_is_routable, email_domain

router = APIRouter()

# Domain keys supported by the alert classifier (matches report_service).
_ALERT_DOMAINS = (
    "security",
    "frontend",
    "coding",
    "data",
    "hardware",
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


@router.get("/email-status")
async def get_email_status():
    """Email deliverability status for the Settings page.

    Reports which provider is active (Resend beats SMTP when configured),
    the effective From address actually used (never the non-routable
    ``.local`` default), and whether that address is likely to authenticate
    (SPF/DKIM). Lets the dashboard explain — and fix — Spam-folder issues.
    """
    settings = get_settings()
    effective_from = settings.effective_email_from
    domain = email_domain(effective_from)
    routable = _domain_is_routable(domain)
    provider = "none"
    if settings.resend_api_key:
        provider = "resend"
    elif settings.is_email_configured:
        provider = "smtp"
    return {
        "provider": provider,
        "configured": settings.is_email_configured or bool(settings.resend_api_key),
        "from": effective_from,
        "domain": domain or None,
        "routable": routable,
        "tips": [
            (
                "Mark one InternTrack email as 'Not spam' in Gmail — the "
                "sender learns and future mail lands in Inbox."
            ),
            "Add the From address to your contacts.",
            (
                "A real sending domain (EMAIL_FROM) with SPF/DKIM/DMARC "
                "DNS records fixes this permanently."
            ),
            ("Best fix: set RESEND_API_KEY — Resend handles SPF/DKIM automatically."),
        ],
    }


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


@router.post("/user/{user_id}/test")
async def send_user_test_alert(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Send a test alert to ONE user's own email + Telegram.

    Mirrors how the real daily digest is routed: the message goes to the
    user's own email address (not the shared/owner mailbox) and their own
    Telegram chat, so a friend can verify their delivery path the moment
    they are onboarded instead of waiting for the next 8:00/13:00/19:00 IST
    slot. Never raises: returns a ``results``/``hint`` dict in every case.
    """
    from interntrack.scheduler.jobs import DEFAULT_ALERT_USER, _user_profile

    user = await _user_profile(db, user_id)
    # The legacy default account (``user1``) predates registered users — it
    # has no User row, so route its test through the shared configured
    # channels, exactly like the daily digest does for that account.
    if user is None and user_id != DEFAULT_ALERT_USER:
        return {
            "sent": False,
            "results": {},
            "hint": "No account found with this user ID.",
        }

    if user is not None:
        recipient = {
            "email": getattr(user, "email", None),
            "telegram_chat_id": getattr(user, "telegram_chat_id", None),
            "phone_number": getattr(user, "phone_number", None),
        }
        name = (getattr(user, "name", None) or "").strip() or "there"
        location = (getattr(user, "location", None) or "").strip() or "your city"
        domains = list(getattr(user, "domains", None) or [])
        domain_txt = ", ".join(domains) if domains else "your categories"
    else:
        recipient = None
        name = "there"
        location = "your city"
        domain_txt = "your categories"

    message = (
        f"👋 <b>Hi {name} — this is a test alert!</b>\n\n"
        "Your personalized InternTrack digest is working. When new jobs match "
        f"<b>{domain_txt}</b> in <b>{location}</b>, they will land right "
        "here with an Apply button, at 8:00 / 13:00 / 19:00 IST.\n\n"
        "No action needed — you are all set. ✅"
    )
    try:
        manager = NotificationManager(db)
        results = await manager.notify(
            ["email", "telegram"],
            message,
            subject="🔔 Test alert — InternTrack",
            recipient=recipient,
        )
        sent_channels = [ch for ch, ok in results.items() if ok]
        has_contact = bool(
            recipient and (recipient.get("email") or recipient.get("telegram_chat_id"))
        )
        missing = [
            ch
            for ch in ("email", "telegram")
            if ch not in sent_channels and has_contact
        ]
        hint = None
        if sent_channels:
            hint = f"Delivered via {', '.join(sent_channels)}. " + (
                f"Not set up: {', '.join(missing)}." if missing else ""
            )
        elif recipient is None:
            hint = (
                "Nothing was sent — the shared email/Telegram channels are "
                "not configured on the API or delivery failed."
            )
        elif not has_contact:
            hint = (
                "Nothing was sent — this account has no email and no Telegram "
                "chat ID on file."
            )
        else:
            hint = (
                "Nothing was sent — delivery failed or the email/Telegram "
                "channels are not configured on the API."
            )
        return {"sent": bool(sent_channels), "results": results, "hint": hint}
    except Exception as e:  # pragma: no cover - network path
        return {"sent": False, "results": {}, "hint": f"Could not send: {e}"}


@router.get("/stats")
async def get_notification_stats(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """Aggregated alert-delivery stats across all users.

    Powers the dashboard Alerts page: total sends, jobs delivered,
    per-channel delivered/failed totals, a per-user breakdown and a daily
    trend for the last N days. Pure read — never raises.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from interntrack.domain.models import NotificationHistory

    window = max(1, min(int(days), 90))
    since = datetime.now(UTC) - timedelta(days=window)
    result = await db.execute(
        select(NotificationHistory)
        .where(NotificationHistory.created_at >= since)
        .order_by(NotificationHistory.created_at.asc())
    )
    rows = result.scalars().all()

    per_channel: dict[str, dict[str, int]] = {}
    per_user: dict[str, dict] = {}
    trend: dict[str, dict[str, int]] = {}
    total_sends = len(rows)
    total_jobs = 0

    for row in rows:
        created = row.created_at
        job_count = int(row.job_count or 0)
        total_jobs += job_count

        uid = str(row.user_id or "user1")
        u = per_user.setdefault(
            uid,
            {
                "sends": 0,
                "jobs": 0,
                "delivered": 0,
                "failed": 0,
                "last_sent_at": None,
            },
        )
        u["sends"] += 1
        u["jobs"] += job_count

        day = (created or since).strftime("%Y-%m-%d")
        t = trend.setdefault(day, {"sends": 0, "jobs": 0})
        t["sends"] += 1
        t["jobs"] += job_count

        for ch, ok in (row.results or {}).items():
            bucket = per_channel.setdefault(str(ch), {"delivered": 0, "failed": 0})
            if ok:
                bucket["delivered"] += 1
                u["delivered"] += 1
            else:
                bucket["failed"] += 1
                u["failed"] += 1
        if created is not None and (
            u["last_sent_at"] is None or created > u["last_sent_at"]
        ):
            u["last_sent_at"] = created

    # Flatten the per-user rows for JSON (keep datetime comparison above).
    for u in per_user.values():
        if u["last_sent_at"] is not None:
            u["last_sent"] = u["last_sent_at"].isoformat()
        else:
            u["last_sent"] = None
        u.pop("last_sent_at", None)

    delivered = sum(v["delivered"] for v in per_channel.values())
    failed = sum(v["failed"] for v in per_channel.values())
    return {
        "days": window,
        "total_sends": total_sends,
        "total_jobs_sent": total_jobs,
        "delivered": delivered,
        "failed": failed,
        "delivery_rate": round(delivered / (delivered + failed) * 100, 1)
        if (delivered + failed)
        else None,
        "per_channel": per_channel,
        "per_user": per_user,
        "trend": [{"date": d, **v} for d, v in sorted(trend.items())],
    }


@router.get("/owner")
async def get_owner():
    """Email of the owner (admin) account.

    The owner is the account named by ``TEAM_OWNER_EMAIL`` when set,
    otherwise the first-registered account. The dashboard uses this to
    show the Team & Users admin page to the owner only — members are
    separate users and must not see each other's profiles or stats.
    """
    settings = get_settings()
    override = str(settings.team_owner_email or "").strip().lower()
    # Avoid a full async DB round-trip for the common override case.
    if override:
        return {"email": override, "is_owner": True}
    # Fall back to the first-registered account.
    try:
        from sqlalchemy import select

        from interntrack.domain.models import User

        async for db in get_db():
            result = await db.execute(select(User).order_by(User.created_at.asc()))
            users = list(result.scalars().all())
            if users:
                email = str(getattr(users[0], "email", "") or "").strip()
                return {"email": email, "is_owner": True}
    except Exception as exc:  # noqa: BLE001 - never fail the dashboard
        print(f"[owner lookup] failed: {exc}")
    return {"email": None, "is_owner": False}


@router.get("/team/recap")
async def get_team_recap(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """Per-member alert-delivery summary for the owner's team view.

    One row per registered account: digests sent, jobs delivered, emails
    delivered, and the top roles/companies covered over the last N days.
    Powers the Team page recap panel and mirrors what the weekly owner
    recap email contains. Pure read — never raises.
    """
    from interntrack.scheduler.jobs import team_recap_stats

    return await team_recap_stats(db, days=max(1, min(int(days), 30)))


@router.post("/team/recap/send")
async def send_team_recap_now():
    """Send the weekly team-alerts recap email to the owner right now.

    Vercel is serverless, so the APScheduler worker never executes there;
    the GitHub Actions weekly cron hits this endpoint every Monday (after
    the weekly digests) so the live deployment sends the owner recap too.
    Never raises: returns the job's status dict in every case.
    """
    from interntrack.scheduler.jobs import send_team_recap

    try:
        result = await send_team_recap()
    except Exception as e:  # pragma: no cover - defensive
        return {"sent": False, "reason": str(e)}
    return result


@router.post("/closing-soon")
async def run_closing_soon_sweep():
    """Run the closing-soon sweep now and return per-user job counts.

    Vercel is serverless, so the APScheduler worker never executes there;
    the free GitHub Actions cron hits this endpoint twice a day (mirroring
    the scheduler's morning/evening triggers) so users get their
    "🚨 Closing soon" digest on the live deployment too. Returns
    ``{user_id: job_count}`` for the users who received a digest.
    """
    from interntrack.scheduler.jobs import send_closing_soon_alerts

    try:
        sent = await send_closing_soon_alerts()
    except Exception as e:  # pragma: no cover - defensive
        return {"sent": {}, "users_alerted": 0, "error": str(e)}
    return {"sent": sent, "users_alerted": len(sent)}


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
        include_remote=prefs.get("include_remote", True),
        quiet_day_emails=prefs.get("quiet_day_emails", True),
        paused_until=prefs.get("paused_until"),
        min_salary=prefs.get("min_salary"),
        keywords=list(prefs.get("keywords") or []),
        experience_levels=list(prefs.get("experience_levels") or []),
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
    if update.include_remote is not None:
        pref.include_remote = update.include_remote  # type: ignore[assignment]
    if update.quiet_day_emails is not None:
        pref.quiet_day_emails = update.quiet_day_emails  # type: ignore[assignment]
    if update.resume_alerts is True:
        pref.paused_until = None  # type: ignore[assignment]
    elif update.paused_until is not None:
        pref.paused_until = update.paused_until  # type: ignore[assignment]
    if update.min_salary is not None:
        target = max(0, int(update.min_salary))
        pref.min_salary = target  # type: ignore[assignment]
    if update.keywords is not None:
        cleaned_kws: list[str] = []
        for kw in update.keywords:
            kw = str(kw).strip().lower()
            if kw and kw not in cleaned_kws:
                cleaned_kws.append(kw)
        pref.keywords = cleaned_kws[:10]  # type: ignore[assignment]
    if update.experience_levels is not None:
        cleaned_levels: list[str] = []
        for lvl in update.experience_levels:
            lvl = str(lvl).strip().lower()
            if lvl and lvl not in cleaned_levels:
                cleaned_levels.append(lvl)
        pref.experience_levels = cleaned_levels  # type: ignore[assignment]

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
        include_remote=(
            bool(pref.include_remote) if pref.include_remote is not None else True
        ),
        quiet_day_emails=(
            bool(pref.quiet_day_emails) if pref.quiet_day_emails is not None else True
        ),
        paused_until=pref.paused_until,
        min_salary=pref.min_salary,
        keywords=list(pref.keywords or []),
        experience_levels=list(pref.experience_levels or []),
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
    # Route the send to the user's own email / Telegram when they have an
    # account; the legacy path (no account) uses the shared configured channels.
    user = await _user_profile(db, user_id)
    user_location = (
        (getattr(user, "location", None) or "").strip() or DEFAULT_LOCATION or None
    )
    include_remote = bool(prefs.get("include_remote", True))
    service = ReportService(db)
    report = await service.generate_daily_report(
        domains=domains,
        min_match_score=prefs.get("min_match_score"),
        since=prefs.get("last_alert_at"),
        location=user_location,
        include_remote=include_remote,
        experience_levels=prefs.get("experience_levels") or None,
    )
    manager = NotificationManager(db)
    channels = prefs.get("channels") or None
    subject = "InternTrack Daily Alert"
    if domains:
        subject += f" ({', '.join(domains)})"
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
                "jobs": row.jobs or [],
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.get("/preferences/{user_id}/preview")
async def preview_digest(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Preview the next daily digest for a user WITHOUT sending anything.

    Runs the exact same pipeline the scheduled digest uses (same domains,
    location scope, include-remote setting, min match %, no-duplicates
    window) and returns the jobs that would be delivered, each with its
    match %. Nothing is sent, no window is advanced, no history row is
    created — purely a "what would I get?" lookahead.
    """
    from sqlalchemy import select

    from interntrack.domain.models import User

    prefs = await _load_alert_preferences(db, user_id=user_id)
    domains = prefs.get("domains") or None

    user = None
    if user_id != "user1":
        result = await db.execute(select(User).where(User.id == user_id))
        candidate = result.scalar_one_or_none()
        if isinstance(candidate, User):
            user = candidate
    user_location = (
        (getattr(user, "location", None) or "").strip() or DEFAULT_LOCATION or None
    )
    include_remote = bool(prefs.get("include_remote", True))

    service = ReportService(db)
    report = await service.generate_daily_report(
        domains=domains,
        min_match_score=prefs.get("min_match_score"),
        since=prefs.get("last_alert_at"),
        location=user_location,
        include_remote=include_remote,
        experience_levels=prefs.get("experience_levels") or None,
    )
    jobs = report.get("new_jobs") or []

    resume_skills = await _latest_resume_skill_names(db, user_id=user_id)
    preview_jobs = []
    min_score = report.get("min_match_score")
    for job in jobs:
        score = _job_match_score(resume_skills, job)
        if min_score and score is not None and score < min_score:
            continue
        preview_jobs.append(
            {
                "title": job.get("title"),
                "company": job.get("company"),
                "location": job.get("location"),
                "url": job.get("url"),
                "domain": job.get("domain") or "other",
                "match_score": score,
                "source": job.get("source"),
                "salary_min": job.get("salary_min"),
                "salary_max": job.get("salary_max"),
                "posted_at": job.get("posted_at"),
            }
        )
    preview_jobs.sort(key=lambda j: -(j["match_score"] or 0))

    return {
        "user_id": user_id,
        "domains": domains or [],
        "location": user_location,
        "include_remote": include_remote,
        "min_match_score": report.get("min_match_score"),
        "summary": report.get("summary", {}),
        "jobs": preview_jobs,
        "job_count": len(preview_jobs),
    }
