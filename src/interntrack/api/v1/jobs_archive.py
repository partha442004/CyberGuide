"""
Daily job archive endpoint — the private-repo, day-by-day job database.

Every digest send already records the exact jobs each member received in
``NotificationHistory.jobs``.  This endpoint turns those rows into a single
JSON document that the daily workflow commits into the SEPARATE PRIVATE
repository ``partha442004/interntrack-jobs-archive``:

    archive/YYYY/MM/YYYY-MM-DD/daily-jobs.json

Because the destination is private, the document carries REAL member
identities (name/email resolved from the ``users`` table) so the owner can
browse "jobs according to user" directly.  Nothing member-identifying is
ever committed to the public CyberGuide repo — only this endpoint's
response (transient, secret-guarded) and the private repo hold identities.
"""

import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.deps import require_cron_secret
from interntrack.database.session import get_db
from interntrack.domain.models import NotificationHistory, User
from interntrack.utils.helpers import to_naive_utc

router = APIRouter()

# Fallback anonymous key for rows whose user has no resolvable profile
# (e.g. the legacy default account).  Deterministic so a given user_id
# always maps to the same placeholder across days.
_HASH_SALT = "interntrack-archive-v1"

# Job fields that make the archive useful for browsing.  Anything else on
# the stored digest card — internal ids, tracking fields — is dropped.
_JOB_FIELDS = ("title", "company", "location", "url", "domain", "match_score")


def _member_fallback_key(user_id: str) -> str:
    """Deterministic anonymous fallback key for profile-less user ids."""
    digest = hashlib.sha256(f"{_HASH_SALT}:{user_id}".encode()).hexdigest()
    return f"unresolved-{digest[:8]}"


def _clean_job(card) -> dict | None:
    """Keep only the publishable fields of a stored digest job card."""
    if not isinstance(card, dict):
        return None
    url = str(card.get("url") or "").strip()
    title = str(card.get("title") or "").strip()
    if not url or not title:
        return None
    return {
        field: card.get(field)
        for field in _JOB_FIELDS
        if card.get(field) not in (None, "")
    }


def _window_start(days: int, now: datetime | None = None) -> datetime:
    """Naive-UTC start of the lookback window covering ``days`` calendar days.

    ``days=1`` (the default) means "since UTC midnight today" so each daily
    file contains exactly that day's deliveries — a fixed 48h window would
    re-include yesterday's rows (already archived in yesterday's file).
    Larger values are for the one-time seed/backfill of the private repo.
    """
    now = now or to_naive_utc(datetime.now(UTC))
    now = now or datetime.now(UTC).replace(tzinfo=None)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=days - 1)


async def _collect_digest_rows(db: AsyncSession, since: datetime) -> list:
    """NotificationHistory rows from ``since`` onward that carry jobs."""
    result = await db.execute(
        select(NotificationHistory)
        .where(NotificationHistory.created_at >= since)
        .order_by(NotificationHistory.created_at.asc())
    )
    return list(result.scalars().all())


async def _load_user_index(db: AsyncSession) -> dict[str, dict]:
    """``{user_id: {name, email}}`` for every profile in the users table."""
    result = await db.execute(select(User))
    index: dict[str, dict] = {}
    for user in result.scalars().all():
        index[str(user.id)] = {
            "name": str(getattr(user, "name", "") or "").strip(),
            "email": str(getattr(user, "email", "") or "").strip().lower(),
        }
    return index


@router.get("/daily-archive")
async def daily_archive(
    days: int = Query(default=1, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_cron_secret),
):
    """Build an archive document from recent digest sends.

    Default window is today (UTC) only; the daily workflow commits that
    into the private archive repo as ``archive/YYYY/MM/YYYY-MM-DD/``.
    ``?days=N`` widens the window to the last N calendar days — used for
    the one-time seed of the private repo (the document lands under
    today's date; it is a merged backfill, not per-day files).

    Response shape: ``{date, generated_at, totals, members: [{name,
    email, domains, job_count, jobs: [...]}]}``.  Returns ``members: []``
    when the window has no delivered jobs so the workflow skips the
    commit instead of creating empty history.
    """
    rows = await _collect_digest_rows(db, _window_start(days))
    users = await _load_user_index(db)

    members: dict[str, dict] = {}
    for row in rows:
        stored_jobs = getattr(row, "jobs", None)
        if not isinstance(stored_jobs, list):
            continue  # legacy/None shapes carry no archiveable cards
        user_id = str(getattr(row, "user_id", "") or "")
        if not user_id:
            continue

        profile = users.get(user_id)
        if profile and profile["email"]:
            identity = f"{profile['name']} <{profile['email']}>"
        else:
            identity = _member_fallback_key(user_id)

        entry = members.setdefault(
            identity,
            {
                "name": profile["name"] if profile else None,
                "email": profile["email"] if profile else None,
                "member": identity,
                "domains": [],
                "jobs": {},
            },
        )
        # Latest non-empty domains win (a member may change prefs mid-day).
        raw_domains = getattr(row, "domains", None) or []
        row_domains = [str(d) for d in raw_domains if str(d).strip()]
        if row_domains:
            entry["domains"] = row_domains
        # Merge multiple sends (digest + catch-up) per member, deduped by URL.
        for card in stored_jobs:
            cleaned = _clean_job(card)
            if cleaned:
                entry["jobs"][cleaned["url"]] = cleaned

    member_list = []
    for entry in members.values():
        jobs = list(entry.pop("jobs").values())
        if not jobs:
            continue
        entry["job_count"] = len(jobs)
        entry["jobs"] = jobs
        member_list.append(entry)
    member_list.sort(key=lambda m: (-m["job_count"], m["member"]))

    return {
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "totals": {
            "members_with_jobs": len(member_list),
            "jobs_delivered": sum(m["job_count"] for m in member_list),
        },
        "members": member_list,
    }
