"""
Scheduled background jobs.
"""

import re
from datetime import UTC, datetime

from interntrack.database.session import get_db_session
from interntrack.services.job_service import JobService
from interntrack.services.notification_service import NotificationManager
from interntrack.services.report_service import ReportService, classify_domain


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
                "paused_until": getattr(pref, "paused_until", None),
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
            report,
            session,
            domains=domains,
            title=title,
            user_id=user_id,
            user_location=user_location,
            include_remote=include_remote,
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
            loc_lower = (getattr(user, "location", None) or "").strip().lower()
            matches = []
            for job in saved_jobs:
                title = str(getattr(job, "title", "") or "")
                tags = list(getattr(job, "tags", None) or [])
                job_domain = classify_domain(title, tags)
                if domains and job_domain not in domains:
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
    # Each user's digest is scoped to *their* city (synonym-aware), so two
    # accounts on the same domain never see each other's locations. The
    # legacy default user (no profile) falls back to DEFAULT_LOCATION so
    # their digest is city-scoped too, not every-city.
    user_location = (
        (getattr(user, "location", None) or "").strip() or DEFAULT_LOCATION or None
    )
    include_remote = bool(prefs.get("include_remote", True))
    service = ReportService(session)
    report = await service.generate_daily_report(
        domains=domains,
        min_match_score=prefs.get("min_match_score"),
        since=prefs.get("last_alert_at"),
        location=user_location,
        include_remote=include_remote,
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
            if _alerts_paused(prefs):
                print(f"[{datetime.now(UTC)}] Daily report skipped — alerts paused")
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
            if _alerts_paused(target["prefs"]):
                print(
                    f"[{datetime.now(UTC)}] Daily report skipped for "
                    f"{target['user_id']} — alerts paused"
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
    "frontend": "🖥️ Frontend / UI",
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
    salary = _salary_txt(job)
    if salary:
        lines.append(f"   💰 {salary}")
    exp_level = str(job.get("experience_level") or "").strip()
    if exp_level:
        lines.append(f"   🎓 {exp_level}")
    desc = _job_desc_snippet(job)
    if desc:
        # Escaped: Telegram sends with HTML parse mode and scraped
        # descriptions routinely contain <, >, & (and leftover tags).
        lines.append(f"   📝 {_esc(desc)}")
    if url:
        lines.append(f"   🔗 Apply: {url}")
    note = _expiry_note(job)
    if note:
        lines.append(note)
    return lines


_HTML_TAG_RE = re.compile(r"<[^>]*>")


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
    user_location: str | None = None,
    include_remote: bool = True,
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
                lines.extend(_job_lines(score, job))
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
    return chunks


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
    d_order = ["security", "coding", "data", "design", "finance", "marketing", "other"]
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

    parts.append(
        "<p style='color:#64748b;font-size:12px;margin-top:22px;'>"
        "Match % = how well your uploaded resume fits each job · "
        "✅/⬜ = applied / not applied.</p></div>"
    )
    return "".join(parts)


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
    salary = _esc(_salary_txt(job))
    exp_level = _esc(str(job.get("experience_level") or "").strip())
    meta_bits = [bit for bit in (status_txt, expiry, salary, exp_level) if bit]
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
    desc = _esc(_job_desc_snippet(job, limit=240))
    if desc:
        card += (
            "<div style='margin-top:8px;padding:8px 10px;background:#f8fafc;"
            "border-left:3px solid " + accent + ";border-radius:6px;"
            "color:#475569;font-size:13px;line-height:1.45;'>" + desc + "</div>"
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
    # Location-aware: location-suffixed queries go FIRST so the [:limit] cap
    # keeps them (a Bangalore user's alerts should search "cybersecurity
    # bangalore" before plain "cybersecurity"). The dedupe below then drops
    # the redundant plain duplicates when the limit allows more queries.
    location = (getattr(user, "location", None) or "").strip() if user else ""
    if not location:
        location = DEFAULT_LOCATION
    located_queries: list[str] = []
    if location:
        for q in list(queries):
            if location.lower() not in q.lower():
                located_queries.append(f"{q} {location}")
    queries = located_queries + list(queries)
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
