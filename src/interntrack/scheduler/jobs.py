"""
Scheduled background jobs.
"""

from datetime import UTC, datetime

from interntrack.database.session import get_db_session
from interntrack.services.job_service import JobService
from interntrack.services.notification_service import NotificationManager
from interntrack.services.report_service import ReportService


async def run_job_discovery():
    """Periodic job discovery from all sources."""
    async with get_db_session() as session:
        from interntrack.scrapers.registry import get_default_registry

        service = JobService(session)
        registry = get_default_registry()

        jobs = await registry.fetch_all(query="python developer")
        saved = await service.save_jobs(jobs)
        print(f"[{datetime.now(UTC)}] Discovery: {len(jobs)} found, {len(saved)} saved")


# Default user whose alert preferences apply to the scheduled digest.
DEFAULT_ALERT_USER = "user1"

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
            return {
                "domains": list(pref.domains or []),
                "channels": list(pref.channels or []),
                "min_match_score": pref.min_match_score,
                "is_enabled": bool(pref.is_enabled),
                "last_alert_at": pref.last_alert_at,
                "slot_domains": slot_domains,
                "weekly_enabled": weekly if isinstance(weekly, bool) else True,
            }
    except Exception:
        return {}
    return {}


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
) -> None:
    """Persist an alert-send record for the dashboard history view.

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
            )
        )
        await session.commit()
    except Exception:
        with contextlib.suppress(Exception):
            await session.rollback()


async def _deliver_alert(
    manager,
    channels: list | None,
    report: dict,
    session,
    domains: list | None = None,
    subject: str = "InternTrack Daily Alert",
    weekly: bool = False,
) -> dict:
    """Send an alert through the given channels (None = all configured).

    Emails get the full single digest message. Telegram gets the digest
    split into small chunks, each with inline **Apply** buttons linking to
    the job listing. Returns the per-channel delivery results.
    """
    title = "📅 Weekly Digest" if weekly else "📊 Daily Report"
    targets = channels if channels is not None else manager.get_configured_channels()
    results: dict = {}
    non_telegram = [c for c in targets if c != "telegram"]
    if non_telegram:
        message = await build_daily_report_message(
            report, session, domains=domains, title=title
        )
        results.update(await manager.notify(non_telegram, message, subject=subject))
    if "telegram" in targets:
        chunks = await build_alert_chunks(
            report, session, domains=domains, weekly=weekly
        )
        # Every chunk must deliver for the send to count as delivered.
        telegram_ok = True
        for text, buttons in chunks:
            chunk_results = await manager.notify(
                ["telegram"], text, subject=subject, buttons=buttons
            )
            telegram_ok = telegram_ok and bool(chunk_results.get("telegram", False))
        results["telegram"] = telegram_ok
    return results


async def generate_daily_report():
    """Generate and send daily report, honoring saved alert preferences.

    Only jobs created since the previous alert are included (no duplicates
    across the three daily sends), and the send window advances afterwards.
    """
    async with get_db_session() as session:
        prefs = await _load_alert_preferences(session)
        if prefs.get("is_enabled") is False:
            print(f"[{datetime.now(UTC)}] Daily report skipped — alerts disabled")
            return
        domains = prefs.get("domains") or None
        service = ReportService(session)
        report = await service.generate_daily_report(
            domains=domains,
            min_match_score=prefs.get("min_match_score"),
            since=prefs.get("last_alert_at"),
        )

        await _mark_alert_sent(session, DEFAULT_ALERT_USER)
        if not (report.get("new_jobs") or []):
            print(f"[{datetime.now(UTC)}] Daily report: no new jobs since last alert")
            return

        # Send notification via preferred channels (or all configured).
        manager = NotificationManager(session)
        subject = "Daily Report"
        if domains:
            subject += f" ({', '.join(domains)})"
        await _deliver_alert(
            manager,
            prefs.get("channels") or None,
            report,
            session,
            domains=domains,
            subject=subject,
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


async def _latest_resume_skill_names(session) -> set | None:
    """Load the most recently parsed resume's skill names, if any."""
    try:
        from sqlalchemy import select

        from cybershield.api.v1.resumes import _extract_skill_names
        from cybershield.domain.models import ResumeData

        result = await session.execute(
            select(ResumeData).order_by(ResumeData.updated_at.desc()).limit(1)
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
    "coding": "💻 Coding / Software",
    "data": "📊 Data & Analytics",
    "design": "🎨 Design",
    "marketing": "📣 Marketing / Sales",
    "finance": "💰 Finance / Admin",
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


def _job_lines(score, job: dict) -> list[str]:
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
    if url:
        lines.append(f"   🔗 Apply: {url}")
    note = _expiry_note(job)
    if note:
        lines.append(note)
    return lines


async def _score_and_group_jobs(
    report: dict,
    session,
    domains: list | None = None,
) -> list[tuple[str, list[tuple[float | None, dict]]]]:
    """Score, filter and group the report's jobs into domain sections.

    Returns a list of ``(domain, [(score, job), ...])`` ordered by the
    canonical domain order, jobs within each section sorted by match score.
    ``report['min_match_score']`` drops jobs below the threshold.
    """
    jobs = report.get("new_jobs") or []
    if not jobs:
        return []
    resume_skills = await _latest_resume_skill_names(session)
    scored = [(_job_match_score(resume_skills, job), job) for job in jobs]
    min_score = report.get("min_match_score")
    if min_score:
        scored = [(s, job) for s, job in scored if s is None or (s or 0) >= min_score]
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
        "other",
    ]
    sections: list[tuple[str, list[tuple[float | None, dict]]]] = []
    for domain in domain_order:
        items = grouped.get(domain)
        if not items:
            continue
        items.sort(key=lambda item: (item[0] is None, -(item[0] or 0.0)))
        sections.append((domain, items))
    return sections


async def build_daily_report_message(
    report: dict,
    session,
    domains: list | None = None,
    title: str = "📊 Daily Report",
) -> str:
    """Rich daily-report notification: summary counts plus the recent jobs
    grouped by domain (security / coding / data / …), each job carrying its
    apply link, expiry status, age badge, applied marker and match %.

    ``domains`` (when given) only includes those sections and adds a
    "filtered to …" footer; ``report['min_match_score']`` drops jobs whose
    resume match % is below the threshold.
    """
    lines = [format_daily_report(report, title)]
    sections = await _score_and_group_jobs(report, session, domains)
    for domain, items in sections:
        lines.append("")
        lines.append(f"{_DOMAIN_ICONS.get(domain, domain)} ({len(items)}):")
        for score, job in items:
            lines.extend(_job_lines(score, job))

    if sections:
        lines.append("")
        lines.append(
            "Match % = how well your uploaded resume fits each job · "
            "✅/⬜ = applied / not applied."
        )
        if domains:
            lines.append(f"🔔 Filtered to: {', '.join(domains)} only")
    return "\n".join(lines)


async def build_alert_chunks(
    report: dict,
    session,
    domains: list | None = None,
    weekly: bool = False,
    jobs_per_chunk: int = 4,
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Split the alert digest into Telegram-sized chunks with Apply buttons.

    Telegram truncates messages at 4096 chars, so a 15-job digest is sent
    as several messages. Each chunk returns ``(text, buttons)`` where
    ``buttons`` is a list of ``(label, url)`` pairs rendered as an inline
    keyboard on Telegram.
    """
    title = "📅 Weekly Digest" if weekly else "📊 Daily Report"
    sections = await _score_and_group_jobs(report, session, domains)
    flat: list[tuple[str, float | None, dict]] = []
    for domain, items in sections:
        for score, job in items:
            flat.append((domain, score, job))
    if not flat:
        return [(format_daily_report(report, title), [])]

    chunks: list[tuple[str, list[tuple[str, str]]]] = []
    for start in range(0, len(flat), jobs_per_chunk):
        part = flat[start : start + jobs_per_chunk]
        lines = [format_daily_report(report, title)]
        buttons: list[tuple[str, str]] = []
        for domain, score, job in part:
            domain_label = _DOMAIN_ICONS.get(domain, domain)
            if not lines or lines[-1] != domain_label:
                lines.append("")
                lines.append(domain_label)
            lines.extend(_job_lines(score, job))
            url = job.get("url")
            if url:
                # Telegram caps button text at 64 chars.
                job_title = (job.get("title") or "Job").strip()[:60]
                buttons.append((f"✅ Apply — {job_title}", url))
        chunks.append(("\n".join(lines), buttons))
    return chunks


async def verify_job_links():
    """Verify job links are still active."""
    async with get_db_session() as session:
        from interntrack.engines.verification import VerificationEngine

        engine = VerificationEngine(session)
        results = await engine.verify_all_links()

        dead_links = [r for r in results if not r.get("is_alive")]
        if dead_links:
            print(f"[{datetime.now(UTC)}] Found {len(dead_links)} dead links")


async def deactivate_expired_jobs():
    """Deactivate expired job listings."""
    async with get_db_session() as session:
        service = JobService(session)
        count = await service.deactivate_expired()
        if count > 0:
            print(f"[{datetime.now(UTC)}] Deactivated {count} expired jobs")
