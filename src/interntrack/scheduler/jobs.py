"""
Scheduled background jobs.
"""

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta

from interntrack.database.session import get_db_session
from interntrack.services.job_service import JobService
from interntrack.services.notification_service import NotificationManager
from interntrack.services.report_service import ReportService, classify_domain

logger = logging.getLogger("interntrack.scheduler.jobs")

# How long to wait before retrying an email that failed to deliver once.
# Short enough to not stall the digest run, long enough to let a busy
# relay catch its breath. The owner failure ping only fires after this
# retry also fails.
EMAIL_RETRY_DELAY_SECONDS = 3.0


async def run_job_discovery():
    """Periodic job discovery from all sources."""
    async with get_db_session() as session:
        from interntrack.scrapers.registry import get_default_registry

        service = JobService(session)
        registry = get_default_registry()

        jobs = await registry.fetch_all(query="python developer")
        saved = await service.save_jobs(jobs)
        print(f"[{datetime.now(UTC)}] Discovery: {len(jobs)} found, {len(saved)} saved")


async def enrich_jobs_for_match(session, limit: int = 200) -> int:
    """Backfill skill tags / required_skills on jobs that carry a description.

    Many sources save descriptions without structured skills, so those jobs
    score ``match_score: null`` against every resume. This sweep derives
    tags + required_skills from the description text (same keyword engine
    as ``auto_tag_job``) and persists them, so previously-matchless jobs
    become scoreable. Best-effort: a failure never breaks the daily digest.
    """
    try:
        from sqlalchemy import select

        from interntrack.domain.models import Job
        from interntrack.services.job_service import (
            _derive_required_skills,
            auto_tag_job,
        )

        result = await session.execute(
            select(Job)
            .where(Job.description.isnot(None))
            .where(Job.description != "")
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        jobs = list(result.scalars().all())
        updated = 0
        for job in jobs:
            changed = False
            tags = [str(t) for t in (getattr(job, "tags", None) or []) if str(t)]
            required = [
                s for s in (getattr(job, "required_skills", None) or []) if str(s)
            ]
            data = {
                "title": str(job.title or ""),
                "description": str(job.description or ""),
                "tags": tags,
                "required_skills": required,
            }
            normalized = auto_tag_job(data)
            new_tags = [t for t in (normalized.get("tags") or []) if t not in tags]
            if new_tags:
                job.tags = (tags + new_tags)[:15]
                changed = True
            if not required:
                derived = _derive_required_skills(data)
                if derived:
                    job.required_skills = derived
                    changed = True
            if changed:
                updated += 1
        if updated:
            await session.commit()
        return updated
    except Exception as e:  # noqa: BLE001 - enrichment must never break anything
        print(f"[{datetime.now(UTC)}] Skill enrichment failed: {e}")
        return 0


# Default user whose alert preferences apply to the scheduled digest.
DEFAULT_ALERT_USER = "user1"
DEFAULT_DOMAINS = ["security"]  # Default alert domain when no user prefs
DEFAULT_LOCATION = "Bangalore"  # Default discovery location

# The three daily send slots (see .github/workflows/daily-refresh.yml).
# Default categories per slot, used when the user hasn't customized
# ``slot_domains``. The workflow discovers cybersecurity / software
# engineering / python developer jobs respectively at these times.
ALERT_SLOTS = ("morning", "afternoon", "evening")
DEFAULT_SLOT_DOMAINS = {
    "morning": ["security"],
    "afternoon": ["coding"],
    "evening": ["coding", "data"],
}


async def _load_alert_preferences(
    session,
    user_id: str = DEFAULT_ALERT_USER,
) -> dict:
    """Load saved alert preferences for a user.

    Returns an empty dict when nothing is saved — callers treat that as
    "all domains, all configured channels, alerts on". A saved (even
    disabled) row returns its stored values plus ``is_enabled`` so callers
    can skip the digest when alerts are turned off. Never raises:
    preference loading must not break the daily digest.
    """
    try:
        from sqlalchemy import select

        from interntrack.domain.models import AlertPreferences

        result = await session.execute(
            select(AlertPreferences).where(AlertPreferences.user_id == user_id)
        )
        pref = result.scalar_one_or_none()
        if pref is not None:
            slot_domains = (
                dict(pref.slot_domains)
                if isinstance(getattr(pref, "slot_domains", None), dict)
                else {}
            )
            weekly = getattr(pref, "weekly_enabled", None)
            instant = getattr(pref, "instant_alerts", None)
            return {
                "domains": list(pref.domains or []),
                "channels": list(pref.channels or []),
                "min_match_score": pref.min_match_score,
                "is_enabled": bool(pref.is_enabled),
                "last_alert_at": pref.last_alert_at,
                "slot_domains": slot_domains,
                "weekly_enabled": weekly if isinstance(weekly, bool) else True,
                "instant_alerts": instant if isinstance(instant, bool) else True,
                "include_remote": (
                    bool(getattr(pref, "include_remote", True))
                    if getattr(pref, "include_remote", None) is not None
                    else True
                ),
                "quiet_day_emails": (
                    bool(getattr(pref, "quiet_day_emails", True))
                    if getattr(pref, "quiet_day_emails", None) is not None
                    else True
                ),
                "paused_until": getattr(pref, "paused_until", None),
                "min_salary": getattr(pref, "min_salary", None),
                "keywords": list(getattr(pref, "keywords", None) or []),
                "experience_levels": list(
                    getattr(pref, "experience_levels", None) or []
                ),
            }
    except Exception:
        return {}
    return {}


def _alerts_paused(prefs: dict) -> bool:
    """True when vacation mode is active (paused_until is in the future).

    Gates every delivery path — daily digest, weekly digest, instant
    Telegram pings and one-off sends — so a single Settings toggle can
    silence everything until a chosen date. Never raises on bad input:
    garbage or missing timestamps mean "not paused".
    """
    until = prefs.get("paused_until")
    if not until:
        return False
    try:
        from interntrack.utils.helpers import utcnow

        return bool(until > utcnow())
    except Exception:  # noqa: BLE001 - never break delivery over a bad date
        return False


async def _mark_alert_sent(
    session,
    user_id: str,
    at: datetime | None = None,
) -> None:
    """Record when the last alert was sent.

    This drives the no-duplicates window: the next digest only includes jobs
    created after this timestamp. Never raises.
    """
    import contextlib

    try:
        from sqlalchemy import select

        from interntrack.domain.models import AlertPreferences
        from interntrack.utils.helpers import utcnow

        result = await session.execute(
            select(AlertPreferences).where(AlertPreferences.user_id == user_id)
        )
        pref = result.scalar_one_or_none()
        stamp = at or utcnow()
        if pref is None:
            session.add(AlertPreferences(user_id=user_id, last_alert_at=stamp))
        else:
            pref.last_alert_at = stamp
        await session.commit()
    except Exception:
        with contextlib.suppress(Exception):
            await session.rollback()


async def _record_alert_history(
    session,
    user_id: str,
    subject: str | None,
    channels: list,
    domains: list,
    job_count: int,
    results: dict,
    jobs: list | None = None,
) -> None:
    """Persist an alert-send record for the dashboard history view.

    ``jobs`` (optional) is the compact list of jobs actually sent — title,
    company, location, url, domain and match score — so the dashboard can
    show exactly what each digest delivered instead of just a count.
    Never raises — history must never break a digest send.
    """
    import contextlib

    try:
        from interntrack.domain.models import NotificationHistory

        session.add(
            NotificationHistory(
                user_id=user_id,
                subject=subject,
                channels=list(channels or []),
                domains=list(domains or []),
                job_count=int(job_count or 0),
                results=dict(results or {}),
                jobs=list(jobs or []),
            )
        )
        await session.commit()
    except Exception:
        with contextlib.suppress(Exception):
            await session.rollback()


async def _team_digest_stats(
    session,
    email: str | None = None,
) -> dict | None:
    """Team snapshot for the weekly email: member count + your referrals.

    Returns ``{team_size, my_referrals}`` or ``None`` when no accounts exist
    (or the query fails). ``my_referrals`` counts accounts whose
    ``referred_by`` matches this user's email, excluding their own account.
    """
    try:
        from sqlalchemy import select

        from interntrack.domain.models import User

        result = await session.execute(select(User))
        users = list(result.scalars().all())
        if not users:
            return None
        my_email = (email or "").strip().lower()
        my_refs = 0
        for u in users:
            referred = str(getattr(u, "referred_by", "") or "").lower()
            own_email = str(getattr(u, "email", "") or "").strip().lower()
            if my_email and referred == my_email and own_email != my_email:
                my_refs += 1
        return {"team_size": len(users), "my_referrals": my_refs}
    except Exception:  # noqa: BLE001 - best-effort email enrichment
        return None


async def team_recap_stats(session, days: int = 7) -> dict:
    """Per-member alert delivery for the last N days, for the owner recap.

    One entry per registered account with how many digests were sent, how
    many jobs were delivered, how many emails landed, and the top domains /
    companies covered (from the compact ``jobs`` list each digest stores).
    Pure read — never raises: an empty ``users`` list on failure keeps both
    the owner email job and the dashboard endpoint safe. This is the single
    source of truth shared by the weekly owner recap email and the Team
    page recap panel.
    """
    try:
        from collections import Counter

        from sqlalchemy import func, select

        from interntrack.domain.models import Application, NotificationHistory, User
        from interntrack.utils.helpers import to_naive_utc

        window = max(1, int(days or 7))
        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=window)
        since_str = since.strftime("%Y-%m-%d %H:%M:%S")

        users_result = await session.execute(select(User))
        users = list(users_result.scalars().all())
        hist_result = await session.execute(select(NotificationHistory))
        rows = list(hist_result.scalars().all())

        # Applications recorded straight from the signed digest Apply links
        # (``source="email"``), per member, within the window — the recap's
        # "member activity without the dashboard" signal.
        email_applied: dict[str, int] = {}
        applied_result = await session.execute(
            select(Application.user_id, func.count(Application.id))
            .where(
                Application.source == "email",
                Application.applied_at >= since,
            )
            .group_by(Application.user_id)
        )
        for uid, count in applied_result.all():
            if uid:
                email_applied[str(uid)] = int(count)

        by_user: dict[str, list] = {}
        for row in rows:
            created = getattr(row, "created_at", None)
            if created is None:
                continue
            created_naive = to_naive_utc(created)
            if (
                created_naive is None
                or created_naive.strftime("%Y-%m-%d %H:%M:%S") < since_str
            ):
                continue
            uid = str(getattr(row, "user_id", "") or "")
            by_user.setdefault(uid, []).append(row)

        out: list[dict] = []
        for u in users:
            uid = str(getattr(u, "id", "") or "")
            rows_for = by_user.get(uid, [])
            sends = len(rows_for)
            jobs = sum(int(getattr(r, "job_count", 0) or 0) for r in rows_for)
            emails_ok = sum(
                1
                for r in rows_for
                if bool((getattr(r, "results", None) or {}).get("email"))
            )
            opened = sum(1 for r in rows_for if getattr(r, "opened_at", None))
            domain_counter: Counter = Counter()
            company_counter: Counter = Counter()
            for r in rows_for:
                for d in getattr(r, "domains", None) or []:
                    if d:
                        domain_counter[str(d)] += 1
                for j in getattr(r, "jobs", None) or []:
                    company = str((j or {}).get("company") or "").strip()
                    if company and company.lower() != "unknown":
                        company_counter[company] += 1
            out.append(
                {
                    "user_id": uid,
                    "name": str(getattr(u, "name", "") or ""),
                    "email": str(getattr(u, "email", "") or ""),
                    "location": str(getattr(u, "location", "") or ""),
                    "domains": [str(d) for d in (getattr(u, "domains", None) or [])],
                    "sends": sends,
                    "jobs": jobs,
                    "emails_ok": emails_ok,
                    "opened": opened,
                    "email_applied": email_applied.get(uid, 0),
                    "top_domains": [d for d, _ in domain_counter.most_common(3)],
                    "top_companies": [c for c, _ in company_counter.most_common(5)],
                }
            )
        out.sort(key=lambda r: (-r["jobs"], r["name"].lower()))
        return {
            "days": window,
            "total_sends": sum(r["sends"] for r in out),
            "total_jobs": sum(r["jobs"] for r in out),
            "total_opened": sum(r["opened"] for r in out),
            "total_email_applied": sum(email_applied.values()),
            "users": out,
        }
    except Exception:  # noqa: BLE001 - a recap must never break the worker
        return {
            "days": int(days or 7),
            "total_sends": 0,
            "total_jobs": 0,
            "total_opened": 0,
            "total_email_applied": 0,
            "users": [],
        }


def _build_team_recap_html(stats: dict, owner_name) -> str:
    """HTML body for the owner's weekly team-alerts recap email.

    Renders a per-member table (digests / jobs / emails delivered / top
    roles & companies). Every interpolated value is escaped — member names
    and companies come from untrusted account/job data.
    """
    from html import escape

    users = stats.get("users") or []
    total_jobs = int(stats.get("total_jobs") or 0)
    total_sends = int(stats.get("total_sends") or 0)
    total_opened = int(stats.get("total_opened") or 0)
    total_email_applied = int(stats.get("total_email_applied") or 0)
    rows: list[str] = []
    for u in users:
        domains = ", ".join(u.get("top_domains") or u.get("domains") or []) or "all"
        companies = ", ".join(u.get("top_companies") or []) or "—"
        opened_txt = "✓" if int(u.get("opened", 0) or 0) else "—"
        rows.append(
            "<tr>"
            "<td style='padding:8px 10px;border-bottom:1px solid #e2e8f0;'>"
            f"<b>{escape(str(u.get('name') or ''))}</b><br/>"
            f"<span style='color:#64748b;font-size:12px;'>"
            f"{escape(str(u.get('email') or ''))} · "
            f"{escape(str(u.get('location') or '—'))}</span></td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid #e2e8f0;"
            f"text-align:center;'>{u.get('sends', 0)}</td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid #e2e8f0;"
            f"text-align:center;'>{u.get('jobs', 0)}</td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid #e2e8f0;"
            f"text-align:center;'>{u.get('emails_ok', 0)}</td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid #e2e8f0;"
            f"text-align:center;'>{opened_txt}</td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid #e2e8f0;"
            f"text-align:center;'>{u.get('email_applied', 0)}</td>"
            "<td style='padding:8px 10px;border-bottom:1px solid #e2e8f0;'>"
            f"{escape(domains)}<br/>"
            f"<span style='color:#64748b;font-size:12px;'>🏢 "
            f"{escape(companies)}</span></td>"
            "</tr>"
        )
    email_applied_line = ""
    if total_email_applied:
        email_applied_line = (
            f"<p style='color:#64748b;font-size:13px;'>📨 <b>{total_email_applied}</b> "
            "application(s) recorded straight from digest Apply clicks — "
            "members applying without ever opening the dashboard.</p>"
        )
    opened_line = ""
    if total_opened:
        opened_line = (
            f"<p style='color:#64748b;font-size:13px;'>👀 <b>{total_opened}</b> "
            "member(s) opened a digest this week (tracking pixel).</p>"
        )
    return (
        "<div style='font-family:Inter,Arial,sans-serif;max-width:640px;"
        "margin:0 auto;'>"
        "<h2 style='margin-bottom:4px;'>📬 Team alerts recap</h2>"
        f"<p style='color:#64748b;margin-top:0;'>Hey "
        f"{escape(str(owner_name or 'there'))} — here's what your team's "
        "personalized job alerts delivered over the last 7 days.</p>"
        "<table style='width:100%;border-collapse:collapse;'>"
        "<tr style='background:#f1f5f9;'>"
        "<th style='padding:8px 10px;text-align:left;'>Member</th>"
        "<th style='padding:8px 10px;'>Digests</th>"
        "<th style='padding:8px 10px;'>Jobs</th>"
        "<th style='padding:8px 10px;'>Emails ✓</th>"
        "<th style='padding:8px 10px;'>👀 Opened</th>"
        "<th style='padding:8px 10px;'>📨 Applied</th>"
        "<th style='padding:8px 10px;text-align:left;'>Top roles & companies</th>"
        "</tr>" + "".join(rows) + "</table>"
        f"<p style='color:#64748b;font-size:13px;'><b>{total_jobs}</b> jobs across "
        f"<b>{total_sends}</b> digest sends for <b>{len(users)}</b> member(s). "
        "Each person still receives only their own role + city — nothing mixed.</p>"
        + email_applied_line
        + opened_line
        + "</div>"
    )


async def _notify_owner_of_failure(
    session,
    member_name: str,
    member_email: str,
    channel: str,
    domain_label: str = "",
) -> bool:
    """Ping the team owner on Telegram when a member's delivery fails.

    The owner is the account named by ``TEAM_OWNER_EMAIL`` when set,
    otherwise the first-registered account (same rule as the weekly team
    recap). The ping only fires when the bot token is configured AND the
    owner has a ``telegram_chat_id`` saved on their profile; otherwise it
    silently skips — the member's own history still records the failure.
    Never raises; returns whether a ping was attempted.
    """
    try:
        from sqlalchemy import select

        from interntrack.config import get_settings
        from interntrack.domain.models import User
        from interntrack.services.notification_service import TelegramChannel

        settings = get_settings()
        if not (settings.telegram_bot_token and settings.is_telegram_configured):
            return False
        result = await session.execute(select(User).order_by(User.created_at.asc()))
        users = list(result.scalars().all())
        if not users:
            return False
        override = str(settings.team_owner_email or "").strip().lower()
        owner = users[0]
        if override:
            for u in users:
                if str(getattr(u, "email", "") or "").strip().lower() == override:
                    owner = u
                    break
        owner_chat = str(getattr(owner, "telegram_chat_id", "") or "").strip()
        if not owner_chat:
            return False
        lines = [
            "⚠️ <b>Alert delivery failed</b>",
            f"👤 {_esc(member_name or member_email or 'Member')}",
            f"📧 {_esc(member_email or '—')}",
            f"📡 channel: <b>{_esc(channel)}</b>",
        ]
        if domain_label:
            lines.append(f"🎯 domains: {_esc(domain_label)}")
        lines.append("")
        lines.append(
            "Check the SMTP / Resend credentials or the member's "
            "spam settings — their digest did not go out."
        )
        await TelegramChannel(
            bot_token=str(settings.telegram_bot_token),
            chat_id=owner_chat,
        ).send("\n".join(lines), subject="⚠️ Alert delivery failed")
        return True
    except Exception:  # noqa: BLE001 - owner pings must never break delivery
        return False


async def send_team_recap() -> dict:
    """Weekly owner email: what each team member's alerts delivered.

    Runs after the Monday weekly digests (and via the ``POST
    /notifications/team/recap/send`` endpoint on the serverless deployment,
    which the GitHub Actions weekly cron hits). The owner is the account
    named by ``TEAM_OWNER_EMAIL`` when set, otherwise the first-registered
    account. Aggregates the last 7 days of per-member delivery history
    (``team_recap_stats``) and emails one summary to the owner.

    Returns a small status dict ``{"sent": bool, "reason": str | None}`` so
    the HTTP endpoint can surface why a run was skipped. Skips quietly (no
    email) when fewer than two accounts exist, email is not configured, or
    there is no history in the window — never raises.
    """
    async with get_db_session() as session:
        try:
            from sqlalchemy import select

            from interntrack.config import get_settings
            from interntrack.domain.models import User
            from interntrack.services.notification_service import EmailChannel

            settings = get_settings()
            if not settings.team_recap_enabled:
                reason = "team recap disabled (TEAM_RECAP_ENABLED unset)"
                print(f"[{datetime.now(UTC)}] Team recap skipped — {reason}")
                return {"sent": False, "reason": reason}

            result = await session.execute(select(User).order_by(User.created_at.asc()))
            users = list(result.scalars().all())
            if len(users) < 2:
                reason = "need at least 2 accounts"
                print(f"[{datetime.now(UTC)}] Team recap skipped — {reason}")
                return {"sent": False, "reason": reason}

            # Explicit owner override wins; otherwise the first-registered
            # account is the team owner. An override that matches no account
            # falls back to first-registered so the recap is never lost.
            override = str(settings.team_owner_email or "").strip().lower()
            owner = users[0]
            if override:
                matched = [
                    u
                    for u in users
                    if str(getattr(u, "email", "") or "").strip().lower() == override
                ]
                if matched:
                    owner = matched[0]
            owner_email = str(getattr(owner, "email", "") or "").strip()
            if not owner_email:
                reason = "owner has no email"
                print(f"[{datetime.now(UTC)}] Team recap skipped — {reason}")
                return {"sent": False, "reason": reason}
            if not settings.is_email_configured:
                reason = "email not configured"
                print(f"[{datetime.now(UTC)}] Team recap skipped — {reason}")
                return {"sent": False, "reason": reason}
            stats = await team_recap_stats(session, days=7)
            if not stats.get("users"):
                reason = "no alert history in window"
                print(f"[{datetime.now(UTC)}] Team recap skipped — {reason}")
                return {"sent": False, "reason": reason}
            subject = (
                f"📬 Team alerts recap — {len(stats['users'])} members, "
                f"{stats['total_jobs']} jobs this week"
            )
            channel = EmailChannel(
                host=settings.smtp_host,
                port=settings.smtp_port,
                user=settings.smtp_user or "",
                password=settings.smtp_password or "",
                from_email=settings.email_from,
                to_email=owner_email,
            )
            await channel.send(
                _build_team_recap_html(stats, getattr(owner, "name", None)),
                subject=subject,
            )
            print(f"[{datetime.now(UTC)}] Team recap sent to {owner_email}")
            return {
                "sent": True,
                "to": owner_email,
                "members": len(stats.get("users") or []),
                "jobs": int(stats.get("total_jobs") or 0),
            }
        except Exception as e:  # noqa: BLE001 - recap must never crash the worker
            print(f"[{datetime.now(UTC)}] Team recap failed: {e}")
            return {"sent": False, "reason": str(e)}


def _build_daily_summary_html(stats: dict) -> str:
    """Compact HTML body for the owner's daily delivery summary email."""
    from html import escape

    users = stats.get("users") or []
    rows: list[str] = []
    for u in users:
        rows.append(
            "<tr>"
            "<td style='padding:6px 10px;border-bottom:1px solid #e2e8f0;'>"
            f"<b>{escape(str(u.get('name') or ''))}</b></td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #e2e8f0;"
            f"text-align:center;'>{u.get('sends', 0)}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #e2e8f0;"
            f"text-align:center;'>{u.get('jobs', 0)}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #e2e8f0;"
            f"text-align:center;'>{u.get('opened', 0)}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #e2e8f0;"
            f"text-align:center;'>{u.get('email_applied', 0)}</td>"
            "</tr>"
        )
    return (
        "<div style='font-family:Inter,Arial,sans-serif;max-width:640px;"
        "margin:0 auto;'>"
        "<h2 style='margin-bottom:4px;'>📊 Today's delivery</h2>"
        f"<p style='color:#64748b;margin-top:0;'>"
        f"{stats.get('total_sends', 0)} digest sends · "
        f"{stats.get('total_jobs', 0)} jobs · "
        f"{stats.get('total_opened', 0)} opened · "
        f"{stats.get('total_email_applied', 0)} applied from email.</p>"
        "<table style='width:100%;border-collapse:collapse;'>"
        "<tr style='background:#f1f5f9;'>"
        "<th style='padding:6px 10px;text-align:left;'>Member</th>"
        "<th style='padding:6px 10px;'>Digests</th>"
        "<th style='padding:6px 10px;'>Jobs</th>"
        "<th style='padding:6px 10px;'>👀 Opened</th>"
        "<th style='padding:6px 10px;'>📨 Applied</th>"
        "</tr>" + "".join(rows) + "</table>"
        "<p style='color:#94a3b8;font-size:12px;'>Automatic daily summary — "
        "no action needed.</p>"
        "</div>"
    )


async def send_daily_owner_summary() -> dict:
    """Daily owner email: today's per-member delivery + engagement.

    One compact summary each evening (after the last digest slot) so the
    owner knows digests went out, who opened them and who applied — without
    logging in. Reuses ``team_recap_stats(days=1)``. Skips quietly when
    email is not configured, the owner has no email, or nothing was sent in
    the window. Never raises.
    """
    async with get_db_session() as session:
        try:
            from sqlalchemy import select

            from interntrack.config import get_settings
            from interntrack.domain.models import User
            from interntrack.services.notification_service import EmailChannel

            settings = get_settings()
            if not settings.is_email_configured:
                return {"sent": False, "reason": "email not configured"}

            result = await session.execute(select(User).order_by(User.created_at.asc()))
            users = list(result.scalars().all())
            if not users:
                return {"sent": False, "reason": "no accounts"}

            override = str(settings.team_owner_email or "").strip().lower()
            owner = users[0]
            if override:
                matched = [
                    u
                    for u in users
                    if str(getattr(u, "email", "") or "").strip().lower() == override
                ]
                if matched:
                    owner = matched[0]
            owner_email = str(getattr(owner, "email", "") or "").strip()
            if not owner_email:
                return {"sent": False, "reason": "owner has no email"}

            stats = await team_recap_stats(session, days=1)
            if not stats.get("users") or not stats.get("total_sends"):
                return {"sent": False, "reason": "nothing sent in window"}

            subject = (
                f"📊 Today's delivery — {stats['total_jobs']} jobs, "
                f"{stats['total_opened']} opened, "
                f"{stats['total_email_applied']} applied"
            )
            channel = EmailChannel(
                host=settings.smtp_host,
                port=settings.smtp_port,
                user=settings.smtp_user or "",
                password=settings.smtp_password or "",
                from_email=settings.email_from,
                to_email=owner_email,
            )
            await channel.send(
                _build_daily_summary_html(stats),
                subject=subject,
            )
            print(f"[{datetime.now(UTC)}] Daily owner summary sent to {owner_email}")
            return {
                "sent": True,
                "to": owner_email,
                "members": len(stats.get("users") or []),
                "jobs": int(stats.get("total_jobs") or 0),
            }
        except Exception as e:  # noqa: BLE001 - never crash the worker
            print(f"[{datetime.now(UTC)}] Daily owner summary failed: {e}")
            return {"sent": False, "reason": str(e)}


def _digest_subject(
    report: dict,
    domains: list | None,
    user_location: str | None,
    weekly: bool = False,
) -> str:
    """Per-recipient email subject: job count + domains + location.

    Members see e.g. "🎯 4 security jobs in Bangalore" instead of the
    generic "Daily Report" — the inbox line already tells them whether
    the digest is worth opening.
    """
    count = len(report.get("new_jobs") or [])
    domain_txt = ", ".join(domains) if domains else "matching"
    loc_txt = (user_location or "").strip() or DEFAULT_LOCATION
    if weekly:
        return f"📅 {count} jobs this week ({domain_txt})"
    return f"🎯 {count} {domain_txt} jobs in {loc_txt}"


async def _deliver_alert(
    manager,
    channels: list | None,
    report: dict,
    session,
    domains: list | None = None,
    subject: str = "InternTrack Daily Alert",
    weekly: bool = False,
    user=None,
) -> dict:
    """Send an alert through the given channels (None = all configured).

    Emails get the full single digest message. Telegram gets the digest
    split into small chunks, each with inline **Apply** buttons linking to
    the job listing. When ``user`` is given, match % is computed from that
    user's own resume (``user.id``) and delivery is routed to the user's
    email / Telegram chat instead of the shared defaults. Returns the
    per-channel delivery results.
    """
    title = "📅 Weekly Digest" if weekly else "📊 Daily Report"
    targets = channels if channels is not None else manager.get_configured_channels()
    user_id = getattr(user, "id", None)
    recipient = None
    if user is not None:
        recipient = {
            "email": getattr(user, "email", None),
            "telegram_chat_id": getattr(user, "telegram_chat_id", None),
            "phone_number": getattr(user, "phone_number", None),
        }
    # Dashboard links (and the "manage alerts" footer) are owner-only:
    # members asked for job digests, not an account/dashboard to manage.
    # The legacy path (``user`` is None — the default ``user1`` account)
    # is the owner's own digest, so it keeps the link.
    show_dashboard_link = True
    if user is not None:
        try:
            owner_email = await _owner_email(session)
            member_email = str(getattr(user, "email", "") or "").strip().lower()
            show_dashboard_link = bool(
                owner_email and member_email == str(owner_email).strip().lower()
            )
        except Exception:  # noqa: BLE001, S110 - best-effort gate
            show_dashboard_link = False
    results: dict = {}
    # Preferred-location split (📍 Your area / 🌍 Other locations). Discovery
    # already searches the default location when the user hasn't set one, so
    # the digest must render the split with the same fallback — otherwise the
    # default user never sees the location split at all.
    user_location = (getattr(user, "location", None) or "").strip() or DEFAULT_LOCATION
    # Remote / WFH / "anywhere" listings count as "your area" when the user
    # opted in (include_remote default True). Loaded best-effort so a failed
    # prefs read never breaks delivery.
    include_remote = True
    if user is not None:
        try:
            _prefs = await _load_alert_preferences(
                session,
                user_id=getattr(user, "id", "") or "",
            )
            include_remote = bool(_prefs.get("include_remote", True))
        except Exception:  # noqa: BLE001, S110 - best-effort
            pass
    # The weekly email closes with a team snapshot (members + your referrals).
    # A new dict (not mutation) so the caller's report stays untouched.
    if weekly:
        team = await _team_digest_stats(
            session,
            getattr(user, "email", None),
        )
        if team:
            report = {**report, "team": team}
    # Users with instant Telegram alerts on get the same new jobs pinged
    # instantly, so the digest skips Telegram for them (email still covers
    # the full digest) — otherwise every job would arrive twice on Telegram.
    # Only a saved prefs row with ``instant_alerts: True`` skips Telegram: a
    # failed/absent load (empty dict) keeps the digest Telegram as before.
    if user is not None and getattr(user, "telegram_chat_id", None):
        try:
            prefs = await _load_alert_preferences(
                session,
                user_id=getattr(user, "id", "") or "",
            )
            if prefs.get("instant_alerts") is True:
                targets = [c for c in targets if c != "telegram"]
        except Exception:  # noqa: BLE001, S110 - best-effort dedup
            pass
    non_telegram = [c for c in targets if c != "telegram"]
    email_targets = [c for c in non_telegram if c == "email"]
    text_targets = [c for c in non_telegram if c != "email"]
    if email_targets:
        # Email gets the styled HTML digest; other text channels stay plain.
        html = await build_daily_report_html(
            report,
            session,
            domains=domains,
            title=title,
            user_id=user_id,
            user_location=user_location,
            include_remote=include_remote,
            weekly=weekly,
            show_dashboard_link=show_dashboard_link,
        )
        if recipient:
            results.update(
                await manager.notify(
                    email_targets, html, subject=subject, recipient=recipient
                )
            )
        else:
            results.update(await manager.notify(email_targets, html, subject=subject))
        # One quick retry for transient SMTP/relay failures (a busy relay or
        # a blip is common; the failure ping to the owner should only fire
        # after the retry also fails). Delivered emails skip the retry.
        if results.get("email") is False:
            await asyncio.sleep(EMAIL_RETRY_DELAY_SECONDS)
            if recipient:
                results.update(
                    await manager.notify(
                        email_targets, html, subject=subject, recipient=recipient
                    )
                )
            else:
                results.update(
                    await manager.notify(email_targets, html, subject=subject)
                )
    if text_targets:
        message = await build_daily_report_message(
            report,
            session,
            domains=domains,
            title=title,
            user_id=user_id,
            user_location=user_location,
            include_remote=include_remote,
            weekly=weekly,
        )
        if recipient:
            results.update(
                await manager.notify(
                    text_targets, message, subject=subject, recipient=recipient
                )
            )
        else:
            results.update(await manager.notify(text_targets, message, subject=subject))
    if "telegram" in targets:
        chunks = await build_alert_chunks(
            report,
            session,
            domains=domains,
            weekly=weekly,
            user_id=user_id,
            user_location=user_location,
            include_remote=include_remote,
            show_dashboard_link=show_dashboard_link,
        )
        # Every chunk must deliver for the send to count as delivered.
        telegram_ok = True
        for text, buttons in chunks:
            if recipient:
                chunk_results = await manager.notify(
                    ["telegram"],
                    text,
                    subject=subject,
                    buttons=buttons,
                    recipient=recipient,
                )
            else:
                chunk_results = await manager.notify(
                    ["telegram"], text, subject=subject, buttons=buttons
                )
            telegram_ok = telegram_ok and bool(chunk_results.get("telegram", False))
        results["telegram"] = telegram_ok
    return results


async def _send_instant_alerts(session, saved_jobs: list) -> dict:
    """Ping users on Telegram the moment a high-match job is discovered.

    For every enabled account with ``instant_alerts`` on and a Telegram chat
    ID, each newly saved job is checked against the user's saved domains,
    preferred location and resume match threshold. Matching jobs are sent in
    one compact Telegram message with Apply buttons routed to that user's own
    chat. Deliberately Telegram-only — email stays on the scheduled digest —
    and never raises: a broken chat or DB never blocks discovery.

    Returns ``{user_id: job_count}`` for matched sends (for logging).
    """
    if not saved_jobs:
        return {}
    sent: dict = {}
    try:
        targets = await _enabled_alert_targets(session)
    except Exception:  # noqa: BLE001 - best-effort pings
        return {}
    for target in targets:
        user_id = target.get("user_id")
        prefs = target.get("prefs") or {}
        user = target.get("user")
        if not user_id or not prefs.get("instant_alerts", True):
            continue
        if _alerts_paused(prefs):
            continue
        chat_id = getattr(user, "telegram_chat_id", None)
        if not chat_id:
            continue
        try:
            resume_skills = await _latest_resume_skill_names(session, user_id=user_id)
            domains = prefs.get("domains") or []
            min_score = prefs.get("min_match_score")
            include_remote = bool(prefs.get("include_remote", True))
            experience_levels = prefs.get("experience_levels") or []
            loc_lower = (getattr(user, "location", None) or "").strip().lower()
            from interntrack.utils.helpers import job_experience_ok

            matches = []
            for job in saved_jobs:
                title = str(getattr(job, "title", "") or "")
                tags = list(getattr(job, "tags", None) or [])
                job_domain = classify_domain(title, tags)
                if domains and job_domain not in domains:
                    continue
                if experience_levels and not job_experience_ok(job, experience_levels):
                    continue
                job_loc = str(getattr(job, "location", None) or "").lower()
                if loc_lower and not _location_allows(
                    job_loc,
                    loc_lower,
                    include_remote,
                ):
                    continue
                job_dict = {
                    "id": str(getattr(job, "id", "") or ""),
                    "title": title,
                    "company": str(getattr(job, "company", "") or ""),
                    "location": getattr(job, "location", None),
                    "url": getattr(job, "url", None),
                    "description": getattr(job, "description", None),
                    "required_skills": list(
                        getattr(job, "required_skills", None) or []
                    ),
                    "preferred_skills": list(
                        getattr(job, "preferred_skills", None) or []
                    ),
                    "tags": tags,
                }
                score = _job_match_score(resume_skills, job_dict)
                # Unknown match % passes (same as the digest); a known score
                # below the threshold is dropped.
                if min_score and score is not None and (score or 0) < min_score:
                    continue
                matches.append((score, job_dict))
            if not matches:
                continue
            matches.sort(key=lambda item: -(item[0] or 0.0))
            lines = [
                (
                    f"⚡ <b>New match for you!</b> "
                    f"({len(matches)} job{'s' if len(matches) != 1 else ''} "
                    f"just discovered)"
                )
            ]
            buttons: list[tuple[str, str]] = []
            for score, job in matches[:5]:
                score_txt = f" · {score:.0f}% match" if score is not None else ""
                location = job.get("location") or "Remote"
                lines.append(
                    f"🔹 <b>{_esc(job['title'])}</b> @ {_esc(job['company'])}"
                    f" · {_esc(location)}{score_txt}"
                )
                desc = _job_desc_snippet(job_dict)
                if desc:
                    lines.append(f"   📝 {_esc(desc)}")
                url = str(job.get("url") or "")
                if url:
                    job_title = str(job["title"] or "Job").strip()[:60]
                    buttons.append((f"✅ Apply — {job_title}", url))
            if len(matches) > 5:
                lines.append(f"…and {len(matches) - 5} more on the dashboard.")
            message = "\n".join(lines)
            manager = NotificationManager(session)
            results = await manager.notify(
                ["telegram"],
                message,
                subject="⚡ New job match",
                buttons=buttons or None,
                recipient={"telegram_chat_id": chat_id},
            )
            if results.get("telegram"):
                sent[user_id] = len(matches)
        except Exception:  # noqa: BLE001, S112 - one user must not block the rest
            continue
    return sent


async def _send_closing_soon_sweep(session) -> dict:
    """One '🚨 Closing soon' alert per user for jobs expiring within 48h.

    Matches each enabled account's saved domains (and preferred location,
    with the remote opt-in) against jobs closing in the next 2 days and
    sends ONE digest-style message per user with Apply buttons. Each job is
    flagged exactly once per user — sent job ids are kept in
    ``AlertPreferences.closing_soon_sent`` (auto-added to live tables by
    ``_sync_missing_columns``) and pruned once the job has closed. Never
    raises; returns ``{user_id: job_count}`` for logging.
    """
    sent: dict = {}
    try:
        from sqlalchemy import select

        from interntrack.domain.models import AlertPreferences
        from interntrack.repositories.job_repository import JobRepository
        from interntrack.utils.helpers import job_experience_ok, location_allows

        owner_email = await _owner_email(session)
        api_base = ""
        try:
            from interntrack.config import get_settings

            api_base = (get_settings().api_base_url or "").strip().rstrip("/")
        except Exception:  # noqa: BLE001, S110 - best-effort
            api_base = ""
        targets = await _enabled_alert_targets(session)
        if not targets:
            return {}
        closing = await JobRepository(session).get_closing_soon(days=2)
        if not closing:
            return {}
        closing_list: list[dict] = [
            {
                "id": str(j.id),
                "title": str(j.title or "Untitled"),
                "company": str(j.company or "Unknown"),
                "location": str(j.location or "Remote"),
                "url": str(j.url or ""),
                "expires_at": j.expires_at.isoformat() if j.expires_at else None,
                "experience_level": str(getattr(j, "experience_level", None) or ""),
                "domain": classify_domain(
                    str(j.title or ""),
                    tags=list(getattr(j, "tags", None) or []),
                ),
            }
            for j in closing
        ]
        for target in targets:
            user_id = target.get("user_id")
            prefs = target.get("prefs") or {}
            user = target.get("user")
            if not user_id:
                continue
            if _alerts_paused(prefs):
                continue
            domains = prefs.get("domains") or []
            include_remote = bool(prefs.get("include_remote", True))
            experience_levels = prefs.get("experience_levels") or []
            user_loc = (
                (getattr(user, "location", None) or "").strip().lower() if user else ""
            )

            result = await session.execute(
                select(AlertPreferences).where(AlertPreferences.user_id == user_id)
            )
            pref = result.scalar_one_or_none()
            already = {
                str(x)
                for x in (getattr(pref, "closing_soon_sent", None) or [])
                if pref is not None
            }
            matches = [
                cj
                for cj in closing_list
                if str(cj["id"]) not in already
                and (not domains or cj["domain"] in domains)
                and (not experience_levels or job_experience_ok(cj, experience_levels))
                and (
                    not user_loc
                    or location_allows(
                        str(cj["location"] or "").lower(), user_loc, include_remote
                    )
                )
            ]
            if not matches:
                continue
            # Keep the history + dedup bookkeeping aligned with what is
            # actually rendered (the message caps at 5 jobs).
            matches = matches[:5]

            lines = ["🚨 <b>Closing soon — apply now!</b>", ""]
            buttons: list[tuple[str, str]] = []
            for cj in matches[:5]:
                closes = (cj["expires_at"] or "")[:10]
                lines.append(
                    f"🔹 <b>{cj['title']}</b> @ {cj['company']} · "
                    f"{cj['location']} · closes {closes}"
                )
                if cj["url"]:
                    buttons.append((f"✅ Apply — {cj['title'][:40]}", cj["url"]))
            manager = NotificationManager(session)
            channel_list = _without_telegram_for_members(
                prefs.get("channels")
                or manager.get_configured_channels()
                or ["email", "sms"],
                user,
                owner_email,
            )
            recipient = None
            if user is not None:
                recipient = {
                    "email": getattr(user, "email", None),
                    "telegram_chat_id": getattr(user, "telegram_chat_id", None),
                    "phone_number": getattr(user, "phone_number", None),
                }
            # Personalized subject: job count + the member's city (when
            # known), like the daily digest subjects.
            closing_subject = (
                f"🚨 {len(matches)} job{'s' if len(matches) != 1 else ''} closing soon"
            )
            if user_loc:
                closing_subject += f" in {user_loc.title()}"
            # Email members get the styled HTML cards (with signed
            # apply-tracking links); Telegram keeps the inline buttons.
            non_telegram = [c for c in channel_list if c != "telegram"]
            email_targets = [c for c in non_telegram if c == "email"]
            text_targets = [c for c in non_telegram if c != "email"]
            results: dict = {}
            if email_targets:
                results.update(
                    await manager.notify(
                        email_targets,
                        _closing_soon_html(matches, user_id, api_base),
                        subject=closing_subject,
                        recipient=recipient,
                    )
                )
            if text_targets:
                results.update(
                    await manager.notify(
                        text_targets,
                        "\n".join(lines),
                        subject=closing_subject,
                        buttons=buttons or None,
                        recipient=recipient,
                    )
                )
            await _record_alert_history(
                session,
                user_id=user_id,
                subject="🚨 Closing soon",
                channels=list(results.keys()),
                domains=domains or [],
                job_count=len(matches),
                results=results,
            )
            new_ids = [str(cj["id"]) for cj in matches]
            if pref is None:
                session.add(
                    AlertPreferences(
                        user_id=user_id, is_enabled=True, closing_soon_sent=new_ids
                    )
                )
            else:
                # Prune ids whose job has since closed (or vanished) so the
                # list never grows stale — only ids that are STILL closing
                # (or were just sent) are kept, newest last, capped at 50.
                closing_ids = {str(cj["id"]) for cj in closing_list}
                merged = list(dict.fromkeys((already & closing_ids) | set(new_ids)))[
                    -50:
                ]
                pref.closing_soon_sent = merged
            await session.commit()
            sent[user_id] = len(matches)
    except Exception as e:  # noqa: BLE001 - sweep must never break the app
        print(f"[{datetime.now(UTC)}] Closing-soon sweep failed: {e}")
    return sent


async def send_closing_soon_alerts() -> dict:
    """Scheduled wrapper: run the closing-soon sweep on its own session."""
    async with get_db_session() as session:
        return await _send_closing_soon_sweep(session)


def _status_links(
    api_base: str, user_id: str, application_id: str
) -> dict[str, str] | None:
    """Signed nudge status-update URLs (interview/rejected/offer), or None.

    Only when the deployment has an ``api_base_url`` and both ids are
    known — the same best-effort rule as the apply-tracking links.
    """
    if not api_base or not user_id or not application_id:
        return None
    from urllib.parse import quote

    from interntrack.utils.helpers import status_token

    base = api_base.strip().rstrip("/")
    out: dict[str, str] = {}
    for key in ("interview", "rejected", "offer"):
        token = status_token(str(user_id), str(application_id), key)
        out[key] = (
            f"{base}/api/v1/email/status?u={quote(str(user_id))}"
            f"&a={quote(str(application_id))}&s={key}&t={token}"
        )
    return out


def _follow_up_nudge_text(
    item: dict, status_links: dict[str, str] | None = None
) -> tuple[str, list[tuple[str, str]]]:
    """Message + buttons for one stale-application follow-up nudge.

    ``item`` carries application_id / job_title / company / job_url /
    days_since. Renders a short message with a copy-paste follow-up
    template the user can send the recruiter, plus a View-job button.
    When ``status_links`` is given, the message ends with one-click
    interview / rejected / offer links so email-only members can update
    their application without the dashboard. Pure and testable.
    """
    title = str(item.get("job_title") or "the role")
    company = str(item.get("company") or "the company")
    days = int(item.get("days_since") or 0)
    lines = [
        f"⏰ <b>Still waiting after {days} day{'s' if days != 1 else ''}?</b>",
        (
            f"You applied for <b>{_esc(title)}</b> @ {_esc(company)} and there "
            "has been no update since."
        ),
        "",
        "💬 A quick follow-up can revive it — try:",
        (
            f'"Hi {_esc(company)} team, I applied for the {_esc(title)} role '
            "recently and wanted to check in on the status. I am very excited "
            "about the opportunity and happy to provide any further details. "
            'Thank you!"'
        ),
        "",
    ]
    if status_links:
        lines.append(
            "⬇️ Update your status right from this email (no dashboard needed):"
        )
        lines.append(f"   🗓️ Interview → {_esc(status_links['interview'])}")
        lines.append(f"   ❌ Rejected → {_esc(status_links['rejected'])}")
        lines.append(f"   🎉 Offer → {_esc(status_links['offer'])}")
    else:
        lines.append("Update the status on your dashboard when you hear back.")
    buttons: list[tuple[str, str]] = []
    if item.get("job_url"):
        buttons.append(("🔗 View job", str(item["job_url"])))
    if status_links:
        for key, label in (
            ("interview", "🗓️ Interview"),
            ("rejected", "❌ Rejected"),
            ("offer", "🎉 Offer"),
        ):
            buttons.append((label, status_links[key]))
    return "\n".join(lines), buttons


async def _send_follow_up_nudges(session, days: int = 7) -> dict:
    """One follow-up nudge per user for applications stuck in 'applied'.

    Applications that have been sitting in the ``applied`` status for
    ``days``+ (no interview, no rejection, no offer) get a short nudge
    through the user's saved channels with a copy-paste follow-up
    template. Each application is nudged exactly once (``reminded``
    flag). Only enabled, non-paused accounts are pinged; the legacy
    ``user1`` default is skipped when accounts exist. Never raises;
    returns ``{user_id: count}`` for logging.
    """
    sent: dict = {}
    try:
        from sqlalchemy import select

        from interntrack.domain.enums import ApplicationStatus
        from interntrack.domain.models import Application, Job

        owner_email = await _owner_email(session)
        api_base = ""
        try:
            from interntrack.config import get_settings

            api_base = (get_settings().api_base_url or "").strip().rstrip("/")
        except Exception:  # noqa: BLE001, S110 - best-effort
            api_base = ""
        now = datetime.now(UTC).replace(tzinfo=None)
        cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        result = await session.execute(
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(
                Application.status == ApplicationStatus.APPLIED,
                Application.reminded.is_(False),
                Application.applied_at.isnot(None),
            )
        )
        rows = result.all()
        targets = await _enabled_alert_targets(session)
        by_user = {t["user_id"]: t for t in targets if t.get("user_id")}
        pending: list[dict] = []
        for app, job in rows:
            applied_at = getattr(app, "applied_at", None)
            if applied_at is None:
                continue
            stamp = applied_at.strftime("%Y-%m-%d %H:%M:%S")
            if stamp >= cutoff:
                continue
            pending.append(
                {
                    "application_id": str(getattr(app, "id", "") or ""),
                    "user_id": str(getattr(app, "user_id", "") or ""),
                    "job_title": getattr(job, "title", None) or "the role",
                    "company": getattr(job, "company", None) or "the company",
                    "job_url": getattr(job, "url", None) or "",
                    "days_since": max(1, (now - applied_at).days),
                }
            )
        if not pending:
            return sent
        for item in pending:
            uid = item["user_id"]
            target = by_user.get(uid)
            if not target:
                continue
            prefs = target.get("prefs") or {}
            if _alerts_paused(prefs):
                continue
            manager = NotificationManager(session)
            user = target.get("user")
            channel_list = _without_telegram_for_members(
                prefs.get("channels")
                or manager.get_configured_channels()
                or ["email", "sms"],
                user,
                owner_email,
            )
            status_links = _status_links(api_base, uid, item["application_id"])
            text, buttons = _follow_up_nudge_text(item, status_links)
            recipient = None
            if user is not None:
                recipient = {
                    "email": getattr(user, "email", None),
                    "telegram_chat_id": getattr(user, "telegram_chat_id", None),
                    "phone_number": getattr(user, "phone_number", None),
                }
            results = await manager.notify(
                channel_list,
                text,
                subject="⏰ Follow up on your application",
                buttons=buttons or None,
                recipient=recipient,
            )
            await _record_alert_history(
                session,
                user_id=uid,
                subject="⏰ Follow up on your application",
                channels=list(results.keys()),
                domains=prefs.get("domains") or [],
                job_count=1,
                results=results,
            )
            from sqlalchemy import update

            await session.execute(
                update(Application)
                .where(Application.id == item["application_id"])
                .values(reminded=True)
            )
            await session.commit()
            sent[uid] = sent.get(uid, 0) + 1
    except Exception as e:  # noqa: BLE001 - nudge must never break the app
        print(f"[{datetime.now(UTC)}] Follow-up nudges failed: {e}")
    return sent


async def send_follow_up_nudges() -> dict:
    """Scheduled wrapper: run the follow-up nudge sweep on its own session."""
    async with get_db_session() as session:
        return await _send_follow_up_nudges(session)


async def _interview_reminders_for(
    session,
    user_id: str,
    hours: int = 36,
) -> list[dict]:
    """Applications with an interview in the next ``hours``, not yet reminded.

    Returns compact dicts (title / company / job url / interview time /
    expected skills) joined from the application + its job, sorted soonest
    first. A reminder is only due once per application
    (``interview_reminder_sent_at`` is NULL). Never raises; ``[]`` on any
    problem.
    """
    try:
        from sqlalchemy import select

        from interntrack.domain.enums import ApplicationStatus
        from interntrack.domain.models import Application, Job

        now = datetime.now(UTC).replace(tzinfo=None)
        horizon = now + timedelta(hours=hours)
        result = await session.execute(
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(
                Application.user_id == user_id,
                Application.status == ApplicationStatus.INTERVIEW,
                Application.interview_at.isnot(None),
                Application.interview_at > now,
                Application.interview_at <= horizon,
                Application.interview_reminder_sent_at.is_(None),
            )
        )
        items: list[dict] = []
        for app, job in result.all():
            items.append(
                {
                    "application_id": str(getattr(app, "id", "") or ""),
                    "job_id": str(getattr(app, "job_id", "") or ""),
                    "job_title": getattr(job, "title", None) or "Interview",
                    "company": getattr(job, "company", None) or "Unknown",
                    "job_url": getattr(job, "url", None) or "",
                    "interview_at": getattr(app, "interview_at", None),
                    "location": getattr(job, "location", None) or "",
                    "skills": list(getattr(job, "required_skills", None) or [])[:5],
                }
            )
        items.sort(key=lambda x: (x["interview_at"] is None, x["interview_at"]))
        return items
    except Exception:  # noqa: BLE001 - reminders must never break the scheduler
        return []


def _interview_reminder_text(item: dict) -> tuple[str, list[tuple[str, str]]]:
    """Message + buttons for one interview reminder (pure, testable)."""
    when = item.get("interview_at")
    when_txt = ""
    if when:
        try:
            # Times are stored as naive UTC (the model coerces), so label
            # them rather than letting users read UTC as local time.
            when_txt = when.strftime("%a %d %b · %I:%M %p (UTC)")
        except Exception:  # noqa: BLE001 - best-effort time formatting
            when_txt = str(when)[:16]
    title = str(item.get("job_title") or "Interview")
    company = str(item.get("company") or "Unknown")
    lines = [f"🗓️ <b>Interview soon:</b> {title} @ {company}"]
    if when_txt:
        lines.append(f"⏰ {when_txt}")
    loc = str(item.get("location") or "")
    if loc and loc.lower() != "remote":
        lines.append(f"📍 {loc}")
    skills = item.get("skills") or []
    if skills:
        lines.append("🧠 They expect: " + ", ".join(str(s) for s in skills[:5]))
    lines.append("")
    lines.append("Good luck! Mark the interview done on your dashboard.")
    buttons: list[tuple[str, str]] = []
    if item.get("job_url"):
        buttons.append(("🔗 View job", str(item["job_url"])))
    cal = _calendar_link(title, company)
    if cal:
        buttons.append(("📅 Add to calendar", cal))
    return "\n".join(lines), buttons


async def _send_interview_reminders_for_user(
    session,
    user_id: str,
    prefs: dict,
    user,
    sent: dict,
) -> None:
    """Send '🗓️ Interview soon' pushes for one user's due interviews."""
    if not user_id or _alerts_paused(prefs):
        return
    items = await _interview_reminders_for(session, user_id)
    if not items:
        return
    manager = NotificationManager(session)
    owner_email = await _owner_email(session)
    channel_list = _without_telegram_for_members(
        prefs.get("channels") or manager.get_configured_channels() or ["email", "sms"],
        user,
        owner_email,
    )
    recipient = None
    if user is not None:
        recipient = {
            "email": getattr(user, "email", None),
            "telegram_chat_id": getattr(user, "telegram_chat_id", None),
            "phone_number": getattr(user, "phone_number", None),
        }
    from sqlalchemy import update

    from interntrack.domain.models import Application

    now = datetime.now(UTC).replace(tzinfo=None)
    for item in items[:3]:
        text, buttons = _interview_reminder_text(item)
        results = await manager.notify(
            channel_list,
            text,
            subject="🗓️ Interview soon",
            buttons=buttons or None,
            recipient=recipient,
        )
        await _record_alert_history(
            session,
            user_id=user_id,
            subject="🗓️ Interview soon",
            channels=list(results.keys()),
            domains=prefs.get("domains") or [],
            job_count=1,
            results=results,
        )
        # Mark reminded even if delivery hiccuped — never spam every run.
        # Commit per item so a later failure can never roll back an
        # already-sent reminder and cause a duplicate on the next run.
        await session.execute(
            update(Application)
            .where(Application.id == item["application_id"])
            .values(interview_reminder_sent_at=now)
        )
        await session.commit()
    sent[user_id] = len(items[:3])


async def _send_interview_reminders(session) -> dict:
    """One '🗓️ Interview soon' push per due interview for every user.

    Interviews scheduled within the next 36 hours get a short notification
    through the user's saved channels (View job + Add to calendar buttons)
    exactly once. Never raises; returns ``{user_id: count}`` for logging.
    """
    sent: dict = {}
    try:
        targets = await _enabled_alert_targets(session)
        if not targets:
            # Legacy single-user path before accounts exist.
            prefs = await _load_alert_preferences(session)
            if prefs.get("is_enabled") is not False:
                await _send_interview_reminders_for_user(
                    session, DEFAULT_ALERT_USER, prefs, None, sent
                )
            return sent
        for target in targets:
            await _send_interview_reminders_for_user(
                session,
                target.get("user_id") or "",
                target.get("prefs") or {},
                target.get("user"),
                sent,
            )
    except Exception as e:  # noqa: BLE001 - sweep must never break the app
        print(f"[{datetime.now(UTC)}] Interview reminders failed: {e}")
    return sent


async def send_interview_reminders() -> dict:
    """Scheduled wrapper: run the interview-reminder sweep on its own session."""
    async with get_db_session() as session:
        return await _send_interview_reminders(session)


async def _enabled_alert_targets(session) -> list[dict]:
    """Every account with alerts enabled, as ``{user_id, prefs, user}``.

    ``prefs`` is the loaded alert-preferences dict for that user, ``user``
    is the matching ``User`` profile (``None`` for the legacy ``user1``
    default before any accounts exist). Never raises: an empty list makes
    callers fall back to the single-user path (which keeps every existing
    test and pre-account deployment working unchanged).
    """
    try:
        from sqlalchemy import select

        from interntrack.domain.models import AlertPreferences, User

        result = await session.execute(
            select(AlertPreferences).where(AlertPreferences.is_enabled.is_(True))
        )
        rows = list(result.scalars().all())
        targets: list[dict] = []
        for pref in rows:
            user_id = str(getattr(pref, "user_id", "") or "")
            if not user_id:
                continue
            prefs = await _load_alert_preferences(session, user_id=user_id)
            user = None
            if user_id != DEFAULT_ALERT_USER:
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                candidate = user_result.scalar_one_or_none()
                if isinstance(candidate, User):
                    user = candidate
            targets.append({"user_id": user_id, "prefs": prefs, "user": user})
        return targets
    except Exception:
        return []


async def _user_profile(session, user_id: str):
    """Load a User profile by id, or None when missing. Never raises.

    Only a genuine :class:`User` row is returned — a mocked/failed session
    that yields anything else is treated as "no profile" so callers fall
    back to the shared configured channels instead of routing to junk.
    """
    try:
        from sqlalchemy import select

        from interntrack.domain.models import User

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if isinstance(user, User):
            return user
    except Exception:
        return None
    return None


async def _owner_email(session) -> str | None:
    """Email of the team owner (TEAM_OWNER_EMAIL, else first-registered).

    Same rule as the owner failure pings and the weekly team recap. Never
    raises — channel building must survive a broken prefs read.
    """
    try:
        from sqlalchemy import select

        from interntrack.config import get_settings
        from interntrack.domain.models import User

        result = await session.execute(select(User).order_by(User.created_at.asc()))
        users = list(result.scalars().all())
        if not users:
            return None
        override = str(get_settings().team_owner_email or "").strip().lower()
        if override:
            for u in users:
                if str(getattr(u, "email", "") or "").strip().lower() == override:
                    return str(u.email or "") or None
        return str(users[0].email or "") or None
    except Exception:  # noqa: BLE001, S110 - best-effort
        return None


def _without_telegram_for_members(
    channels: list | None,
    user,
    owner_email: str | None,
) -> list:
    """Members get email + SMS only; Telegram stays for the owner.

    Product decision: SMS is the member notification channel for now —
    Telegram/others are added for a member only when explicitly enabled.
    The owner's own digests keep Telegram. Returns a new list, never
    mutates the caller's.
    """
    if not channels:
        return list(channels or [])
    if owner_email and user is not None:
        email = str(getattr(user, "email", "") or "").strip().lower()
        if email == owner_email.strip().lower():
            return list(channels)
    return [c for c in channels if c != "telegram"]


async def _send_alert_for(
    session,
    user_id: str,
    prefs: dict,
    user=None,
    weekly: bool = False,
) -> None:
    """Build and deliver one user's daily or weekly digest.

    Honors the saved domains / channels / min match %, advances that user's
    no-duplicates window (daily) or recaps the whole week (weekly),
    delivers to the user's own channels and records the send in that user's
    history.
    """
    domains = prefs.get("domains") or None
    # Each user's digest is scoped to *their* city (synonym-aware), so two
    # accounts on the same domain never see each other's locations. The
    # legacy default user (no profile) falls back to DEFAULT_LOCATION so
    # their digest is city-scoped too, not every-city.
    user_location = (
        (getattr(user, "location", None) or "").strip() or DEFAULT_LOCATION or None
    )
    include_remote = bool(prefs.get("include_remote", True))
    service = ReportService(session)
    if weekly:
        # Whole-week recap: span 7 days so every listing of the week is
        # recapped on Mondays, regardless of the daily no-duplicates window.
        since: datetime | None = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            days=7
        )
    else:
        since = prefs.get("last_alert_at")
    report = await service.generate_daily_report(
        domains=domains,
        min_match_score=prefs.get("min_match_score"),
        since=since,
        location=user_location,
        include_remote=include_remote,
        experience_levels=prefs.get("experience_levels") or None,
    )
    if weekly:
        report["report_type"] = "weekly"
        # The week's most-engaged jobs (apps + bookmarks + views) lead the
        # recap. Defensive: a stats failure must never break the digest.
        report["top_engaged"] = await _weekly_top_engaged(session)
    # Per-user digest smartening: salary target + keyword highlights ride
    # along on the report so every builder sees the same numbers.
    report["target_salary"] = prefs.get("min_salary") or None
    report["keywords"] = list(prefs.get("keywords") or [])
    # Fresher-only members get the 🎓 Internships & fresher roles highlight
    # (experience_levels like ["entry", "junior"] mean fresher-only).
    _levels = prefs.get("experience_levels") or []
    report["fresher_only"] = bool(_levels) and not any(
        lvl in ("mid", "senior", "lead", "executive") for lvl in _levels
    )

    await _mark_alert_sent(session, user_id)
    if not (report.get("new_jobs") or []):
        kind = "Weekly digest" if weekly else "Daily report"
        print(f"[{datetime.now(UTC)}] {kind} for {user_id}: no new jobs in window")
        return

    manager = NotificationManager(session)
    subject = _digest_subject(report, domains, user_location, weekly=weekly)
    # Members are email + SMS only for now (no Telegram) — the owner keeps
    # Telegram on their own digest.
    owner_email = await _owner_email(session)
    member_channels = _without_telegram_for_members(
        prefs.get("channels") or None,
        user,
        owner_email,
    )
    results = await _deliver_alert(
        manager,
        member_channels or None,
        report,
        session,
        domains=domains,
        subject=subject,
        weekly=weekly,
        user=user,
    )
    # Owner failure alerts: when a member's email channel was attempted but
    # reports delivered=False, ping the owner on Telegram so a silent SMTP /
    # Resend outage never leaves members without digests. Best-effort — the
    # digest pipeline itself is unaffected by a failed ping.
    try:
        attempted = prefs.get("channels") or manager.get_configured_channels()
        if "email" in attempted and results.get("email") is False:
            member_name = str(getattr(user, "name", "") or "") if user else ""
            member_email = str(getattr(user, "email", "") or "") if user else ""
            fallback_id = user_id if user_id != DEFAULT_ALERT_USER else ""
            await _notify_owner_of_failure(
                session,
                member_name=member_name,
                member_email=member_email or fallback_id,
                channel="email",
                domain_label=", ".join(domains or []),
            )
    except Exception:  # noqa: BLE001, S110 - failure pings never break digests
        pass

    # Compact snapshot of the jobs that were actually sent (with match %), so
    # the dashboard history shows the real digest content, not just a count.
    # Built defensively: history must never be lost to a scoring hiccup after
    # the mail was already delivered.
    sent_jobs: list = []
    try:
        resume_skills = await _latest_resume_skill_names(session, user_id=user_id)
        sent_jobs = [
            {
                "title": job.get("title"),
                "company": job.get("company"),
                "location": job.get("location"),
                "url": job.get("url"),
                "domain": job.get("domain") or "other",
                "match_score": _job_match_score(resume_skills, job),
                "source": job.get("source"),
                "posted_at": job.get("posted_at"),
            }
            for job in (report.get("new_jobs") or [])
        ]
    except Exception:  # noqa: BLE001, S110 - history must never break
        sent_jobs = []
    await _record_alert_history(
        session,
        user_id=user_id,
        subject=subject,
        channels=prefs.get("channels") or list(results.keys()),
        domains=domains or [],
        job_count=len(report.get("new_jobs") or []),
        results=results,
        jobs=sent_jobs,
    )


async def _weekly_top_engaged(session, days: int = 7, limit: int = 5) -> list[dict]:
    """Most-engaged jobs of the last N days, for the weekly digest.

    Delegates to :meth:`JobRepository.get_most_engaged` (the same single
    source of truth the weekly API endpoint uses) so the ranking formula
    can never drift between the two. Never raises.
    """
    try:
        from interntrack.repositories.job_repository import JobRepository

        return await JobRepository(session).get_most_engaged(days=days, limit=limit)
    except Exception:  # noqa: BLE001 - never break the weekly digest
        return []


async def _top_companies_near(
    session,
    user_location: str | None = None,
    include_remote: bool = True,
    days: int = 7,
    limit: int = 6,
) -> list[tuple[str, int, str]]:
    """Hiring companies near a user's city, ranked by recent postings.

    Counts active jobs from the last ``days`` days whose location matches
    the user's preferred city (synonym-aware, remote opt-in), grouped by
    company — a "who is hiring around me right now" market snapshot for
    the daily email, even on days with few new matches. Each entry is
    ``(company, job_count, salary_range)`` where the salary range is the
    median band (e.g. ``₹8–12 LPA``) of that company's posted roles, or
    ``""`` when none carry a salary. ``Unknown`` companies are skipped.
    Never raises; ``[]`` on any problem.
    """
    try:
        from statistics import median

        from interntrack.repositories.job_repository import JobRepository
        from interntrack.utils.helpers import location_allows, salary_band_txt

        jobs = await JobRepository(session).get_recent_jobs(days=days)
        loc_lower = (user_location or "").strip().lower()
        per_company: dict[str, dict] = {}
        for job in jobs:
            if not getattr(job, "is_active", True):
                continue
            company = str(getattr(job, "company", "") or "").strip()
            if not company or company.lower() == "unknown":
                continue
            if loc_lower and not location_allows(
                str(getattr(job, "location", "") or "").lower(),
                loc_lower,
                include_remote=include_remote,
            ):
                continue
            entry = per_company.setdefault(company, {"count": 0, "min": [], "max": []})
            entry["count"] += 1
            if getattr(job, "salary_min", None) is not None:
                entry["min"].append(float(job.salary_min))
            if getattr(job, "salary_max", None) is not None:
                entry["max"].append(float(job.salary_max))
        out: list[tuple[str, int, str]] = []
        for company, entry in sorted(
            per_company.items(), key=lambda kv: kv[1]["count"], reverse=True
        )[:limit]:
            low = median(entry["min"]) if entry["min"] else None
            high = median(entry["max"]) if entry["max"] else None
            out.append((company, entry["count"], salary_band_txt(low, high)))
        return out
    except Exception:  # noqa: BLE001 - never break the digest
        return []


async def _fresher_roles(
    report: dict,
    session,
    domains: list | None = None,
    user_id: str | None = None,
    limit: int = 3,
) -> list[dict]:
    """Fresher/entry/intern roles in today's jobs for a fresher-only user.

    Re-uses the digest's own scored sections so the highlighted roles are
    exactly the ones already shown (never anything new or duplicated) —
    the freshest entry-level postings across the user's domains, capped
    at ``limit``. Returns ``[]`` when the user isn't fresher-only or no
    fresher roles exist. Never raises.
    """
    try:
        sections = await _score_and_group_jobs(
            report, session, domains, user_id=user_id
        )
        fresher = [
            job
            for _domain, items in sections
            for _score, job in items
            if _job_fresher_rank(job) == 0
        ]
        return fresher[:limit]
    except Exception:  # noqa: BLE001 - never break the digest
        return []


async def _weekly_skill_gap(
    session,
    sections,
    user_id: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Skills the weekly digest's jobs expect but the resume lacks, ranked.

    Flattens the scored ``(domain, [(score, job), ...])`` sections (the
    same jobs shown in the digest), compares each job's expected skills
    against the user's latest resume skills, and returns the missing ones
    ranked by how many jobs want them — the digest counterpart of the My
    Matches skills-gap panel. Never raises.
    """
    try:
        if not sections:
            return []
        resume_skills = await _latest_resume_skill_names(session, user_id=user_id)
        if not resume_skills:
            return []
        jobs = [job for _domain, items in sections for _score, job in items]
        return _skill_gap_counts(resume_skills, jobs, limit=limit)
    except Exception:  # noqa: BLE001 - the digest must never break
        return []


# Digest domain -> salary-benchmark domain (the benchmarks use coarser
# buckets: development / devops / design / security / data).
_DIGEST_SALARY_DOMAINS = {
    "security": "security",
    "data": "data",
    "frontend": "development",
    "coding": "development",
    "design": "design",
    # govt intentionally unmapped: salary benchmarks have no govt bucket,
    # so a govt-only member simply gets no benchmark line (cleaner than a
    # misleading private-sector number).
}


async def _weekly_salary_insight(session, domains, user_location) -> str | None:
    """One-line median-pay insight for the weekly digest, or ``None``.

    Looks up the live (domain, city) benchmark via the shared
    ``salary_benchmark_for`` helper (same numbers as the dashboard's
    salary chips) and formats a compact ``💰 Median … `` line. Never
    raises.
    """
    try:
        from interntrack.api.v1.salary_insights import salary_benchmark_for

        city = ""
        if user_location:
            city = str(user_location).split(",")[0].strip()
        # Security-first: a security-minded user whose prefs also list
        # coding should see security pay, not the first domain with data.
        for domain in sorted((domains or []), key=lambda d: d != "security"):
            mapped = _DIGEST_SALARY_DOMAINS.get(domain)
            if not mapped:
                continue
            row = await salary_benchmark_for(session, mapped, city)
            if not row:
                continue
            med = int(row.get("median") or 0)
            if not med:
                continue
            low = int(med * 0.75)
            high = int(med * 1.25)
            # Scale/symbol from the row's authoritative currency field,
            # with a magnitude fallback when it is missing.
            currency = str(row.get("currency") or "").upper()
            if currency == "INR" or med >= 100000:  # INR scale: 8.0M -> 8.0L
                low_s, high_s = f"{low / 100000:.1f}L", f"{high / 100000:.1f}L"
                symbol = "₹"
            else:  # USD scale
                low_s, high_s = f"{low // 1000}k", f"{high // 1000}k"
                symbol = "$"
            count = int(row.get("count") or 0)
            city_name = row.get("city") or city or "India"
            line = (
                f"💰 Median {mapped} pay in {city_name}: "
                f"{symbol}{low_s}–{symbol}{high_s}"
            )
            if count:
                line += f" (from {count} live postings)"
            return line
    except Exception:  # noqa: BLE001 - salary insight must never break the digest
        return None
    return None


_WEEK_STATUS_LABELS = (
    ("applied", "applied", "applied"),
    ("interview", "interview", "interviews"),
    ("assessment", "assessment", "assessments"),
    ("offer", "offer", "offers"),
    ("joined", "joined", "joined"),
    ("rejected", "rejection", "rejections"),
)


def _week_status_label(status: str, count: int) -> str:
    """Singular/plural label for an application status count."""
    for key, singular, plural in _WEEK_STATUS_LABELS:
        if key == status:
            return singular if count == 1 else plural
    return status


def _week_stats_parts(counts: dict) -> list[str]:
    """Human labels for non-zero application status counts (text/SMS)."""
    parts: list[str] = []
    for status, _, _ in _WEEK_STATUS_LABELS:
        count = int(counts.get(status, 0))
        if count:
            parts.append(f"{count} {_week_status_label(status, count)}")
    return parts


async def _week_application_stats(
    session,
    user_id: str,
    days: int = 7,
) -> dict:
    """Applications created in the last ``days`` for a user, by current status.

    Powers the weekly digest's "Your week in applications" block so users
    see how their pipeline moved. Never raises; returns ``{}`` when there
    is nothing to report.
    """
    try:
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import select

        from interntrack.domain.models import Application

        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
        result = await session.execute(
            select(Application).where(
                Application.user_id == user_id,
                Application.created_at >= since,
            )
        )
        status_counts: dict[str, int] = {}
        for app in result.scalars().all():
            status = str(getattr(app, "status", "") or "saved").strip().lower()
            status_counts[status] = status_counts.get(status, 0) + 1
        total = sum(status_counts.values())
        if not total:
            return {}
        return {"total": total, "status_counts": status_counts, "days": days}
    except Exception:  # noqa: BLE001 - stats must never break the digest
        return {}


async def _record_match_snapshot(
    session,
    user_id: str,
    domains: list | None = None,
    user_location: str | None = None,
    include_remote: bool = True,
) -> dict | None:
    """Snapshot today's average resume-match % across recent active jobs.

    Scores up to 150 recent active jobs against the user's resume (scoped
    to their domains and, like the digest, their city when configured) and
    upserts one ``MatchSnapshot`` row per ``(user_id, day)``. Never
    raises; returns the snapshot dict or ``None`` when there is no resume
    / too few scored jobs (fewer than 3).
    """
    try:
        from sqlalchemy import select

        from interntrack.domain.models import Job, MatchSnapshot

        resume_skills = await _latest_resume_skill_names(session, user_id=user_id)
        if not resume_skills:
            return None
        user_loc_lower = str(user_location or "").split(",")[0].strip().lower() or None
        result = await session.execute(
            select(Job)
            .where(Job.is_active.is_(True))
            .order_by(Job.posted_at.desc())
            .limit(150)
        )
        scores: list[float] = []
        for job in result.scalars().all():
            job_dict = {
                "id": str(getattr(job, "id", "") or ""),
                "title": getattr(job, "title", None),
                "company": getattr(job, "company", None),
                "required_skills": list(getattr(job, "required_skills", None) or []),
                "preferred_skills": list(getattr(job, "preferred_skills", None) or []),
                "tags": list(getattr(job, "tags", None) or []),
            }
            if domains:
                job_domain = str(getattr(job, "domain", "") or "").strip().lower()
                if not any(
                    d.strip().lower() in job_domain or job_domain in d.strip().lower()
                    for d in domains
                ):
                    continue
            if user_loc_lower:
                job_loc = str(getattr(job, "location", "") or "").strip().lower()
                if not _location_allows(
                    job_loc, user_loc_lower, include_remote=include_remote
                ):
                    continue
            score = _job_match_score(resume_skills, job_dict)
            if score is not None:
                scores.append(score)
        if len(scores) < 3:
            return None
        today = datetime.now(UTC).date()
        existing = await session.execute(
            select(MatchSnapshot).where(
                MatchSnapshot.user_id == user_id,
                MatchSnapshot.snapshot_date == today,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = MatchSnapshot(user_id=user_id, snapshot_date=today)
            session.add(row)
        row.avg_match = round(sum(scores) / len(scores), 1)
        row.min_match = round(min(scores), 1)
        row.max_match = round(max(scores), 1)
        row.jobs_scored = len(scores)
        await session.commit()
        return {
            "date": str(today),
            "avg_match": row.avg_match,
            "min_match": row.min_match,
            "max_match": row.max_match,
            "jobs_scored": row.jobs_scored,
        }
    except Exception:  # noqa: BLE001 - a snapshot failure must never break the scheduler
        return None


async def record_match_snapshots() -> int:
    """Daily resume-match % progress snapshots for every enabled user.

    Scheduler entry point (runs at 23:30 UTC): one snapshot row per user
    per day, so the dashboard chart and weekly trend line build up over
    time. Falls back to the legacy ``user1`` when no accounts exist.
    Returns how many snapshots were recorded.
    """
    async with get_db_session() as session:
        targets = await _enabled_alert_targets(session)
        if not targets:
            prefs = await _load_alert_preferences(session)
            snap = await _record_match_snapshot(
                session,
                DEFAULT_ALERT_USER,
                prefs.get("domains") or None,
            )
            return 1 if snap else 0
        recorded = 0
        for target in targets:
            if target["prefs"].get("is_enabled") is False:
                continue
            user_location = (
                (getattr(target.get("user"), "location", None) or "").strip()
                or DEFAULT_LOCATION
                or None
            )
            snap = await _record_match_snapshot(
                session,
                target["user_id"],
                target["prefs"].get("domains") or None,
                user_location=user_location,
                include_remote=bool(target["prefs"].get("include_remote", True)),
            )
            if snap:
                recorded += 1
        return recorded


async def generate_daily_report(weekly: bool = False):
    """Generate and send daily (or weekly) reports for every enabled user.

    Each registered account gets a personalized digest: their own domains,
    their own resume match %, their own no-duplicates window, delivered to
    their own email / Telegram and recorded in their own history. When no
    accounts exist yet, the legacy single-user path (``user1``) is used so
    pre-account deployments behave exactly as before.

    ``weekly=True`` (the Monday cron) sends the weekly digest instead: a
    7-day window, the week's most-engaged jobs, the team snapshot, and
    skips accounts that disabled ``weekly_enabled``.
    """
    async with get_db_session() as session:
        kind = "Weekly digest" if weekly else "Daily report"
        targets = await _enabled_alert_targets(session)
        if not targets:
            # Legacy single-user fallback (no registered accounts yet).
            prefs = await _load_alert_preferences(session)
            if prefs.get("is_enabled") is False:
                print(f"[{datetime.now(UTC)}] {kind} skipped — alerts disabled")
                return
            if weekly and prefs.get("weekly_enabled") is False:
                print(f"[{datetime.now(UTC)}] {kind} skipped — weekly digest disabled")
                return
            if _alerts_paused(prefs):
                print(f"[{datetime.now(UTC)}] {kind} skipped — alerts paused")
                return
            await _send_alert_for(
                session,
                DEFAULT_ALERT_USER,
                prefs,
                None,
                weekly=weekly,
            )
            return

        for target in targets:
            if target["prefs"].get("is_enabled") is False:
                print(
                    f"[{datetime.now(UTC)}] {kind} skipped for "
                    f"{target['user_id']} — alerts disabled"
                )
                continue
            if weekly and target["prefs"].get("weekly_enabled") is False:
                print(
                    f"[{datetime.now(UTC)}] {kind} skipped for "
                    f"{target['user_id']} — weekly digest disabled"
                )
                continue
            if _alerts_paused(target["prefs"]):
                print(
                    f"[{datetime.now(UTC)}] {kind} skipped for "
                    f"{target['user_id']} — alerts paused"
                )
                continue
            await _send_alert_for(
                session,
                target["user_id"],
                target["prefs"],
                target["user"],
                weekly=weekly,
            )


def format_daily_report(report: dict, title: str = "📊 Daily Report") -> str:
    """Format daily report summary counts for notification."""
    summary = report.get("summary", {})
    return (
        f"{title}\n\n"
        f"New Jobs: {summary.get('new_jobs', 0)}\n"
        f"New Applications: {summary.get('new_applications', 0)}\n"
        f"Total Applications: {summary.get('total_applications', 0)}"
    )


async def _latest_resume_skill_names(session, user_id: str | None = None) -> set | None:
    """Load a user's most recently parsed resume's skill names, if any.

    ``user_id`` scopes the lookup to that user's own resume so every user's
    match % is computed from *their* skills. ``None`` keeps the legacy
    behavior (most recent resume across all users) used by the default
    ``user1`` path before any accounts exist.
    """
    try:
        from sqlalchemy import select

        from cybershield.api.v1.resumes import _extract_skill_names
        from cybershield.domain.models import ResumeData

        query = select(ResumeData)
        if user_id:
            query = query.where(ResumeData.user_id == user_id)
        result = await session.execute(
            query.order_by(ResumeData.updated_at.desc()).limit(1)
        )
        resume = result.scalar_one_or_none()
        if resume:
            return _extract_skill_names(resume.skills)
    except Exception:
        return None
    return None


def _job_match_score(resume_skills: set | None, job: dict) -> float | None:
    """Match % for a job against the resume skills, or None when unknown."""
    if not resume_skills:
        return None
    try:
        from cybershield.api.v1.resumes import _calculate_job_match, _JobMatchData

        job_data = _JobMatchData(
            id=str(job.get("id") or ""),
            title=job.get("title"),
            company=job.get("company"),
            required_skills=job.get("required_skills") or [],
            preferred_skills=job.get("preferred_skills") or [],
            tags=job.get("tags") or [],
        )
        result = _calculate_job_match(resume_skills, job_data)
        if result.match_score is None:
            return None
        return float(result.match_score)
    except Exception:
        return None


def _calendar_link(title: str, company: str = "") -> str:
    """Google Calendar 'add event' template URL for an interview."""
    from urllib.parse import quote

    text = f"Interview: {title} {company}".strip()
    details = (
        f"Interview with {company} for {title} — "
        "open the job listing and update this slot with the actual time."
    ).strip()
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(text)}&details={quote(details)}"
    )


def _expiry_note(job: dict) -> str:
    """Expiry/status line for a job, or "" when it never expires."""
    if not job.get("is_active", True):
        return "   ❌ Expired / closed"
    expires_at = job.get("expires_at")
    if not expires_at:
        return ""
    try:
        exp = datetime.fromisoformat(str(expires_at))
        if exp.tzinfo is not None:
            exp = exp.astimezone(UTC).replace(tzinfo=None)
    except ValueError:
        return f"   ⏳ Expires: {expires_at}"
    now = datetime.now(UTC).replace(tzinfo=None)
    days_left = (exp - now).total_seconds() / 86400
    if days_left < 0:
        return "   ❌ Expired"
    if days_left <= 2:
        return f"   ⏳ Closing soon ({exp:%b %d})"
    return f"   ⏳ Expires: {exp:%b %d}"


_DOMAIN_ICONS = {
    "security": "🔐 Cybersecurity / VAPT / SOC",
    "frontend": "🖥️ Frontend / UI",
    "coding": "💻 Coding / Software",
    "data": "📊 Data & Analytics",
    "design": "🎨 Design",
    "marketing": "📣 Marketing / Sales",
    "finance": "💰 Finance / Admin",
    "govt": "🏛️ Govt / Sarkari / PSU",
    "other": "📦 Other",
}


def _age_badge(age: int) -> str:
    if age <= 0:
        return "🟢 today"
    if age == 1:
        return "🟡 1d ago"
    if age <= 3:
        return f"🟠 {age}d ago"
    return f"⚪ {age}d ago"


def _source_label(source) -> str:
    """Friendly board name for a job's source, or "" when unknown.

    Scrapers store their source name (``linkedin``, ``internshala_direct``,
    ``rss_feed``, ...) but the API can also emit enum strings
    (``JobSource.LINKEDIN``); both normalize to the same label so the email
    and Telegram digests can show "which board this job came from" without
    leaking internal enum names.
    """
    raw = str(source or "").strip()
    if not raw:
        return ""
    if "." in raw:
        raw = raw.rsplit(".", 1)[-1]
    key = raw.lower()
    labels = {
        "linkedin": "🔗 LinkedIn",
        "linkedin_india": "🔗 LinkedIn India",
        "linkedin_jobs_api": "🔗 LinkedIn API",
        "rss_feed": "📰 RSS feeds",
        "company": "🏢 Company careers",
        "greenhouse": "🏢 Company careers",
        "hackernews": "🐍 HackerNews",
        "internshala_direct": "🎓 Internshala",
        "internshala": "🎓 Internshala",
        "cutshort": "⚡ Cutshort",
        "wellfound": "🚀 Wellfound",
        "foundit": "🏢 Foundit",
        "naukri": "💼 Naukri",
        "apna": "🤝 Apna",
        "indeed": "🌐 Indeed",
        "indeed_india": "🌐 Indeed India",
        "glassdoor": "🏫 Glassdoor",
        "glassdoor_india": "🏫 Glassdoor India",
        "google_jobs": "🔎 Google Jobs",
        "timesjobs": "⏰ TimesJobs",
        "search_engine": "🔎 Search engine",
        "manual": "📥 Shared link",
        "unknown": "❓ Unknown",
    }
    return labels.get(key, key.replace("_", " ").title())


_INR_TO_USD = 83.0  # fixed rate used to compare USD postings to an INR target


def _salary_meets_target(job: dict, target: int | None) -> bool:
    """Whether a job's listed minimum salary meets the user's annual target.

    Both are treated as annual figures. USD postings are compared against
    an INR target using a fixed ₹83/$ rate so a ₹ target still catches
    remote/US roles; jobs with no salary data never "meet" the target.
    """
    try:
        if not target or float(target) <= 0:
            return False
        lo = job.get("salary_min")
        hi = job.get("salary_max")
        if lo is None and hi is None:
            return False
        if lo is not None:
            low = float(lo)
        elif hi is not None:
            low = float(hi)
        else:
            return False
        currency = str(job.get("salary_currency") or "USD").upper()
        if currency == "USD":
            low = low * _INR_TO_USD
        return low >= float(target)
    except Exception:  # noqa: BLE001 - a bad salary must never break the digest
        return False


def _salary_below_floor(job: dict, floor: int | None) -> bool:
    """True when a job's listed salary is definitively below the floor.

    Jobs with no salary data return False (kept) so freshers don't lose
    unknown-salary roles — only postings whose *known* salary is below the
    member's target are dropped. USD postings are compared against an INR
    floor with the same fixed rate ``_salary_meets_target`` uses.
    """
    try:
        if not floor or float(floor) <= 0:
            return False
        lo = job.get("salary_min")
        hi = job.get("salary_max")
        if lo is None and hi is None:
            return False
        if lo is not None:
            low = float(lo)
        elif hi is not None:
            low = float(hi)
        else:
            return False
        currency = str(job.get("salary_currency") or "USD").upper()
        if currency == "USD":
            low = low * _INR_TO_USD
        return low < float(floor)
    except Exception:  # noqa: BLE001 - a bad salary must never break the digest
        return False


def _keyword_hits(job: dict, keywords: list | None) -> list[str]:
    """Which of the user's highlight keywords match a job, capped at 3.

    Case-insensitive substring match against the title, description, tags
    and required skills. Never raises.
    """
    hits: list[str] = []
    if not keywords:
        return hits
    try:
        text = (
            str(job.get("title") or "") + " " + str(job.get("description") or "")
        ).lower()
        text += " " + " ".join(str(t).lower() for t in (job.get("tags") or []))
        text += " " + " ".join(
            str(s).lower() for s in (job.get("required_skills") or [])
        )
        for kw in keywords:
            kw_l = str(kw).strip().lower()
            if kw_l and kw_l in text and kw_l not in hits:
                hits.append(kw_l)
    except Exception:  # noqa: BLE001 - highlight logic must never break the digest
        return []
    return hits[:3]


def _job_lines(
    score,
    job: dict,
    target_salary: int | None = None,
    keywords: list | None = None,
    resume_skills: set | None = None,
) -> list[str]:
    """One job's notification lines (headline + apply link + expiry note)."""
    title = (job.get("title") or "Untitled")[:90]
    company = (job.get("company") or "").strip()
    url = job.get("url") or ""
    head = f"🎯 [{score:.0f}%] {title}" if score is not None else f"💼 {title}"
    if company and company.lower() != "unknown":
        head += f" — {company}"
    applied = job.get("is_applied", False)
    head += " ✅ Applied" if applied else " ⬜ Not applied"
    head += f" · {_age_badge(int(job.get('age_days', 0) or 0))}"
    lines = [head]
    salary = _salary_txt(job)
    if salary:
        lines.append(f"   💰 {salary}")
    exp_level = str(job.get("experience_level") or "").strip()
    if exp_level:
        lines.append(f"   🎓 {exp_level}")
    source = _source_label(job.get("source"))
    if source:
        lines.append(f"   🗂 {_esc(source)}")
    desc = _job_desc_snippet(job)
    if desc:
        # Escaped: Telegram sends with HTML parse mode and scraped
        # descriptions routinely contain <, >, & (and leftover tags).
        lines.append(f"   📝 {_esc(desc)}")
    skills = _skills_txt(job)
    if skills:
        lines.append(f"   🛠 Skills: {_esc(skills)}")
    checklist = _skills_checklist_lines(job, resume_skills)
    if checklist:
        lines.append("   " + "  ".join(checklist))
    if _salary_meets_target(job, target_salary):
        lines.append("   💰 Meets your target salary")
    hits = _keyword_hits(job, keywords)
    if hits:
        lines.append("   🔎 Matches: " + ", ".join(hits))
    signal = _hiring_signal(job)
    if signal:
        lines.append(f"   {_esc(signal)}")
    scam_flags = _scam_signals(job)
    if scam_flags:
        lines.append(
            f"   ⚠️ Review carefully — red flags: {_esc(', '.join(scam_flags))}"
        )
    if url:
        lines.append(f"   🔗 Apply: {url}")
    note = _expiry_note(job)
    if note:
        lines.append(note)
    return lines


_HTML_TAG_RE = re.compile(r"<[^>]*>")


def _job_desc_full(job: dict) -> str:
    """Clean, full job description text (no truncation).

    Same sanitizing as the snippet (raw HTML tags stripped, whitespace
    collapsed) but the whole posting is kept so the email card can offer
    an expandable \"What they expect\" block with the complete role
    description — no more cutting multi-paragraph postings mid-sentence.
    """
    desc = str(job.get("description") or "").strip()
    if not desc:
        return ""
    desc = _HTML_TAG_RE.sub(" ", desc)
    return " ".join(desc.split())


def _job_fresher_rank(job: dict) -> int:
    """0 for fresher/entry/intern roles, 1 otherwise — freshers sort first.

    Experience values stored by the scrapers are free-ish text
    (``fresher``/``intern``/``junior``/``senior``, sometimes with a year
    range), so the check is a loose substring match. Unknown/missing levels
    rank as non-fresher so explicit fresher roles always lead.
    """
    level = str(job.get("experience_level") or "").lower()
    return 0 if any(tok in level for tok in ("fresher", "entry", "intern")) else 1


def _job_desc_snippet(job: dict, limit: int = 180) -> str:
    """One-line job description snippet, or '' when the posting has none.

    Whitespace is collapsed, leftover HTML tags from sources that keep raw
    markup (greenhouse / notion boards, RSS) are stripped, and long
    descriptions are cut at a word-ish boundary with an ellipsis — so a
    multi-paragraph posting never bloats a Telegram message or email card
    with raw ``<p>`` / ``<strong>`` noise.
    """
    desc = str(job.get("description") or "").strip()
    if not desc:
        return ""
    desc = _HTML_TAG_RE.sub(" ", desc)
    desc = " ".join(desc.split())
    if len(desc) <= limit:
        return desc
    return desc[: limit - 1].rstrip() + "…"


# Tokens that show up in scraper-fed ``tags`` but are not skills —
# location names, employment types, urgency words. Kept out of the digest
# skills line so a fallback never renders "🛠 Skills: Bengaluru, Full-time".
_SKILL_NOISE = re.compile(
    r"\b(full[- ]time|part[- ]time|work[- ]from[- ]home|wfh|remote|hybrid|on[- ]site|"
    r"fresher|immediate|urgent|experience|years?|bangalore|bengaluru|chennai|"
    r"mumbai|delhi|noida|gurgaon|gurugram|hyderabad|pune|kolkata|coimbatore|"
    r"india|internship|intern|job|career|salary)\b",
    re.IGNORECASE,
)


def _skills_txt(job: dict, limit: int = 6) -> str:
    """Comma-joined list of skills the role expects ("what they expect").

    Prefers structured ``required_skills`` (backfilled from descriptions by
    the tag-backfill job); ``tags`` top up the list when a source only
    saves freeform tags. Entries are normalized (stripped, empties
    dropped) before the fallback applies, so a truthy-but-empty
    ``required_skills`` never suppresses real tags. Non-skill noise tokens
    (locations, full/part-time, hybrid/remote, fresher, …) are filtered,
    skills are deduped case-insensitively and capped at ``limit``.
    """
    raw = list(job.get("required_skills") or []) + list(job.get("tags") or [])
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        if len(out) >= limit:
            break
        skill = str(item or "").strip()
        if not skill or _SKILL_NOISE.search(skill):
            continue
        key = skill.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(skill)
    return ", ".join(out)


def _skill_gap_counts(resume_skills, jobs: list[dict], limit: int = 5) -> list[dict]:
    """Skills the digest's jobs expect but the resume lacks, ranked.

    Compares each job's expected skills (``required_skills``, ``tags``
    fallback) against the resume's skill names, counts how many jobs want
    each missing skill, and returns ``[{"skill", "count"}]`` sorted by
    count desc then alphabetically and capped at ``limit``. Non-skill
    noise is filtered with the same ``_SKILL_NOISE`` list the skills line
    uses, matching is case-insensitive, and a job is only counted once
    per skill.
    """
    if not resume_skills:
        return []
    have = {str(s).strip().lower() for s in resume_skills if str(s).strip()}
    if not have:
        return []
    counts: dict[str, int] = {}
    display: dict[str, str] = {}
    for job in jobs:
        seen_in_job: set[str] = set()
        for raw in (job.get("required_skills") or []) + (job.get("tags") or []):
            skill = str(raw or "").strip()
            if not skill or _SKILL_NOISE.search(skill):
                continue
            key = skill.lower()
            if key in have or key in seen_in_job:
                continue
            seen_in_job.add(key)
            display.setdefault(key, skill)
            counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"skill": display[k], "count": c} for k, c in ranked[:limit]]


# Curated free learning resources for the most common skills (security-
# heavy, matching the user's core focus). Anything not listed falls back
# to a YouTube course search so the digest never dead-ends.
_SKILL_RESOURCES: dict[str, tuple[str, str]] = {
    "splunk": (
        "Splunk free training",
        "https://www.splunk.com/en_us/training/free-courses/overview.html",
    ),
    "siem": (
        "SOC / SIEM course",
        "https://www.youtube.com/results?search_query=siem+soc+analyst+course",
    ),
    "burp suite": (
        "PortSwigger Web Security Academy",
        "https://portswigger.net/web-security",
    ),
    "wireshark": ("Wireshark docs", "https://www.wireshark.org/docs/"),
    "nmap": ("Nmap book", "https://nmap.org/book/toc.html"),
    "kali linux": ("Kali docs", "https://www.kali.org/docs/"),
    "metasploit": (
        "Metasploit Unleashed",
        "https://www.offsec.com/metasploit-unleashed/",
    ),
    "penetration testing": ("TryHackMe (free)", "https://tryhackme.com/"),
    "ethical hacking": ("TryHackMe (free)", "https://tryhackme.com/"),
    "vapt": (
        "VAPT roadmap",
        "https://www.youtube.com/results?search_query=vapt+penetration+testing+roadmap",
    ),
    "threat": ("MITRE ATT&CK", "https://attack.mitre.org/"),
    "python": ("Python tutorial", "https://docs.python.org/3/tutorial/"),
    "linux": ("Linux Journey", "https://linuxjourney.com/"),
    "aws": ("AWS free training", "https://aws.amazon.com/training/"),
    "azure": (
        "Microsoft Learn",
        "https://learn.microsoft.com/en-us/training/browse/?products=azure",
    ),
    "gcp": ("Google Cloud Skills Boost", "https://www.cloudskillsboost.google/"),
    "docker": ("Docker get-started", "https://docs.docker.com/get-started/"),
    "kubernetes": (
        "K8s basics",
        "https://kubernetes.io/docs/tutorials/kubernetes-basics/",
    ),
    "git": ("GitHub Skills", "https://skills.github.com/"),
    "sql": ("SQLBolt", "https://sqlbolt.com/"),
    "javascript": (
        "MDN JS guide",
        "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
    ),
    "react": ("React docs", "https://react.dev/learn"),
}


def _skill_learn_url(skill: str) -> str | None:
    """Curated free learning resource for a skill, else a YouTube search.

    Returns ``None`` only for empty input; every real skill gets at least
    a YouTube course-search fallback so the digest never dead-ends.
    """
    key = str(skill or "").strip().lower()
    if not key:
        return None
    curated = _SKILL_RESOURCES.get(key)
    if curated:
        return curated[1]
    from urllib.parse import quote

    return "https://www.youtube.com/results?search_query=" + quote(key + " course")


def _salary_txt(job: dict) -> str:
    """Compact salary line ("₹10L–₹15L" / "$80k–$100k") or "" when unknown."""
    lo = job.get("salary_min")
    hi = job.get("salary_max")
    if not lo and not hi:
        return ""
    currency = str(job.get("salary_currency") or "USD").upper()
    symbol = "₹" if currency == "INR" else "$"
    # Pick the scale from the larger bound so max-only INR salaries format
    # consistently (150000 -> 1.5L, not 150K).
    biggest = max(lo or 0, hi or 0)

    def fmt(value) -> str:
        if currency == "INR" and value >= 100000:
            return f"{value / 100000:.1f}".rstrip("0").rstrip(".") + "L"
        if currency == "INR":
            return f"{value / 1000:.0f}K"
        return f"{value / 1000:.0f}k"

    if lo and hi:
        return f"{symbol}{fmt(lo)}–{symbol}{fmt(hi)}"
    return f"{symbol}{fmt(biggest)}"


async def _score_and_group_jobs(
    report: dict,
    session,
    domains: list | None = None,
    user_id: str | None = None,
) -> list[tuple[str, list[tuple[float | None, dict]]]]:
    """Score, filter and group the report's jobs into domain sections.

    Returns a list of ``(domain, [(score, job), ...])`` ordered by the
    canonical domain order, jobs within each section sorted by match score.
    ``report['min_match_score']`` drops jobs below the threshold.

    Location is NOT re-filtered here: per-user digests already arrive
    scoped to the user's city (generate_daily_report), so splitting again
    would only ever produce the "Your area" side. The legacy path (no
    user location) still lets the email/Telegram builders render the
    "Other locations" split themselves.
    """
    jobs = report.get("new_jobs") or []
    if not jobs:
        return []
    # Scam guard: postings with 2+ distinct red-flag groups (money transfer +
    # guaranteed income etc.) never reach members — freshers are prime
    # targets. Single-flag jobs pass but carry a ⚠️ review note on the card.
    clean_jobs = [job for job in jobs if not _is_likely_scam(job)]
    if len(clean_jobs) != len(jobs):
        logger.warning(
            "Dropped %d likely-scam postings from digest (%d kept)",
            len(jobs) - len(clean_jobs),
            len(clean_jobs),
        )
    resume_skills = await _latest_resume_skill_names(session, user_id=user_id)
    scored = [(_job_match_score(resume_skills, job), job) for job in clean_jobs]
    min_score = report.get("min_match_score")
    if min_score:
        scored = [(s, job) for s, job in scored if s is None or (s or 0) >= min_score]
    # Per-member salary floor: drop postings whose listed salary is
    # definitely below the target (unknown-salary jobs stay — a fresher
    # must not lose roles that simply don't advertise pay).
    floor = report.get("target_salary")
    if floor:
        scored = [(s, job) for s, job in scored if not _salary_below_floor(job, floor)]
    if not scored:
        return []

    grouped: dict[str, list] = {}
    for score, job in scored:
        domain = job.get("domain") or "other"
        if domains and domain not in domains:
            continue
        grouped.setdefault(domain, []).append((score, job))

    domain_order = [
        "security",
        "coding",
        "data",
        "design",
        "marketing",
        "finance",
        "govt",
        "other",
    ]
    sections: list[tuple[str, list[tuple[float | None, dict]]]] = []
    for domain in domain_order:
        items = grouped.get(domain)
        if not items:
            continue
        # Match score first, then fresher/entry roles lead, then the
        # freshest postings (never hide a newer job behind an older one at
        # the same score — "real fresh jobs, not older").
        items.sort(
            key=lambda item: (
                item[0] is None,
                -(item[0] or 0.0),
                _job_fresher_rank(item[1]),
                int(item[1].get("age_days", 0) or 0),
            )
        )
        sections.append((domain, items))
    return sections


def _job_of_day(
    sections: list[tuple[str, list[tuple[float | None, dict]]]],
    user_location: str | None = None,
    include_remote: bool = True,
) -> tuple[float | None, dict] | None:
    """The day's top pick: the highest resume match across all sections.

    When ``user_location`` is set, only jobs in the user's area are
    considered first (so a Bangalore user never headlines a Mumbai role as
    the highlight); the overall best job is the fallback when nothing local
    matched. Without resume scores the newest/first job wins, so the
    highlight is never empty while sections exist.
    """

    def _best_of(items: list) -> tuple[float | None, dict] | None:
        best: tuple[float | None, dict] | None = None
        for score, job in items:
            if score is not None and (
                best is None or best[0] is None or score > best[0]
            ):
                best = (score, job)
        if best is not None:
            return best
        return items[0] if items else None

    all_items = [item for _domain, items in sections for item in items]
    if not all_items:
        return None
    loc_lower = (user_location or "").strip().lower()
    if loc_lower:
        local = [
            item
            for item in all_items
            if _location_allows(
                (item[1].get("location") or "").lower(),
                loc_lower,
                include_remote=include_remote,
            )
        ]
        if local:
            return _best_of(local)
    return _best_of(all_items)


async def build_daily_report_message(
    report: dict,
    session,
    domains: list | None = None,
    title: str = "📊 Daily Report",
    user_id: str | None = None,
    user_location: str | None = None,
    include_remote: bool = True,
    weekly: bool = False,
) -> str:
    """Rich daily-report notification: summary counts plus the recent jobs
    grouped by domain (security / coding / data / …), each job carrying its
    apply link, expiry status, age badge, applied marker and match %.

    ``domains`` (when given) only includes those sections and adds a
    "filtered to …" footer; ``report['min_match_score']`` drops jobs whose
    resume match % is below the threshold.
    """
    lines = [format_daily_report(report, title)]

    sections = await _score_and_group_jobs(report, session, domains, user_id=user_id)
    # Resume skills drive the ✅/⬜ requirements checklist on each job line.
    resume_skills = await _latest_resume_skill_names(session, user_id=user_id)

    # 🔥 Job of the day — the user's best match, right at the top.
    job_of_day = _job_of_day(sections, user_location, include_remote=include_remote)
    if job_of_day is not None:
        jotd_score, jotd_job = job_of_day
        jotd_title = (jotd_job.get("title") or "Untitled")[:90]
        jotd_company = (jotd_job.get("company") or "").strip()
        jotd_url = jotd_job.get("url") or ""
        jotd_head = f"🔥 [JOB OF THE DAY] {jotd_title}"
        if jotd_score is not None:
            jotd_head = f"🔥 [JOB OF THE DAY] ({jotd_score:.0f}% match) {jotd_title}"
        if jotd_company and jotd_company.lower() != "unknown":
            jotd_head += f" — {jotd_company}"
        lines.append(jotd_head)
        jotd_desc = _job_desc_snippet(jotd_job)
        if jotd_desc:
            lines.append(f"   📝 {_esc(jotd_desc)}")
        if jotd_url:
            lines.append(f"   🔗 Apply: {jotd_url}")

    # ⏳ Closing-soon jobs (expiring within 2 days) get a priority section so
    # the user can apply before the deadline instead of discovering the
    # posting is gone.
    closing_soon = report.get("closing_soon") or []
    if closing_soon:
        lines.append("")
        lines.append(f"🚨 Closing soon ({len(closing_soon)}):")
        for item in closing_soon[:5]:
            lines.append(
                f"   ⏳ {_esc(item.get('title'))} @ {_esc(item.get('company'))}"
                f" — {_esc(item.get('expires_at'))}"
            )

    # ⏰ Follow-up reminders for applications that are pending action.
    follow_up = report.get("follow_up") or []
    if follow_up:
        lines.append("")
        lines.append(f"⏰ Follow up ({len(follow_up)}):")
        for item in follow_up[:5]:
            title = item.get("job_title") or "Application"
            company = item.get("company") or ""
            status = item.get("status") or ""
            line = f"   🔔 {_esc(title)}"
            if company:
                line += f" @ {_esc(company)}"
            if status:
                line += f" ({_esc(status)})"
            lines.append(line)

    # 🗓️ Interview-stage applications with a Google Calendar add-link.
    interviews = report.get("upcoming_interviews") or []
    if interviews:
        lines.append("")
        lines.append(f"🗓️ Interviews upcoming ({len(interviews)}):")
        for item in interviews[:5]:
            title = item.get("job_title") or "Interview"
            company = item.get("company") or ""
            status = item.get("status") or ""
            line = f"   🔔 {_esc(title)}"
            if company:
                line += f" @ {_esc(company)}"
            if status:
                line += f" ({_esc(status)})"
            lines.append(line)
            cal = _calendar_link(title, company)
            lines.append(f"   📅 Add to calendar: {cal}")

    loc_lower = (user_location or "").strip().lower()
    for domain, items in sections:
        if loc_lower:
            items = [
                (score, job)
                for score, job in items
                if _location_allows(
                    (job.get("location") or "").lower(),
                    loc_lower,
                    include_remote=include_remote,
                )
            ]
            if not items:
                continue
        lines.append("")
        lines.append(f"{_DOMAIN_ICONS.get(domain, domain)} ({len(items)}):")
        for score, job in items:
            lines.extend(
                _job_lines(
                    score,
                    job,
                    target_salary=report.get("target_salary"),
                    keywords=report.get("keywords") or [],
                    resume_skills=resume_skills,
                )
            )

    # Watched-company jobs get their own highlight section.
    watched_jobs = _watched_jobs(report, await _watched_company_names(session, user_id))
    if watched_jobs:
        lines.append("")
        lines.append(f"🏢 Watched companies ({len(watched_jobs)}):")
        for job in watched_jobs:
            lines.extend(
                _job_lines(
                    None,
                    job,
                    target_salary=report.get("target_salary"),
                    keywords=report.get("keywords") or [],
                    resume_skills=resume_skills,
                )
            )

    # 🎓 Internships & fresher roles highlight for fresher-only members.
    if report.get("fresher_only") and not weekly:
        fresher = await _fresher_roles(report, session, domains, user_id=user_id)
        if fresher:
            lines.append("")
            lines.append("🎓 Internships & fresher roles:")
            for job in fresher:
                lines.append(
                    f"   🎓 {_esc(job.get('title') or 'Untitled')} @ "
                    f"{_esc(job.get('company') or 'Unknown')} · "
                    f"{_esc(job.get('location') or 'Remote')}"
                )
                url = job.get("url") or ""
                if url:
                    lines.append(f"   🔗 Apply: {url}")

    # 🏢 Top companies hiring near the user (market snapshot).
    if not weekly and (sections or watched_jobs):
        companies = await _top_companies_near(
            session,
            user_location=user_location,
            include_remote=include_remote,
        )
        if companies:
            lines.append("")
            near_txt = f" near {user_location}" if user_location else ""
            lines.append(f"🏢 Top companies hiring{near_txt}:")
            for company, count, salary in companies:
                salary_txt = f" · {salary}" if salary else ""
                lines.append(f"   {_esc(company)} — {count} fresh role(s){salary_txt}")

    if sections or watched_jobs:
        lines.append("")
        lines.append(
            "Match % = how well your uploaded resume fits each job · "
            "✅/⬜ = applied / not applied."
        )
        if domains:
            lines.append(f"🔔 Filtered to: {', '.join(domains)} only")
        salary_floor = report.get("target_salary")
        if salary_floor:
            lines.append(
                f"💰 Only jobs at/above ₹{int(salary_floor):,}/yr shown "
                "(below it are filtered out)"
            )
    if weekly:
        week = await _week_application_stats(session, user_id) if user_id else {}
        if week.get("total"):
            week_parts = _week_stats_parts(week.get("status_counts") or {})
            lines.append("")
            lines.append(f"📊 Your week in applications ({int(week['total'])} new):")
            lines.append("   " + " · ".join(week_parts))
        salary_line = await _weekly_salary_insight(session, domains, user_location)
        if salary_line:
            lines.append("")
            lines.append(salary_line)
        gap = await _weekly_skill_gap(session, sections, user_id=user_id)
        if gap:
            lines.append("")
            lines.append("🛠 Skills to learn next (from this week's matches):")
            for g in gap:
                lines.append(
                    f"   ⬜ {_esc(g['skill'])} — wanted by {int(g['count'])} job(s)"
                )
            for g in gap[:3]:
                url = _skill_learn_url(g["skill"])
                if url:
                    lines.append(f"   📚 Learn {_esc(g['skill'])}: {url}")
    return "\n".join(lines)


async def build_alert_chunks(
    report: dict,
    session,
    domains: list | None = None,
    weekly: bool = False,
    jobs_per_chunk: int = 4,
    user_id: str | None = None,
    user_location: str | None = None,
    include_remote: bool = True,
    show_dashboard_link: bool = True,
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Split the alert digest into Telegram-sized chunks with Apply buttons.

    Telegram truncates messages at 4096 chars, so a 15-job digest is sent
    as several messages. Each chunk returns ``(text, buttons)`` where
    ``buttons`` is a list of ``(label, url)`` pairs rendered as an inline
    keyboard on Telegram.

    Mirrors the email's layout when the user has a preferred location:
    jobs are split into **📍 Your area** vs **🌍 Other locations** and a
    compact role × location breakdown closes the digest (Telegram is sent
    with HTML parse mode, so the breakdown renders as a real table).
    """
    title = "📅 Weekly Digest" if weekly else "📊 Daily Report"
    sections = await _score_and_group_jobs(report, session, domains, user_id=user_id)
    # Resume skills drive the ✅/⬜ requirements checklist on each job line.
    resume_skills = await _latest_resume_skill_names(session, user_id=user_id)
    loc_lower = (user_location or "").strip().lower()

    # Split into "your area" vs "other locations" like the email does.
    here_flat: list[tuple[str, float | None, dict]] = []
    there_flat: list[tuple[str, float | None, dict]] = []
    for domain, items in sections:
        for score, job in items:
            entry = (domain, score, job)
            if loc_lower:
                job_loc = (job.get("location") or "").lower()
                if _location_allows(job_loc, loc_lower, include_remote=include_remote):
                    here_flat.append(entry)
                else:
                    there_flat.append(entry)
            else:
                here_flat.append(entry)

    # Closing-soon jobs lead the first chunk so deadlines aren't missed.
    closing_soon = report.get("closing_soon") or []
    closing_lines: list[str] = []
    if closing_soon:
        closing_lines.append(f"🚨 Closing soon ({len(closing_soon)}):")
        for item in closing_soon[:5]:
            closing_lines.append(
                f"   ⏳ {_esc(item.get('title'))} @ {_esc(item.get('company'))}"
                f" — {_esc(item.get('expires_at'))}"
            )

    # ⏰ Follow-up reminders lead the first chunk too.
    follow_up = report.get("follow_up") or []
    if follow_up:
        closing_lines.append(f"⏰ Follow up ({len(follow_up)}):")
        for item in follow_up[:5]:
            fu_title = item.get("job_title") or "Application"
            company = item.get("company") or ""
            status = item.get("status") or ""
            line = f"   🔔 {_esc(fu_title)}"
            if company:
                line += f" @ {_esc(company)}"
            if status:
                line += f" ({_esc(status)})"
            closing_lines.append(line)

    # 🗓️ Interview-stage applications with a calendar add-link.
    interviews = report.get("upcoming_interviews") or []
    if interviews:
        closing_lines.append(f"🗓️ Interviews upcoming ({len(interviews)}):")
        for item in interviews[:5]:
            iv_title = item.get("job_title") or "Interview"
            company = item.get("company") or ""
            status = item.get("status") or ""
            line = f"   🔔 {_esc(iv_title)}"
            if company:
                line += f" @ {_esc(company)}"
            if status:
                line += f" ({_esc(status)})"
            closing_lines.append(line)
            cal = _calendar_link(iv_title, company)
            closing_lines.append(f"   📅 Add to calendar: {cal}")

    if not here_flat and not there_flat:
        head_lines = [format_daily_report(report, title)]
        top_engaged = report.get("top_engaged") or []
        if weekly and top_engaged:
            head_lines.append("")
            head_lines.append("🔥 <b>Most engaged this week</b>")
            for entry in top_engaged[:5]:
                te_title = _esc(entry.get("title"))
                te_company = _esc(entry.get("company"))
                te_loc = _esc(entry.get("location"))
                te_score = float(entry.get("engagement_score") or 0)
                line = (
                    f"🔥 {te_score:.1f} · {te_title}"
                    + (f" @ {te_company}" if te_company else "")
                    + (f" · {te_loc}" if te_loc else "")
                )
                head_lines.append(line)
            buttons = []
            for entry in top_engaged[:5]:
                te_url = entry.get("url")
                if te_url:
                    buttons.append(
                        (f"✅ Apply — {_esc(entry.get('title'))[:55]}", te_url)
                    )
            return [("\n".join(head_lines), buttons)]
        if closing_lines:
            return [("\n".join(head_lines + closing_lines), [])]
        return [(head_lines[0], [])]

    # Location banners for each group (kept short for Telegram).
    here_banner = f"📍 Your area ({user_location})" if loc_lower else "📋 Jobs"
    there_banner = f"🌍 Other locations ({len(there_flat)})"

    def _chunk(
        flat_list, banner: str, first: bool
    ) -> list[tuple[str, list[tuple[str, str]]]]:
        """Split one location group into Telegram-sized chunks."""
        out: list[tuple[str, list[tuple[str, str]]]] = []
        for start in range(0, len(flat_list), jobs_per_chunk):
            part = flat_list[start : start + jobs_per_chunk]
            lines = [format_daily_report(report, title)]
            buttons: list[tuple[str, str]] = []
            if first and start == 0 and closing_lines:
                lines.extend(closing_lines)
            lines.append("")
            lines.append(banner)
            for domain, score, job in part:
                domain_label = _DOMAIN_ICONS.get(domain, domain)
                if not lines or lines[-1] != domain_label:
                    lines.append("")
                    lines.append(domain_label)
                lines.extend(
                    _job_lines(
                        score,
                        job,
                        target_salary=report.get("target_salary"),
                        keywords=report.get("keywords") or [],
                        resume_skills=resume_skills,
                    )
                )
                url = job.get("url")
                if url:
                    # Telegram caps button text at 64 chars.
                    job_title = (job.get("title") or "Job").strip()[:60]
                    buttons.append((f"✅ Apply — {job_title}", url))
            out.append(("\n".join(lines), buttons))
        return out

    chunks: list[tuple[str, list[tuple[str, str]]]] = []
    chunks.extend(_chunk(here_flat, here_banner, first=True))
    if there_flat:
        chunks.extend(_chunk(there_flat, there_banner, first=False))

    # 🔥 Most-engaged jobs of the week — a leading chunk on the weekly
    # digest so the recap opens with real activity (weekly-only; the daily
    # digest never carries ``top_engaged``).
    top_engaged = report.get("top_engaged") or []
    if weekly and top_engaged:
        te_lines = ["🔥 <b>Most engaged this week</b>", ""]
        te_buttons: list[tuple[str, str]] = []
        for entry in top_engaged[:5]:
            te_title = _esc(entry.get("title"))
            te_company = _esc(entry.get("company"))
            te_loc = _esc(entry.get("location"))
            te_score = float(entry.get("engagement_score") or 0)
            line = (
                f"🔥 {te_score:.1f} · {te_title}"
                + (f" @ {te_company}" if te_company else "")
                + (f" · {te_loc}" if te_loc else "")
            )
            te_lines.append(line)
            te_url = entry.get("url")
            if te_url:
                te_buttons.append((f"✅ Apply — {te_title[:55]}", te_url))
        chunks.insert(0, ("\n".join(te_lines), te_buttons))

    # Role × location breakdown, matching the email's closing table.
    breakdown = _telegram_breakdown(here_flat, there_flat)
    if breakdown:
        chunks.append((breakdown, []))

    # 🛠 Skills to learn next — the weekly digest's learning hint, mirroring
    # the email card and the My Matches panel (weekly-only).
    if weekly:
        week = await _week_application_stats(session, user_id) if user_id else {}
        if week.get("total"):
            week_parts = _week_stats_parts(week.get("status_counts") or {})
            chunks.append(
                (
                    "📊 <b>Your week in applications</b> "
                    f"({int(week['total'])} new)\n"
                    + "\n".join(f"• {p}" for p in week_parts),
                    [],
                )
            )
        salary_line = await _weekly_salary_insight(session, domains, user_location)
        if salary_line:
            chunks.append((salary_line, []))
        gap = await _weekly_skill_gap(session, sections, user_id=user_id)
        if gap:
            gap_lines = ["🛠 <b>Skills to learn next</b>", ""]
            gap_buttons: list[tuple[str, str]] = []
            for g in gap:
                gap_lines.append(
                    f"⬜ {_esc(g['skill'])} — wanted by {int(g['count'])} job(s)"
                )
                url = _skill_learn_url(g["skill"])
                if url and len(gap_buttons) < 3:
                    gap_buttons.append((f"📚 Learn {_esc(g['skill'])}", url))
            chunks.append(("\n".join(gap_lines), gap_buttons))

    if show_dashboard_link:
        footer_txt = _digest_footer_text()
        if footer_txt:
            chunks.append((footer_txt, []))
    return chunks


def _digest_footer_text() -> str:
    """Dashboard link line for Telegram/text digests, or '' when unset."""
    try:
        from interntrack.config import get_settings

        base = (get_settings().dashboard_url or "").strip().rstrip("/")
    except Exception:  # noqa: BLE001, S110 - footer must never break digest
        return ""
    if not base:
        return ""
    return (
        "—\n📊 Open full dashboard: "
        + _esc(base)
        + "\n⚙️ Manage alerts from the dashboard's Settings page"
    )


def _telegram_breakdown(
    here_flat: list[tuple[str, float | None, dict]],
    there_flat: list[tuple[str, float | None, dict]],
) -> str:
    """Compact role × location HTML table for the Telegram digest tail.

    Rows are domains (security / coding / …), columns are the top job
    locations plus a total. Rendered as a real table because Telegram sends
    with HTML parse mode.
    """
    from collections import Counter

    all_entries = here_flat + there_flat
    if not all_entries:
        return ""
    dom_loc: dict[str, Counter] = {}
    for _domain, _score, job in all_entries:
        d = str(job.get("domain") or "other")
        loc = (job.get("location") or "Remote")[:30]
        dom_loc.setdefault(d, Counter())
        dom_loc[d][loc] += 1
    loc_totals: Counter[str] = Counter()
    for c in dom_loc.values():
        loc_totals.update(c)
    top_locs = [loc for loc, _ in loc_totals.most_common(6)]
    if not top_locs:
        return ""
    d_order = [
        "security",
        "coding",
        "data",
        "design",
        "finance",
        "marketing",
        "govt",
        "other",
    ]
    rows = []
    td = "padding:4px 8px;border:1px solid #e2e8f0;text-align:center;"
    for d in d_order:
        if d not in dom_loc:
            continue
        c = dom_loc[d]
        cells = "".join(f"<td style='{td}'>{c.get(loc, 0)}</td>" for loc in top_locs)
        rows.append(
            f"<tr><td style='{td}font-weight:600;'>{d.title()}</td>"
            f"{cells}<td style='{td}font-weight:600;'>{sum(c.values())}</td></tr>"
        )
    tc = "".join(
        f"<td style='{td}font-weight:700;'>"
        f"{sum(dom_loc[d].get(loc, 0) for d in dom_loc)}</td>"
        for loc in top_locs
    )
    hc = "".join(
        f"<th style='{td}background:#f1f5f9;'>{_esc(loc)}</th>" for loc in top_locs
    )
    return (
        "<b>📊 Jobs by role × location</b>"
        "<table style='width:100%;border-collapse:collapse;font-size:12px;'>"
        f"<tr><th style='{td}background:#f1f5f9;'>Domain</th>{hc}"
        f"<th style='{td}background:#f1f5f9;'>Total</th></tr>"
        + "".join(rows)
        + f"<tr><td style='{td}font-weight:700;'>Total</td>{tc}"
        f"<td style='{td}font-weight:700;'>{len(all_entries)}</td></tr>"
        "</table>"
    )


async def _watched_company_names(session, user_id: str | None) -> set:
    """Lowercased company names the user is watching, or an empty set."""
    if not user_id:
        return set()
    try:
        from sqlalchemy import select

        from interntrack.domain.models import CompanyWatchlist

        result = await session.execute(
            select(CompanyWatchlist.company).where(CompanyWatchlist.user_id == user_id)
        )
        return {str(r[0]).strip().lower() for r in result.all() if r[0]}
    except Exception:
        return set()


def _watched_jobs(report: dict, watched: set) -> list[dict]:
    """The report's jobs whose company is on the watched list."""
    if not watched:
        return []
    out = []
    for job in report.get("new_jobs") or []:
        company = str(job.get("company") or "").strip().lower()
        if company and company in watched:
            out.append(job)
    return out


def _esc(value) -> str:
    """HTML-escape untrusted job content for email rendering."""
    import html as _html

    return _html.escape(str(value or ""))


async def build_daily_report_html(
    report: dict,
    session,
    domains: list | None = None,
    title: str = "📊 Daily Report",
    user_id: str | None = None,
    user_location: str | None = None,
    include_remote: bool = True,
    weekly: bool = False,
    show_dashboard_link: bool = True,
) -> str:
    """Styled HTML digest for email delivery.

    Every domain section renders as a colored card list with match %,
    expiry status and an Apply button per job.  When the user has a
    ``user_location`` set, jobs are split into a **Your area** section
    (fuzzy location match) and **Other locations**, with a role x
    location breakdown table at the bottom.  All job content is escaped
    (external scrape data). Watched-company jobs get their own section.
    """
    sections = await _score_and_group_jobs(report, session, domains, user_id=user_id)
    watched = await _watched_company_names(session, user_id)
    # The member's resume skills drive the ✅ requirements checklist on every
    # job card (same source as the match %). Loaded once, never raises.
    resume_skills = await _latest_resume_skill_names(session, user_id=user_id)
    # When the deployment exposes an API base URL, member Apply buttons
    # become signed tracking links (records the application, then opens
    # the job). Best-effort: a missing URL just keeps plain Apply links.
    api_base = ""
    try:
        from interntrack.config import get_settings

        api_base = (get_settings().api_base_url or "").strip().rstrip("/")
    except Exception:  # noqa: BLE001, S110 - tracking links must never break email
        api_base = ""
    summary = report.get("summary") or {}
    generated = report.get("generated_at") or ""

    # Split sections by location when user has a preferred location
    loc_lower = (user_location or "").strip().lower()
    location_sections = []
    other_sections = []
    if loc_lower and sections:
        for domain, items in sections:
            here = []
            there = []
            for score, job in items:
                job_loc = (job.get("location") or "").lower()
                if _location_allows(job_loc, loc_lower, include_remote=include_remote):
                    here.append((score, job))
                else:
                    there.append((score, job))
            if here:
                location_sections.append((domain, here))
            if there:
                other_sections.append((domain, there))
    else:
        location_sections = sections

    parts = [
        (
            "<div style='font-family:Inter,-apple-system,Segoe UI,Roboto,"
            "sans-serif;max-width:680px;margin:0 auto;color:#0f172a;'>"
        ),
        (
            f"<div style='background:linear-gradient(135deg,#667eea,#764ba2);"
            "color:#fff;border-radius:14px;padding:22px 26px;'>"
            f"{_email_logo_html()}"
            f"<div style='font-size:20px;font-weight:800;'>{_esc(title)}</div>"
            f"<div style='opacity:.85;font-size:13px;'>{_esc(generated)}</div>"
            f"<div style='margin-top:10px;font-size:14px;'>"
            f"New jobs: <b>{summary.get('new_jobs', 0)}</b> · "
            f"New applications: <b>{summary.get('new_applications', 0)}</b></div></div>"
        ),
    ]

    # 🔥 Job of the day — the user's best match, highlighted as a card.
    job_of_day = _job_of_day(sections, user_location, include_remote=include_remote)
    if job_of_day is not None:
        jotd_score, jotd_job = job_of_day
        jotd_title = _esc(jotd_job.get("title") or "Untitled")
        jotd_company = _esc(str(jotd_job.get("company") or ""))
        jotd_loc = _esc(str(jotd_job.get("location") or ""))
        # Escaped like _job_html_card does — & becomes &amp; so hrefs stay
        # valid in every email client.
        jotd_url = _esc(jotd_job.get("url") or "")
        jotd_score_txt = ""
        if jotd_score is not None:
            jotd_score_txt = (
                "<span style='background:#f59e0b;color:#fff;border-radius:999px;"
                "padding:3px 10px;font-size:12px;font-weight:700;'>"
                f"MATCH {jotd_score:.0f}%</span>"
            )
        jotd_link = ""
        if jotd_url:
            jotd_link = (
                "<div style='margin-top:12px;'><a href='"
                f"{jotd_url}' style='background:#f59e0b;color:#fff;"
                "text-decoration:none;border-radius:8px;padding:9px 18px;"
                "font-weight:600;font-size:13px;display:inline-block;'>"
                "🔥 Apply now</a></div>"
            )
        jotd_meta = " · ".join(bit for bit in (jotd_company, jotd_loc) if bit)
        jotd_meta_html = (
            f"<div style='color:#78350f;font-size:13px;margin-top:4px;'>"
            f"{jotd_meta}</div>"
            if jotd_meta
            else ""
        )
        jotd_desc = _esc(_job_desc_snippet(jotd_job, limit=220))
        jotd_desc_html = (
            f"<div style='margin-top:8px;color:#78350f;font-size:13px;"
            f"line-height:1.5;'>{jotd_desc}</div>"
            if jotd_desc
            else ""
        )
        parts.append(
            "<div style='margin-top:24px;background:linear-gradient(135deg,"
            "#fef3c7,#fde68a);border:1px solid #f59e0b;border-radius:12px;"
            "padding:18px 20px;'>"
            "<div style='font-size:12px;font-weight:800;color:#92400e;"
            "letter-spacing:.6px;'>🔥 JOB OF THE DAY</div>"
            f"<div style='font-size:16px;font-weight:700;margin-top:6px;'>"
            f"{jotd_title}</div>{jotd_meta_html}{jotd_desc_html}"
            f"<div style='margin-top:8px;'>{jotd_score_txt}</div>{jotd_link}</div>"
        )

    # 🚶 Hiring drives today — walk-in / campus / off-campus / virtual-drive
    # jobs among today's matches, highlighted so instant-apply roles are
    # unmissable.
    drives = _hiring_drives(sections)
    if drives:
        drive_rows = []
        for d_label, dscore, djob in drives:
            d_title = _esc(djob.get("title") or "Untitled")
            d_company = _esc(str(djob.get("company") or ""))
            d_loc = _esc(str(djob.get("location") or ""))
            d_url = _esc(djob.get("url") or "")
            d_meta = " · ".join(bit for bit in (d_company, d_loc) if bit)
            d_score_txt = f"{dscore:.0f}%" if dscore is not None else "—"
            d_link = ""
            if d_url:
                d_link = (
                    f"<a href='{d_url}' style='background:#db2777;color:#fff;"
                    "text-decoration:none;border-radius:6px;padding:7px 14px;"
                    "font-size:12px;font-weight:700;'>Apply</a>"
                )
            drive_rows.append(
                "<div style='display:flex;justify-content:space-between;"
                "align-items:center;border-bottom:1px dashed #f9a8d4;"
                "padding:10px 0;'>"
                f"<div><b style='font-size:14px;'>{d_title}</b>"
                f"<div style='color:#9d174d;font-size:12px;'>{_esc(d_label)}"
                + (f" · {d_meta}" if d_meta else "")
                + f" · match {d_score_txt}</div></div>"
                + d_link
                + "</div>"
            )
        parts.append(
            "<div style='margin-top:24px;background:#fdf2f8;"
            "border:1px solid #fbcfe8;border-radius:12px;padding:16px 18px;'>"
            "<div style='font-size:12px;font-weight:800;color:#be185d;"
            "letter-spacing:.6px;'>🚶 HIRING DRIVES TODAY</div>"
            f"{''.join(drive_rows)}</div>"
        )

    # 🗓️ Interview-stage applications section (email) with calendar links.
    interviews = report.get("upcoming_interviews") or []
    if interviews:
        iv_rows = []
        for item in interviews[:5]:
            title = _esc(item.get("job_title") or "Interview")
            company = _esc(item.get("company") or "")
            status = _esc(item.get("status") or "")
            cal = _esc(_calendar_link(title, company))
            iv_rows.append(
                "<div style='display:flex;justify-content:space-between;"
                "align-items:center;border-bottom:1px dashed #e2e8f0;"
                "padding:10px 0;'>"
                f"<div><b style='font-size:14px;'>{title}</b>"
                f"<div style='color:#64748b;font-size:13px;'>"
                f"{company} · {status}</div></div>"
                f"<a href='{cal}' style='background:#10b981;color:#fff;"
                "text-decoration:none;border-radius:6px;padding:7px 14px;"
                "font-size:12px;font-weight:700;'>📅 Add to calendar</a></div>"
            )
        parts.append(
            "<div style='margin-top:24px;background:#ecfdf5;"
            "border:1px solid #a7f3d0;border-radius:12px;padding:16px 18px;'>"
            f"<div style='font-size:14px;font-weight:800;color:#047857;'>"
            f"🗓️ Interviews upcoming ({len(interviews)})</div>"
            f"{''.join(iv_rows)}</div>"
        )

    # ⏰ Follow-up reminders section (email).
    follow_up = report.get("follow_up") or []
    if follow_up:
        fu_rows = []
        for item in follow_up[:5]:
            title = _esc(item.get("job_title") or "Application")
            company = _esc(item.get("company") or "")
            status = _esc(item.get("status") or "")
            fu_rows.append(
                "<div style='display:flex;justify-content:space-between;"
                "align-items:center;border-bottom:1px dashed #e2e8f0;"
                "padding:10px 0;'>"
                f"<div><b style='font-size:14px;'>{title}</b>"
                f"<div style='color:#64748b;font-size:13px;'>"
                f"{company} · {status}</div></div>"
                "<div style='color:#e5484d;font-size:12px;font-weight:700;'>"
                "⏰ FOLLOW UP</div></div>"
            )
        parts.append(
            "<div style='margin-top:24px;background:#fff7ed;"
            "border:1px solid #fed7aa;border-radius:12px;padding:16px 18px;'>"
            f"<div style='font-size:14px;font-weight:800;color:#9a3412;'>"
            f"⏰ Follow up ({len(follow_up)})</div>{''.join(fu_rows)}</div>"
        )

    for domain, items in sections:
        label = _DOMAIN_ICONS.get(domain, domain)
        style = {
            "security": "#e5484d",
            "coding": "#3b82f6",
            "data": "#8b5cf6",
            "design": "#ec4899",
            "finance": "#10b981",
            "marketing": "#f59e0b",
            "other": "#64748b",
        }.get(domain, "#64748b")
        parts.append(
            f"<div style='margin:24px 0 8px;padding:12px 16px;border-radius:10px;"
            f"background:#f1f5f9;border-left:5px solid {style};'>"
            f"<b style='font-size:15px;'>{_esc(label)}</b> "
            f"<span style='background:{style};color:#fff;border-radius:999px;"
            f"padding:2px 10px;font-size:12px;'>{len(items)}</span></div>"
        )
        for score, job in items:
            parts.append(
                _job_html_card(
                    score,
                    job,
                    style,
                    target_salary=report.get("target_salary"),
                    keywords=report.get("keywords") or [],
                    resume_skills=resume_skills,
                    apply_link=_apply_link(api_base, user_id, job.get("id")),
                )
            )

    watched_jobs = _watched_jobs(report, watched)
    if watched_jobs:
        parts.append(
            "<div style='margin:24px 0 8px;padding:12px 16px;border-radius:10px;"
            "background:#f1f5f9;border-left:5px solid #0ea5e9;'>"
            f"<b style='font-size:15px;'>🏢 Watched companies</b> "
            f"<span style='background:#0ea5e9;color:#fff;border-radius:999px;"
            f"padding:2px 10px;font-size:12px;'>{len(watched_jobs)}</span></div>"
        )
        for job in watched_jobs:
            parts.append(
                _job_html_card(
                    None,
                    job,
                    "#0ea5e9",
                    target_salary=report.get("target_salary"),
                    keywords=report.get("keywords") or [],
                    resume_skills=resume_skills,
                    apply_link=_apply_link(api_base, user_id, job.get("id")),
                )
            )

    # 🎓 Internships & fresher roles — highlighted for fresher-only members.
    if report.get("fresher_only") and not weekly:
        fresher = await _fresher_roles(report, session, domains, user_id=user_id)
        if fresher:
            fresher_rows = []
            for job in fresher:
                fresher_rows.append(
                    _job_html_card(
                        None,
                        job,
                        "#10b981",
                        target_salary=report.get("target_salary"),
                        keywords=report.get("keywords") or [],
                        resume_skills=resume_skills,
                        apply_link=_apply_link(api_base, user_id, job.get("id")),
                    )
                )
            parts.append(
                "<div style='margin:26px 0 8px;padding:12px 16px;border-radius:10px;"
                "background:#ecfdf5;border-left:5px solid #10b981;'>"
                "<b style='font-size:15px;color:#065f46;'>"
                "🎓 Internships & fresher roles</b> "
                "<span style='background:#10b981;color:#fff;border-radius:999px;"
                "padding:2px 10px;font-size:12px;'>"
                + str(len(fresher))
                + "</span></div>"
            )
            parts.extend(fresher_rows)

    # 🏢 Top companies hiring near the user (market snapshot).
    if not weekly and (sections or watched_jobs):
        companies = await _top_companies_near(
            session,
            user_location=user_location,
            include_remote=include_remote,
        )
        if companies:
            company_chips = []
            for company, count, salary in companies:
                salary_html = (
                    f"<br/><span style='color:#047857;font-size:11px;'>"
                    f"💰 {_esc(salary)}</span>"
                    if salary
                    else ""
                )
                company_chips.append(
                    "<div style='display:inline-block;margin:4px 6px 0 0;"
                    "padding:7px 14px;border-radius:999px;font-size:12px;"
                    "font-weight:600;color:#0f172a;background:#f1f5f9;"
                    "border:1px solid #e2e8f0;text-align:center;'>"
                    f"🏢 {_esc(company)} · <b>{count}</b>{salary_html}</div>"
                )
            near_txt = " near you" if loc_lower else ""
            parts.append(
                "<div style='background:#f8fafc;border:1px solid #e2e8f0;"
                "border-radius:12px;padding:14px 18px;margin:24px 0 0;'>"
                "<div style='font-weight:800;font-size:14px;'>"
                f"🏢 Top companies hiring{near_txt}</div>"
                "<div style='font-size:12px;color:#64748b;margin:4px 0 8px;'>"
                "Who is posting the most fresh roles in your area this week."
                "</div>" + "".join(company_chips) + "</div>"
            )

    # Other locations section
    if loc_lower and other_sections:
        other_count = sum(len(items) for _, items in other_sections)
        parts.append(
            "<div style='margin:28px 0 8px;padding:12px 16px;border-radius:10px;"
            "background:#fff7ed;border-left:5px solid #f97316;'>"
            "<b style='font-size:15px;'>🌍 Other locations</b> "
            "<span style='background:#f97316;color:#fff;border-radius:999px;"
            "padding:2px 10px;font-size:12px;'>" + str(other_count) + "</span></div>"
        )
        for domain, items in other_sections:
            label = _DOMAIN_ICONS.get(domain, domain)
            accent = {
                "security": "#e5484d",
                "coding": "#3b82f6",
                "data": "#8b5cf6",
                "design": "#ec4899",
                "finance": "#10b981",
                "marketing": "#f59e0b",
                "other": "#64748b",
            }.get(domain, "#64748b")
            parts.append(
                "<div style='margin:16px 0 6px;padding:8px 14px;border-radius:8px;"
                "background:#fff7ed;border-left:4px solid " + accent + ";'>"
                "<b style='font-size:13px;'>" + _esc(label) + "</b> "
                "<span style='background:" + accent + ";color:#fff;border-radius:999px;"
                "padding:1px 8px;font-size:11px;'>" + str(len(items)) + "</span></div>"
            )
            for score, job in items:
                parts.append(
                    _job_html_card(
                        score,
                        job,
                        accent,
                        target_salary=report.get("target_salary"),
                        keywords=report.get("keywords") or [],
                        resume_skills=resume_skills,
                        apply_link=_apply_link(api_base, user_id, job.get("id")),
                    )
                )

    # Role x location breakdown table
    if loc_lower:
        parts.append(_location_breakdown_table(location_sections, other_sections))

    # 🔥 Most-engaged jobs of the week (attached by the weekly endpoint).
    top_engaged = report.get("top_engaged") or []
    if top_engaged:
        parts.append(
            "<div style='margin:26px 0 10px;padding:14px 18px;border-radius:12px;"
            "background:linear-gradient(135deg,#fef3c7 0%,#fde68a 100%);"
            "border:1px solid #fbbf24;'>"
            "<div style='font-weight:800;font-size:15px;'>"
            "🔥 Most engaged this week</div>"
            "<div style='font-size:12px;color:#92400e;margin:4px 0 10px;'>"
            "The jobs people actually applied to / saved / opened this week."
            "</div>"
        )
        for entry in top_engaged:
            te_title = _esc(entry.get("title"))
            te_company = _esc(entry.get("company"))
            te_loc = _esc(entry.get("location"))
            te_url = entry.get("url") or "#"
            te_score = float(entry.get("engagement_score") or 0)
            stats = (
                f"👁 {int(entry.get('views', 0))} views · "
                f"📋 {int(entry.get('applications', 0))} applied · "
                f"📌 {int(entry.get('bookmarks', 0))} saved"
            )
            parts.append(
                "<div style='margin:8px 0;padding:10px 12px;border-radius:8px;"
                "background:#fff;border-left:4px solid #f59e0b;'>"
                "<div style='font-weight:700;font-size:13px;color:#78350f;'>"
                f"🔥 {te_score:.1f} &nbsp;{te_title}</div>"
                "<div style='font-size:12px;color:#64748b;margin:2px 0;'>"
                f"{te_company}{' · ' + te_loc if te_loc else ''}</div>"
                f"<div style='font-size:12px;color:#64748b;'>{stats}</div>"
                f"<a href='{_esc(te_url)}' style='display:inline-block;margin-top:8px;"
                "background:#f59e0b;color:#fff;text-decoration:none;border-radius:6px;"
                "padding:6px 14px;font-size:12px;font-weight:700;'>Apply</a>"
                "</div>"
            )
        parts.append("</div>")

    # Team snapshot (attached by _deliver_alert on weekly sends).
    team = report.get("team")
    if team:
        team_size = int(team.get("team_size", 0) or 0)
        my_refs = int(team.get("my_referrals", 0) or 0)
        parts.append(
            "<div style='background:#f1f5f9;border-radius:12px;padding:14px 18px;"
            "margin:18px 0;font-size:13px;'>"
            "<div style='font-weight:800;font-size:14px;'>👥 Your team</div>"
            "<div style='margin-top:6px;color:#334155;'>"
            f"<b>{team_size}</b> people get personalized alerts on this platform"
            + (
                f" · <b>{my_refs}</b> joined through <b>your</b> invite link 🎁"
                if my_refs
                else ""
            )
            + "</div></div>"
        )

    if weekly:
        week = await _week_application_stats(session, user_id) if user_id else {}
        if week.get("total"):
            week_counts = week.get("status_counts") or {}
            week_chips = " · ".join(
                f"<b>{int(week_counts.get(k, 0))}</b> "
                f"{_esc(_week_status_label(k, int(week_counts.get(k, 0))))}"
                for k, _, _ in _WEEK_STATUS_LABELS
                if week_counts.get(k)
            )
            parts.append(
                "<div style='background:#eff6ff;border:1px solid #bfdbfe;"
                "border-radius:12px;padding:12px 18px;margin:18px 0;"
                "font-size:13px;color:#1e40af;'>"
                "<div style='font-weight:800;font-size:14px;'>"
                "📊 Your week in applications</div>"
                f"<div style='margin-top:6px;'>{week_chips}</div></div>"
            )
        salary_line = await _weekly_salary_insight(session, domains, user_location)
        if salary_line:
            parts.append(
                "<div style='background:#ecfdf5;border-radius:12px;padding:12px 18px;"
                "margin:18px 0;font-size:13px;font-weight:600;color:#065f46;'>"
                f"{_esc(salary_line)}</div>"
            )
        gap = await _weekly_skill_gap(session, sections, user_id=user_id)
        if gap:

            def _gap_chip(g: dict) -> str:
                body = (
                    "<span style='display:inline-block;margin:4px 6px 0 0;"
                    "padding:4px 12px;border-radius:999px;font-size:12px;"
                    "font-weight:600;color:#dc2626;border:1px solid "
                    "rgba(220,38,38,0.35);background:rgba(220,38,38,0.06);'>"
                    f"⬜ {_esc(g['skill'])} · {int(g['count'])} job(s)</span>"
                )
                url = _skill_learn_url(g["skill"])
                if url:
                    return (
                        f"<a href='{_esc(url)}' target='_blank' "
                        f"style='text-decoration:none;'>{body}</a>"
                    )
                return body

            chips = "".join(_gap_chip(g) for g in gap)
            parts.append(
                "<div style='background:#fff7ed;border-radius:12px;padding:14px 18px;"
                "margin:18px 0;font-size:13px;'>"
                "<div style='font-weight:800;font-size:14px;'>"
                "🛠 Skills to learn next</div>"
                "<div style='margin-top:6px;color:#475569;'>Expected by this week's "
                "matches but missing from your resume — learn these to unlock more "
                "matches.</div>"
                f"<div style='margin-top:8px;'>{chips}</div></div>"
            )

    salary_floor = report.get("target_salary")
    if salary_floor:
        parts.append(
            "<p style='color:#64748b;font-size:12px;'>💰 Only jobs at/above "
            f"₹{int(salary_floor):,}/yr shown — below it are filtered out.</p>"
        )
    parts.append(
        "<p style='color:#64748b;font-size:12px;margin-top:22px;'>"
        "Match % = how well your uploaded resume fits each job · "
        "✅/⬜ = applied / not applied.</p>"
    )
    if show_dashboard_link:
        footer = _digest_footer_html()
        if footer:
            parts.append(footer)
    else:
        parts.append(_member_footer_html())
    pixel = _open_pixel_html(api_base, user_id)
    if pixel:
        parts.append(pixel)
    parts.append("</div>")
    return "".join(parts)


def _open_pixel_html(api_base: str, user_id: str | None) -> str:
    """1x1 transparent open-tracking pixel for one digest email, or ''.

    When the deployment has an ``api_base_url`` and the digest knows the
    member, the email's HTML embeds a tiny signed image that records when
    the member opens the email (``NotificationHistory.opened_at``) — the
    owner recap's open column. Never raises.
    """
    if not api_base or not user_id:
        return ""
    from urllib.parse import quote

    from interntrack.utils.helpers import open_token

    base = api_base.strip().rstrip("/")
    token = open_token(str(user_id))
    return (
        f"<img src='{_esc(base)}/api/v1/email/open?u={quote(str(user_id))}"
        f"&t={token}' width='1' height='1' alt='' style='display:none;' />"
    )


def _member_footer_html() -> str:
    """Short no-dashboard footer for member digests.

    Members get everything from email, so the footer tells them what they
    receive and how to make changes — without pointing at the dashboard
    (which is owner-only). Rendered only when ``show_dashboard_link`` is
    False; the owner keeps the dashboard footer instead.
    """
    return (
        "<div style='margin-top:24px;padding-top:16px;border-top:1px solid "
        "#e2e8f0;font-size:12px;color:#94a3b8;'>"
        "You get these every day at 8 AM, 1 PM & 7 PM IST. To change your "
        "roles, location, or pause alerts, ask your admin.</div>"
    )


def _email_logo_html() -> str:
    """Brand logo <img> for the email header, or '' when no public URL.

    Uses the same API base the PWA is served from (``api_base_url``),
    appending ``/static/logo.png`` — the logo is mounted on the API at
    ``/static`` so emails can hotlink it. Falls back to '' so a missing
    URL never breaks the digest; the header keeps its title alone.
    """
    try:
        from interntrack.config import get_settings

        settings = get_settings()
        base = (
            (settings.api_base_url or settings.dashboard_url or "").strip().rstrip("/")
        )
    except Exception:  # noqa: BLE001, S110 - logo must never break email
        return ""
    if not base:
        return ""
    return (
        "<div style='text-align:center;margin-bottom:14px;'>"
        f"<img src='{_esc(base)}/static/logo.png' alt='InternTrack' "
        "width='110' height='84' style='border-radius:10px;"
        "background:#fff;padding:6px 10px;' /></div>"
    )


def _digest_footer_html() -> str:
    """Dashboard + settings links for the email footer, or '' when no URL.

    Reads ``settings.dashboard_url``; when unset (dev / no public dashboard)
    the footer is omitted entirely. Both links are plain-text escaped — the
    URL comes from an env var, but ``_esc`` keeps it defensive.
    """
    try:
        from interntrack.config import get_settings

        base = (get_settings().dashboard_url or "").strip().rstrip("/")
    except Exception:  # noqa: BLE001, S110 - footer must never break email
        return ""
    if not base:
        return ""
    dash = _esc(base)
    return (
        "<div style='margin-top:24px;padding-top:16px;border-top:1px solid "
        "#e2e8f0;font-size:13px;color:#475569;'>"
        f"<a href='{dash}' style='color:#667eea;text-decoration:none;"
        "font-weight:600;'>📊 Open full dashboard</a>"
        "<div style='margin-top:6px;color:#94a3b8;font-size:12px;'>"
        "You get these because your alerts are enabled on InternTrack — "
        "open the dashboard and use the ⚙️ Settings page to change your "
        "domains, location, or turn alerts off.</div></div>"
    )


def _location_matches(job_loc, user_loc):
    """Fuzzy location match with synonyms (delegates to utils.helpers)."""
    from interntrack.utils.helpers import location_matches

    return location_matches(job_loc, user_loc)


def _location_allows(job_loc, user_loc, include_remote: bool = True):
    """City match, plus remote/WFH when opted in (delegates to helpers)."""
    from interntrack.utils.helpers import location_allows

    return location_allows(job_loc, user_loc, include_remote=include_remote)


def _location_breakdown_table(sections, other_sections):
    """HTML table: job counts by domain x top locations."""
    all_jobs = []
    for _, items in (sections or []) + (other_sections or []):
        all_jobs.extend(items)
    if not all_jobs:
        return ""
    from collections import Counter

    dom_loc: dict[str, Counter] = {}
    for _, job in all_jobs:
        d = str(job.get("domain") or "other")
        loc = (job.get("location") or "Remote")[:30]
        dom_loc.setdefault(d, Counter())
        dom_loc[d][loc] += 1
    loc_totals: Counter[str] = Counter()
    for c in dom_loc.values():
        loc_totals.update(c)
    top_locs = [loc for loc, _ in loc_totals.most_common(6)]
    if not top_locs:
        return ""
    d_order = [
        "security",
        "coding",
        "data",
        "design",
        "finance",
        "marketing",
        "govt",
        "other",
    ]
    rows = []
    td = "padding:6px 10px;border:1px solid #e2e8f0;"
    for d in d_order:
        if d not in dom_loc:
            continue
        c = dom_loc[d]
        cells = "".join(
            "<td style='" + td + "text-align:center;'>" + str(c.get(loc, 0)) + "</td>"
            for loc in top_locs
        )
        t = sum(c.values())
        rows.append(
            "<tr><td style='"
            + td
            + "font-weight:600;'>"
            + d.title()
            + "</td>"
            + cells
            + "<td style='"
            + td
            + "font-weight:600;text-align:center;'>"
            + str(t)
            + "</td></tr>"
        )
    tc = ""
    for loc in top_locs:
        v = sum(dom_loc[d].get(loc, 0) for d in dom_loc)
        tc += (
            "<td style='"
            + td
            + "font-weight:700;text-align:center;'>"
            + str(v)
            + "</td>"
        )  # noqa: E501
    hc = "".join(
        "<th style='" + td + "background:#f1f5f9;'>" + loc + "</th>" for loc in top_locs
    )
    return (
        "<div style='margin:28px 0 12px;padding:16px;border-radius:12px;border:1px solid #e2e8f0;background:#fafbfc;'>"  # noqa: E501
        "<b style='font-size:15px;'>📊 Jobs by role × location</b>"
        "<div style='overflow-x:auto;margin-top:10px;'>"
        "<table style='width:100%;border-collapse:collapse;font-size:13px;'>"
        "<tr><th style='"
        + td
        + "background:#f1f5f9;'>Domain</th>"
        + hc
        + "<th style='"
        + td
        + "background:#f1f5f9;'>Total</th></tr>"
        + "".join(rows)
        + "</table></div></div>"
    )


def _skills_checklist_lines(job: dict, resume_skills: set | None) -> list[str]:
    """Plain-text requirements checklist: ✅ matched / 🟡 related / ⬜ missing.

    Mirrors ``_skills_checklist_html`` (same skill-classification engine)
    so the plain-text digest agrees with the email. Returns up to 6 chips
    as a list of short strings; ``[]`` when no resume or no skills.
    """
    if not resume_skills:
        return []
    try:
        from cybershield.api.v1.resumes import (
            _calculate_job_match,
            _JobMatchData,
        )

        job_data = _JobMatchData(
            id=str(job.get("id") or ""),
            title=str(job.get("title") or ""),
            company=str(job.get("company") or ""),
            required_skills=job.get("required_skills") or [],
            preferred_skills=job.get("preferred_skills") or [],
            tags=job.get("tags") or [],
        )
        result = _calculate_job_match(resume_skills, job_data)
        rows = []
        for skill in (result.matched_skills or [])[:3]:
            rows.append(f"✅{_esc(str(skill))}")
        for skill in (result.related_skills or [])[:1]:
            rows.append(f"🟡{_esc(str(skill))}")
        for skill in (result.missing_skills or [])[:2]:
            rows.append(f"⬜{_esc(str(skill))}")
        return rows
    except Exception:  # noqa: BLE001 - a checklist must never break the card
        return []


def _skills_checklist_html(job: dict, resume_skills: set | None) -> str:
    """HTML requirements checklist for a job vs the member's resume skills.

    Uses the same skill-classification engine as the match % (exact /
    synonym / category tiers from ``_calculate_job_match``) so the
    checklist always agrees with the score on the card. Renders up to 8
    skills as ✅ matched / 🟡 related / ⬜ missing chips; returns "" when
    the member has no resume or the job lists no skills. All skill names
    are escaped (external scrape data).
    """
    if not resume_skills:
        return ""
    try:
        from cybershield.api.v1.resumes import (
            _calculate_job_match,
            _JobMatchData,
        )

        job_data = _JobMatchData(
            id=str(job.get("id") or ""),
            title=str(job.get("title") or ""),
            company=str(job.get("company") or ""),
            required_skills=job.get("required_skills") or [],
            preferred_skills=job.get("preferred_skills") or [],
            tags=job.get("tags") or [],
        )
        result = _calculate_job_match(resume_skills, job_data)
        rows = []
        for skill in (result.matched_skills or [])[:4]:
            rows.append(f"<span style='color:#065f46;'>✅ {_esc(str(skill))}</span>")
        for skill in (result.related_skills or [])[:2]:
            rows.append(f"<span style='color:#b45309;'>🟡 {_esc(str(skill))}</span>")
        for skill in (result.missing_skills or [])[:4]:
            learn = _skill_learn_url(skill)
            learn_link = (
                f" <a href='{_esc(learn)}' style='color:#0f766e;"
                f"font-weight:700;text-decoration:none;' target='_blank'>"
                f"📚 learn</a>"
                if learn
                else ""
            )
            rows.append(
                f"<span style='color:#b91c1c;'>⬜ {_esc(str(skill))}{learn_link}</span>"
            )
        if not rows:
            return ""
        chips = (
            "<span style='display:inline-block;margin:3px 8px 0 0;'>"
            + "</span><span style='display:inline-block;margin:3px 8px 0 0;'>".join(
                rows
            )
            + "</span>"
        )
        return (
            "<div style='margin-top:8px;padding:8px 10px;background:#f0fdf4;"
            "border-radius:6px;font-size:12px;line-height:1.6;'>"
            "<div style='font-weight:700;color:#166534;font-size:11px;"
            "letter-spacing:.4px;'>✅ REQUIREMENTS CHECKLIST</div>"
            f"<div style='margin-top:2px;'>{chips}</div></div>"
        )
    except Exception:  # noqa: BLE001 - a checklist must never break the card
        return ""


# Direct hiring signals detected in a job's title / description. When one
# matches, the job card shows a badge (walk-in drive, campus hiring, …) so
# members spot immediate-apply opportunities at a glance.
_HIRING_SIGNALS = (
    (
        "🚶 Walk-in interview",
        ("walk-in interview", "walk in interview", "walkin interview"),
    ),
    ("🏢 Walk-in drive", ("walk-in drive", "walk in drive", "walk-in")),
    (
        "🎓 Campus hiring",
        ("campus hiring", "campus placement", "campus drive", "campus recruitment"),
    ),
    (
        "🎓 Off-campus drive",
        ("off-campus drive", "off campus drive", "offcampus drive"),
    ),
    ("⚡ Immediate hiring", ("immediate hiring", "immediate joining", "urgent hiring")),
    ("📣 Now hiring", ("we are hiring", "now hiring", "looking for")),
    ("🔗 Referral", ("referral", "employee referral", "refer and earn")),
    (
        "💼 Internship opening",
        (
            "internship opening",
            "intern opening",
            "looking for interns",
            "intern required",
        ),
    ),
    (
        "📬 Send resume",
        ("send resume", "send your resume", "mail your resume", "submit your resume"),
    ),
    ("🖥️ Virtual drive", ("virtual hiring", "virtual drive", "online drive")),
    (
        "🔬 Research intern",
        ("research intern", "research internship", "research intern required"),
    ),
    ("🌐 Remote okay", ("remote okay", "work from anywhere")),
)


def _hiring_signal(job: dict) -> str | None:
    """First direct hiring signal label found in title + description, or None."""
    text = f"{job.get('title') or ''} {job.get('description') or ''}".lower()
    if not text.strip():
        return None
    for label, phrases in _HIRING_SIGNALS:
        if any(phrase in text for phrase in phrases):
            return label
    return None


def _hiring_signal_badge(job: dict) -> str:
    """The hiring signal as an HTML chip (empty when no signal matches)."""
    label = _hiring_signal(job)
    if not label:
        return ""
    return (
        "<span style='background:#fce7f3;color:#9d174d;border-radius:999px;"
        "padding:2px 9px;font-size:11px;font-weight:700;margin-right:6px;'>"
        f"{label}</span>"
    )


def _hiring_drives(sections, cap: int = 5) -> list[tuple[str, float | None, dict]]:
    """Instant-apply drive jobs (walk-in / campus / off-campus / virtual)
    pulled out of the digest sections, capped for the highlight section.

    Returns ``[(signal_label, score, job), ...]`` in section order.
    """
    drives: list[tuple[str, float | None, dict]] = []
    for _domain, items in sections:
        for score, job in items:
            label = _hiring_signal(job) or ""
            if any(k in label for k in ("Walk-in", "Campus", "Off-campus", "Virtual")):
                drives.append((label, score, job))
                if len(drives) >= cap:
                    return drives
    return drives


# Red-flag groups used to catch fake / scam postings aimed at freshers.
# These are deliberately conservative: money-transfer or guaranteed-income
# phrases are common scam tells; single matches are flagged (⚠️) on the
# card, two or more distinct groups drop the job from digests entirely.
_SCAM_PATTERNS = (
    (
        "money transfer",
        (
            "registration fee",
            "processing fee",
            "joining fee",
            "pay to apply",
            "send money",
            "money transfer",
            "bank details",
            "upi payment",
            "deposit of",
            "payout",
            "bitcoin",
            "crypto",
        ),
    ),
    (
        "guaranteed income",
        (
            "guaranteed job",
            "guaranteed income",
            "100% placement",
            "guaranteed placement",
            "earn ₹",
            "earn rs ",
            "no experience needed earn",
        ),
    ),
    (
        "no-interview hiring",
        ("no interview needed", "without interview", "direct offer"),
    ),
    (
        "sketchy contact",
        ("contact on telegram", "telegram only", "whatsapp only", "dm me for"),
    ),
)


def _scam_signals(job: dict) -> list[str]:
    """Distinct red-flag groups matched in the title + description."""
    text = f"{job.get('title') or ''} {job.get('description') or ''}".lower()
    if not text.strip():
        return []
    return [
        label for label, phrases in _SCAM_PATTERNS if any(p in text for p in phrases)
    ]


def _is_likely_scam(job: dict) -> bool:
    """Two or more distinct red-flag groups = likely scam, drop from digests."""
    return len(_scam_signals(job)) >= 2


def _apply_link(api_base: str, user_id: str | None, job_id: str | None) -> str | None:
    """Signed 'Apply now' tracking URL for one digest email card, or None.

    When the digest knows the member (``user_id``) and the deployment has an
    ``api_base_url``, the card's Apply button becomes a tracking link that
    records the application (so follow-up nudges and the weekly recap work
    for members who never open the dashboard) before opening the job.
    """
    if not api_base or not user_id or not job_id:
        return None
    from urllib.parse import quote

    from interntrack.utils.helpers import apply_token

    base = api_base.strip().rstrip("/")
    token = apply_token(str(user_id), str(job_id))
    return (
        f"{base}/api/v1/email/apply?u={quote(str(user_id))}"
        f"&j={quote(str(job_id))}&t={token}"
    )


def _closing_soon_html(matches: list[dict], user_id: str | None, api_base: str) -> str:
    """Styled HTML for the closing-soon email, with tracked Apply buttons.

    Reuses the standard job card so closing-soon emails look like the
    daily digest and — when ``api_base`` + ``user_id`` are known — carry
    signed apply-tracking links, so members who never open the dashboard
    record these applications too.
    """
    cards = [
        _job_html_card(
            None,
            cj,
            "#e5484d",
            apply_link=_apply_link(api_base, user_id, cj.get("id")),
        )
        for cj in matches[:5]
    ]
    return (
        "<div style='font-family:Inter,Arial,sans-serif;max-width:640px;"
        "margin:0 auto;'>"
        "<h2 style='margin-bottom:4px;'>🚨 Closing soon — apply now!</h2>"
        "<p style='color:#64748b;margin-top:0;'>These jobs close within "
        "48 hours.</p>" + "".join(cards) + _member_footer_html() + "</div>"
    )


def _job_html_card(
    score,
    job: dict,
    accent: str,
    target_salary: int | None = None,
    keywords: list | None = None,
    resume_skills: set | None = None,
    apply_link: str | None = None,
) -> str:
    """One job as an HTML card with an Apply button.

    When ``resume_skills`` is given, the card also renders a **requirements
    checklist**: the job's expected skills compared against the member's
    resume — ✅ matched, 🟡 related (same skill family), ⬜ missing — so
    the member sees at a glance exactly what the role expects vs. what
    they already have.

    When ``apply_link`` is given, the Apply button points at the signed
    tracking URL (records the application, then opens the job) instead of
    the raw job URL.
    """
    title = _esc(job.get("title") or "Untitled")
    company = _esc(job.get("company") or "")
    url = _esc(job.get("url") or "")
    location = _esc(job.get("location") or "Remote")
    score_txt = f"{score:.0f}%" if score is not None else "—"
    applied = job.get("is_applied", False)
    status_txt = "✅ Applied" if applied else "⬜ Not applied"
    age = _age_badge(int(job.get("age_days", 0) or 0))
    expiry = _esc(_expiry_note(job).strip())
    salary = _esc(_salary_txt(job))
    exp_level = _esc(str(job.get("experience_level") or "").strip())
    source = _esc(_source_label(job.get("source")))
    fresher_badge = (
        "<span style='background:#dcfce7;color:#166534;border-radius:999px;"
        "padding:2px 9px;font-size:11px;font-weight:700;margin-right:6px;'>"
        "🎓 Fresher</span>"
        if _job_fresher_rank(job) == 0
        else ""
    )
    meta_bits = [bit for bit in (status_txt, expiry, salary, exp_level) if bit]
    if source:
        meta_bits.append(source)
    card = (
        "<div style='border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;"
        "margin:10px 0;'>"
        "<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<div><b style='font-size:15px;'>{title}</b>"
        f"<div style='color:#64748b;font-size:13px;'>"
        f"{company} · {location} · {age}</div></div>"
        "<div style='text-align:center;'>"
        f"<div style='font-size:20px;font-weight:800;color:{accent};'>{score_txt}</div>"
        "<div style='color:#94a3b8;font-size:11px;'>match</div></div></div>"
        "<div style='margin-top:8px;font-size:13px;color:#475569;'>"
        f"{' · '.join(meta_bits)}</div>"
    )
    skills = _esc(_skills_txt(job, limit=5))
    if skills:
        card += (
            "<div style='margin-top:6px;font-size:12px;color:#0f766e;'>"
            f"🛠 Skills: {skills}</div>"
        )
    checklist = _skills_checklist_html(job, resume_skills)
    if checklist:
        card += checklist
    chips = ""
    if _salary_meets_target(job, target_salary):
        chips += (
            "<span style='background:#d1fae5;color:#065f46;border-radius:999px;"
            "padding:2px 9px;font-size:11px;font-weight:700;margin-right:6px;'>"
            "💰 Meets your target</span>"
        )
    hiring_badge = _hiring_signal_badge(job)
    if hiring_badge:
        chips += hiring_badge
    for hit in _keyword_hits(job, keywords):
        chips += (
            "<span style='background:#fef3c7;color:#92400e;border-radius:999px;"
            "padding:2px 9px;font-size:11px;font-weight:700;margin-right:6px;'>"
            f"🎯 {_esc(hit)}</span>"
        )
    if chips:
        card += "<div style='margin-top:8px;'>" + chips + "</div>"
    scam_flags = _scam_signals(job)
    if scam_flags:
        card += (
            "<div style='margin-top:8px;background:#fef2f2;border:1px solid #fecaca;"
            "border-radius:6px;padding:6px 10px;color:#b91c1c;font-size:12px;'>"
            f"⚠️ Review carefully — red flags: {_esc(', '.join(scam_flags))}. "
            "Legit employers never ask for money.</div>"
        )
    if fresher_badge:
        card += "<div style='margin-top:8px;'>" + fresher_badge + "</div>"
    desc = _esc(_job_desc_snippet(job, limit=240))
    full_desc = _esc(_job_desc_full(job))
    if desc:
        card += (
            "<div style='margin-top:8px;padding:8px 10px;background:#f8fafc;"
            "border-left:3px solid " + accent + ";border-radius:6px;"
            "color:#475569;font-size:13px;line-height:1.45;'>" + desc + "</div>"
        )
    if full_desc and len(full_desc) > 240:
        card += (
            "<details style='margin-top:8px;'><summary style='cursor:pointer;"
            "color:#475569;font-size:12px;font-weight:600;'>📄 What they expect "
            "— full description</summary><div style='margin-top:6px;padding:8px "
            "10px;background:#f1f5f9;border-radius:6px;color:#475569;"
            "font-size:13px;line-height:1.5;'>" + full_desc + "</div></details>"
        )
    href = apply_link or url
    if href:
        track_hint = (
            " title='Opens the job and tracks it in your applications'"
            if apply_link
            else ""
        )
        card += (
            "<div style='margin-top:10px;'>"
            f"<a href='{_esc(href)}'{track_hint} style='background:{accent};color:#fff;"
            "text-decoration:none;border-radius:8px;padding:8px 18px;"
            "font-weight:600;font-size:13px;display:inline-block;'>Apply now</a>"
            "</div>"
        )
    card += "</div>"
    return card


# Search queries used to discover jobs for each alert category (per-user
# discovery derives its query list from the user's chosen domains + skills).
DOMAIN_QUERIES = {
    "security": [
        "cybersecurity",
        "soc analyst",
        "security analyst",
        "vapt",
        "security engineer",
        "cybersecurity internship",
        "penetration testing",
        "cyber defense",
        "incident response",
        "devsecops",
        "blue team",
        "cybersecurity bangalore",
        "soc analyst bangalore",
        "security analyst bangalore",
        "security engineer bangalore",
        "vapt bangalore",
        "penetration testing bangalore",
        "information security bangalore",
        "network security bangalore",
        "application security bangalore",
        "cloud security bangalore",
        "security operations bangalore",
    ],
    "frontend": [
        "frontend developer",
        "frontend engineer",
        "react developer",
        "ui developer",
        "frontend developer chennai",
        "react developer chennai",
        "ui developer chennai",
        "frontend developer bangalore",
        "angular developer",
        "vue developer",
        "javascript developer",
        "frontend internship",
        "frontend developer internship",
        # Niche frontend roles (surfaced by the day rotation).
        "web developer",
        "html css developer",
        "next.js developer",
        "typescript developer",
        "react native developer",
    ],
    "hardware": [
        "hardware engineer",
        "embedded engineer",
        "embedded systems",
        "pcb design",
        "pcb designer",
        "rf engineer",
        "electronics engineer",
        "vlsi engineer",
        "fpga engineer",
        "firmware engineer",
        "test engineer",
        "testing engineer",
        "hardware testing",
        "labview developer",
        "hardware engineer chennai",
        "embedded engineer chennai",
        "hardware engineer bangalore",
        "embedded engineer bangalore",
        "hardware engineer coimbatore",
        "electronics engineer chennai",
        "electronics engineer bangalore",
        "embedded internship",
        "electronics internship",
        # Niche hardware / electronics roles (surfaced by the day rotation).
        "iot engineer",
        "mechatronics engineer",
        "power electronics engineer",
        "control systems engineer",
        "instrumentation engineer",
        "antenna engineer",
        "automotive electronics",
        "cad engineer",
        "hardware design",
        "schematics design",
        "vlsi design",
    ],
    "coding": [
        "software engineer",
        "software developer",
        "python developer",
        "backend developer",
        "backend engineer",
        "java developer",
        "node.js developer",
        "django developer",
        "spring boot developer",
        "microservices developer",
        "api developer",
        "devops engineer",
        "full stack developer",
        "software engineering internship",
        "software developer internship",
        "software testing",
        "qa engineer",
        "test automation",
        "software tester",
        "sdet",
        "full stack developer internship",
        # Niche developer roles (surfaced by the day rotation).
        "typescript developer",
        "dotnet developer",
        "c++ developer",
        "golang developer",
        "react developer",
        "web developer",
        "java developer internship",
        "python developer internship",
    ],
    "data": [
        "data analyst",
        "data science",
        "business intelligence analyst",
        "data analytics internship",
        "data engineer",
        "etl developer",
        "sql developer",
        "data engineering",
        "data analyst chennai",
        "data engineer chennai",
        "data analyst bangalore",
        "data engineer bangalore",
        "data analyst internship",
        # Niche data roles (surfaced by the day rotation).
        "power bi developer",
        "tableau developer",
        "machine learning engineer",
        "ml engineer",
        "analytics engineer",
        "database administrator",
        "data science internship",
        "data engineer internship",
        "sql developer chennai",
        "sql developer bangalore",
    ],
    "design": [
        "ux designer",
        "graphic designer",
        "product designer",
        "design internship",
    ],
    "finance": ["finance intern", "accountant", "audit", "finance analyst"],
    "marketing": [
        "marketing intern",
        "digital marketing",
        "sales intern",
        "growth marketing",
    ],
    "govt": [
        # Single tokens first: sarkariresult feed titles name the exam
        # directly ("Railway RRB Junior Engineer JE Online Form 2026"), and
        # the matcher requires every query word, so multi-word AND queries
        # like "government job" would match nothing on that feed.
        "railway",
        "rrb",
        "ssc",
        "upsc",
        "ibps",
        "bank",
        "police",
        "constable",
        "teacher",
        "sarkari",
        "government job",
        "govt job",
        "bank po",
        "sbi recruitment",
        "psu recruitment",
        "defence jobs",
        "army recruitment",
        "police recruitment",
        "government internship",
        # Niche govt roles (surfaced by the day rotation).
        "gramin dak sevak",
        "post office",
        "teaching recruitment",
        "central government",
        "state government",
        "navy",
        "air force",
        "customs",
        "income tax",
        "clerk",
        "staff nurse",
        "computer assistant",
        "online form",
        "admit card",
    ],
    "other": ["internship", "entry level", "graduate trainee"],
}

# City tokens that may already appear at the end of a base DOMAIN_QUERIES
# entry ("frontend developer chennai", "data engineer bangalore", ...).
# Location suffixing skips these so a query never ends up with two cities.
_BASE_QUERY_CITIES = (
    "bangalore",
    "bengaluru",
    "chennai",
    "coimbatore",
    "mumbai",
    "delhi",
    "hyderabad",
    "pune",
    "kolkata",
    "noida",
    "gurgaon",
    "gurugram",
    "india",
)


def _query_already_located(q: str) -> bool:
    """Whether a base query already ends with an Indian city token."""
    words = q.lower().split()
    return bool(words and words[-1] in _BASE_QUERY_CITIES)


def _fresher_only(prefs: dict) -> bool:
    """True when the user's saved experience levels mean fresher-only.

    Empty / unset experience_levels means "all levels", and any mid/senior
    level means mixed — neither is fresher-only.
    """
    levels = {
        str(x).strip().lower()
        for x in (prefs.get("experience_levels") or [])
        if str(x).strip()
    }
    if not levels:
        return False
    return levels.issubset({"entry", "junior", "intern", "fresher"})


def discovery_queries_for(prefs: dict, user=None, limit: int = 4) -> list[str]:
    """Search queries matching a user's alert domains + resume skills.

    Domain keywords produce the bulk of the queries; up to three skills from
    the user's profile are appended as ``<skill> intern`` searches so niche
    roles (e.g. VAPT, Burp Suite) get discovered too. Deduplicated and
    capped at ``limit``.
    """
    domains = prefs.get("domains") or []
    queries: list[str] = []
    for domain in domains:
        queries.extend(DOMAIN_QUERIES.get(domain, []))
    if not domains:
        # Use default domain (cybersecurity) when no preferences set
        for d in DEFAULT_DOMAINS:
            queries.extend(DOMAIN_QUERIES.get(d, [])[:4])
        queries.extend(DOMAIN_QUERIES["other"][:1])
    if user is not None:
        for skill in (getattr(user, "skills", None) or [])[:3]:
            skill_name = str(skill).strip()
            if skill_name:
                queries.append(f"{skill_name} intern")
    # Day-based rotation: each daily slot surfaces a different slice of the
    # query list, so niche searches that fall outside the [:limit] cap
    # (vlsi, sdet, labview, iot engineer, ...) still get run over the
    # course of a week instead of the same top-4 forever.
    shift = datetime.now(UTC).toordinal() % max(len(queries), 1)
    if shift:
        queries = queries[shift:] + queries[:shift]
    # Location-aware: location-suffixed queries go FIRST so the [:limit] cap
    # keeps them (a Bangalore user's alerts should search "cybersecurity
    # bangalore" before plain "cybersecurity"). The dedupe below then drops
    # the redundant plain duplicates when the limit allows more queries.
    location = (getattr(user, "location", None) or "").strip() if user else ""
    if not location:
        location = DEFAULT_LOCATION
    # A profile may list several cities ("chennai, bangalore, coimbatore").
    # Split them and cycle round-robin over the base queries so EVERY city
    # gets a search within the limit — mashing them into one
    # "engineer chennai, bangalore, coimbatore" blob made every scraper miss.
    cities = [
        part.strip() for part in re.split(r"\s*[,/]\s*", location) if part.strip()
    ] or [location]
    located_queries: list[str] = []
    for idx, q in enumerate(list(queries)):
        city = cities[idx % len(cities)]
        # Skip base queries that already end in a city (e.g.
        # "frontend developer bangalore") so a profile city never produces
        # a double-city query like "frontend developer bangalore chennai".
        if not _query_already_located(q) and city.lower() not in q.lower():
            located_queries.append(f"{q} {city}")
    queries = located_queries + list(queries)
    # Fresher-only members (experience_levels = ["entry", "junior"]) get
    # fresher-flavored searches so discovery finds fresher roles instead of
    # finding mid/senior roles that the experience gate then has to drop.
    # Only the first ``limit // 2`` queries are fresher-suffixed — the rest
    # stay plain so postings that don't literally say "fresher" still get
    # discovered (the experience gate filters the rest downstream).
    if _fresher_only(prefs) and queries:
        fresher_count = max(1, min(limit // 2, len(queries)))
        queries = [f"{q} fresher" for q in queries[:fresher_count]] + queries[
            fresher_count:
        ]
    seen: set[str] = set()
    unique: list[str] = []
    for query in queries:
        key = query.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(query.strip())
    return unique[:limit]


async def verify_job_links():
    """Verify job links are still active."""
    async with get_db_session() as session:
        from interntrack.engines.verification import VerificationEngine

        engine = VerificationEngine(session)
        results = await engine.verify_all_links()

        dead_links = [r for r in results if not r.get("is_alive")]
        if dead_links:
            print(f"[{datetime.now(UTC)}] Found {len(dead_links)} dead links")


async def archive_old_jobs(days: int = 30):
    """Archive jobs older than N days to keep the database lean."""
    async with get_db_session() as session:
        from interntrack.repositories.job_repository import JobRepository

        repo = JobRepository(session)
        count = await repo.archive_expired_jobs(days=days)
        if count > 0:
            print(f"[{datetime.now(UTC)}] Archived {count} expired jobs")


async def deactivate_expired_jobs():
    """Deactivate expired job listings."""
    async with get_db_session() as session:
        service = JobService(session)
        count = await service.deactivate_expired()
        if count > 0:
            print(f"[{datetime.now(UTC)}] Deactivated {count} expired jobs")
