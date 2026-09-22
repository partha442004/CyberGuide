"""
Daily job archive endpoint — the git-based, day-by-day job history.

Every digest send already records the exact jobs each member received in
``NotificationHistory.jobs``.  This endpoint turns those rows into a single
JSON document shaped for committing into the repo by the daily workflow:

    archive/2026/09/2026-09-22.json

Why an archive at all: the Neon free tier is the only copy of delivery
history, and the retention purge deletes old jobs rows.  A git archive is
free, versioned, browsable day-by-day / month-by-month, and doubles as
disaster recovery.

Privacy: the repository is PUBLIC, so member identities never leave the
API — ``user_id`` values are irreversibly hashed (deterministic, so the
same member maps to the same key across days, enabling user-wise tracking)
and only public job data (title, company, location, apply URL) is emitted.
"""

import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.deps import require_cron_secret
from interntrack.database.session import get_db
from interntrack.domain.models import NotificationHistory
from interntrack.utils.helpers import to_naive_utc

router = APIRouter()

# How far back to sweep NotificationHistory for archiveable sends.  The
# daily digest fires at 08:00 IST (02:30 UTC) and catch-ups run on the
# afternoon slots of the SAME UTC day, so 48h comfortably covers a full
# day's sends while excluding everything older.
_LOOKBACK_HOURS = 48

# Job fields safe (and useful) to publish.  Anything else on the stored
# digest card — internal ids, tracking fields — is dropped here.
_JOB_FIELDS = ("title", "company", "location", "url", "domain", "match_score")

# Salt keeps the hash from being a trivially reversible user_id rainbow
# table (ids are uuid4, so this is belt-and-braces, but costs nothing).
_HASH_SALT = "interntrack-archive-v1"


def _member_key(user_id: str) -> str:
    """Deterministic anonymous member key (stable across days/commits)."""
    digest = hashlib.sha256(f"{_HASH_SALT}:{user_id}".encode()).hexdigest()
    return f"member-{digest[:8]}"


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


async def _collect_digest_rows(db: AsyncSession) -> list:
    """NotificationHistory rows from the lookback window that carry jobs."""
    now = to_naive_utc(datetime.now(UTC)) or datetime.now(UTC).replace(tzinfo=None)
    since = now - timedelta(hours=_LOOKBACK_HOURS)
    result = await db.execute(
        select(NotificationHistory)
        .where(NotificationHistory.created_at >= since)
        .order_by(NotificationHistory.created_at.asc())
    )
    return list(result.scalars().all())


@router.get("/daily-archive")
async def daily_archive(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_cron_secret),
):
    """Build today's archive document from the last 48h of digest sends.

    Response shape (one file per UTC day, committed by the workflow):
    ``{date, generated_at, totals, members: [{member, domains, job_count,
    jobs: [...]}]}``.  Returns ``members: []`` on quiet days so the
    workflow skips the commit instead of creating empty history.
    """
    rows = await _collect_digest_rows(db)

    members: dict[str, dict] = {}
    for row in rows:
        stored_jobs = getattr(row, "jobs", None)
        if not isinstance(stored_jobs, list):
            continue  # legacy/None shapes carry no archiveable cards
        user_id = str(getattr(row, "user_id", "") or "")
        if not user_id:
            continue

        entry = members.setdefault(
            _member_key(user_id),
            {
                "member": _member_key(user_id),
                "domains": [
                    str(d)
                    for d in (getattr(row, "domains", None) or [])
                    if str(d).strip()
                ]
                or [],
                "jobs": {},
            },
        )
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
