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
        }
    results: dict = {}
    non_telegram = [c for c in targets if c != "telegram"]
    email_targets = [c for c in non_telegram if c == "email"]
    text_targets = [c for c in non_telegram if c != "email"]
    if email_targets:
        # Email gets the styled HTML digest; other text channels stay plain.
        user_location = getattr(user, "location", None) if user else None
        html = await build_daily_report_html(
            report,
            session,
            domains=domains,
            title=title,
            user_id=user_id,
            user_location=user_location,
        )
        if recipient:
            results.update(
                await manager.notify(
                    email_targets, html, subject=subject, recipient=recipient
                )
            )
        else:
            results.update(await manager.notify(email_targets, html, subject=subject))
    if text_targets:
        message = await build_daily_report_message(
            report, session, domains=domains, title=title, user_id=user_id
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
            report, session, domains=domains, weekly=weekly, user_id=user_id
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


async def _send_alert_for(session, user_id: str, prefs: dict, user=None) -> None:
    """Build and deliver one user's daily digest (per-user resume + window).

    Honors the saved domains / channels / min match %, advances that user's
    no-duplicates window, delivers to the user's own channels and records
    the send in that user's history.
    """
    domains = prefs.get("domains") or None
    service = ReportService(session)
    report = await service.generate_daily_report(
        domains=domains,
        min_match_score=prefs.get("min_match_score"),
        since=prefs.get("last_alert_at"),
    )

    await _mark_alert_sent(session, user_id)
    if not (report.get("new_jobs") or []):
        print(
            f"[{datetime.now(UTC)}] Daily report for {user_id}: "
            "no new jobs since last alert"
        )
        return

    manager = NotificationManager(session)
    subject = "Daily Report"
    if domains:
        subject += f" ({', '.join(domains)})"
    results = await _deliver_alert(
        manager,
        prefs.get("channels") or None,
        report,
        session,
        domains=domains,
        subject=subject,
        user=user,
    )
    await _record_alert_history(
        session,
        user_id=user_id,
        subject=subject,
        channels=prefs.get("channels") or list(results.keys()),
        domains=domains or [],
        job_count=len(report.get("new_jobs") or []),
        results=results,
    )


async def generate_daily_report():
    """Generate and send daily reports for every user with alerts enabled.

    Each registered account gets a personalized digest: their own domains,
    their own resume match %, their own no-duplicates window, delivered to
    their own email / Telegram and recorded in their own history. When no
    accounts exist yet, the legacy single-user path (``user1``) is used so
    pre-account deployments behave exactly as before.
    """
    async with get_db_session() as session:
        targets = await _enabled_alert_targets(session)
        if not targets:
            # Legacy single-user fallback (no registered accounts yet).
            prefs = await _load_alert_preferences(session)
            if prefs.get("is_enabled") is False:
                print(f"[{datetime.now(UTC)}] Daily report skipped — alerts disabled")
                return
            await _send_alert_for(session, DEFAULT_ALERT_USER, prefs, None)
            return

        for target in targets:
            if target["prefs"].get("is_enabled") is False:
                print(
                    f"[{datetime.now(UTC)}] Daily report skipped for "
                    f"{target['user_id']} — alerts disabled"
                )
                continue
            await _send_alert_for(
                session,
                target["user_id"],
                target["prefs"],
                target["user"],
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
    user_id: str | None = None,
) -> list[tuple[str, list[tuple[float | None, dict]]]]:
    """Score, filter and group the report's jobs into domain sections.

    Returns a list of ``(domain, [(score, job), ...])`` ordered by the
    canonical domain order, jobs within each section sorted by match score.
    ``report['min_match_score']`` drops jobs below the threshold.
    """
    jobs = report.get("new_jobs") or []
    if not jobs:
        return []
    resume_skills = await _latest_resume_skill_names(session, user_id=user_id)
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
    user_id: str | None = None,
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
    for domain, items in sections:
        lines.append("")
        lines.append(f"{_DOMAIN_ICONS.get(domain, domain)} ({len(items)}):")
        for score, job in items:
            lines.extend(_job_lines(score, job))

    # Watched-company jobs get their own highlight section.
    watched_jobs = _watched_jobs(report, await _watched_company_names(session, user_id))
    if watched_jobs:
        lines.append("")
        lines.append(f"🏢 Watched companies ({len(watched_jobs)}):")
        for job in watched_jobs:
            lines.extend(_job_lines(None, job))

    if sections or watched_jobs:
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
    user_id: str | None = None,
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Split the alert digest into Telegram-sized chunks with Apply buttons.

    Telegram truncates messages at 4096 chars, so a 15-job digest is sent
    as several messages. Each chunk returns ``(text, buttons)`` where
    ``buttons`` is a list of ``(label, url)`` pairs rendered as an inline
    keyboard on Telegram.
    """
    title = "📅 Weekly Digest" if weekly else "📊 Daily Report"
    sections = await _score_and_group_jobs(report, session, domains, user_id=user_id)
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
                if _location_matches(job_loc, loc_lower):
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
            f"<div style='font-size:20px;font-weight:800;'>{_esc(title)}</div>"
            f"<div style='opacity:.85;font-size:13px;'>{_esc(generated)}</div>"
            f"<div style='margin-top:10px;font-size:14px;'>"
            f"New jobs: <b>{summary.get('new_jobs', 0)}</b> · "
            f"New applications: <b>{summary.get('new_applications', 0)}</b></div></div>"
        ),
    ]

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
            parts.append(_job_html_card(score, job, style))

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
            parts.append(_job_html_card(None, job, "#0ea5e9"))

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
                parts.append(_job_html_card(score, job, accent))

    # Role x location breakdown table
    if loc_lower:
        parts.append(
            _location_breakdown_table(location_sections, other_sections, loc_lower)
        )

    parts.append(
        "<p style='color:#64748b;font-size:12px;margin-top:22px;'>"
        "Match % = how well your uploaded resume fits each job · "
        "✅/⬜ = applied / not applied.</p></div>"
    )
    return "".join(parts)


def _location_matches(job_loc, user_loc):
    """Fuzzy location match with synonyms."""
    if not job_loc or not user_loc:
        return False
    if user_loc in job_loc:
        return True
    synonyms = {
        "bangalore": ["bengaluru", "bengalore"],
        "bengaluru": ["bangalore", "bengalore"],
        "mumbai": ["bombay"],
        "bombay": ["mumbai"],
        "delhi": ["new delhi", "ncr"],
        "hyderabad": ["secunderabad"],
    }
    for canonical, alts in synonyms.items():
        if user_loc == canonical and any(a in job_loc for a in alts):
            return True
        if user_loc in alts and canonical in job_loc:
            return True
    return False


def _location_breakdown_table(sections, other_sections):
    """HTML table: job counts by domain x top locations."""
    all_jobs = []
    for _, items in (sections or []) + (other_sections or []):
        all_jobs.extend(items)
    if not all_jobs:
        return ""
    from collections import Counter

    dom_loc = {}
    for _, job in all_jobs:
        d = job.get("domain") or "other"
        loc = (job.get("location") or "Remote")[:30]
        dom_loc.setdefault(d, Counter())
        dom_loc[d][loc] += 1
    loc_totals = Counter()
    for c in dom_loc.values():
        loc_totals.update(c)
    top_locs = [loc for loc, _ in loc_totals.most_common(6)]
    if not top_locs:
        return ""
    d_order = ["security", "coding", "data", "design", "finance", "marketing", "other"]
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


def _job_html_card(score, job: dict, accent: str) -> str:
    """One job as an HTML card with an Apply button."""
    title = _esc(job.get("title") or "Untitled")
    company = _esc(job.get("company") or "")
    url = _esc(job.get("url") or "")
    location = _esc(job.get("location") or "Remote")
    score_txt = f"{score:.0f}%" if score is not None else "—"
    applied = job.get("is_applied", False)
    status_txt = "✅ Applied" if applied else "⬜ Not applied"
    age = _age_badge(int(job.get("age_days", 0) or 0))
    expiry = _esc(_expiry_note(job).strip())
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
        f"{status_txt}{(' · ' + expiry) if expiry else ''}</div>"
    )
    if url:
        card += (
            "<div style='margin-top:10px;'>"
            f"<a href='{url}' style='background:{accent};color:#fff;"
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
        "cybersecurity internship",
        "penetration testing",
        "cybersecurity bangalore",
        "soc analyst bangalore",
        "security analyst bangalore",
        "vapt bangalore",
        "penetration testing bangalore",
        "information security bangalore",
        "network security bangalore",
        "application security bangalore",
        "cloud security bangalore",
        "security operations bangalore",
    ],
    "coding": [
        "software engineer",
        "software developer",
        "python developer",
        "full stack developer",
        "software engineering internship",
        "backend developer",
    ],
    "data": [
        "data analyst",
        "data science",
        "business intelligence analyst",
        "data analytics internship",
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
    "other": ["internship", "entry level", "graduate trainee"],
}


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
    # Location-aware: add queries with location appended
    location = (getattr(user, "location", None) or "").strip() if user else ""
    if not location:
        location = DEFAULT_LOCATION
    if location:
        for q in list(queries):
            queries.append(f"{q} {location}")
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


async def deactivate_expired_jobs():
    """Deactivate expired job listings."""
    async with get_db_session() as session:
        service = JobService(session)
        count = await service.deactivate_expired()
        if count > 0:
            print(f"[{datetime.now(UTC)}] Deactivated {count} expired jobs")
