"""
Job repository with job-specific queries.
"""

import re
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.enums import JobSource, JobType
from interntrack.domain.models import Job
from interntrack.repositories.base import BaseRepository
from interntrack.utils.helpers import to_naive_utc, utcnow

_DEDUP_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalize_dedup_text(value: str) -> str:
    """Lowercase, collapse punctuation/whitespace for duplicate matching.

    "Penetration Tester (Texas)" and "Penetration Tester - Texas" both
    become "penetrationtestertexas".
    """
    return _DEDUP_NON_ALNUM.sub("", (value or "").lower())


def _created_at_str(job: Job) -> str:
    """Format a job's created_at as a naive UTC string (tz-safe)."""
    dt = to_naive_utc(getattr(job, "created_at", None))
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class JobRepository(BaseRepository[Job]):
    """Job repository with job-specific queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(Job, session)

    async def get_by_url(self, url: str) -> Job | None:
        """Get a job by URL (for deduplication)."""
        result = await self.session.execute(select(Job).where(Job.url == url))
        return result.scalar_one_or_none()

    async def find_duplicate(
        self,
        title: str,
        company: str,
        source: JobSource,
        tolerance_days: int = 7,
    ) -> Job | None:
        """Find potential duplicate job posting."""
        cutoff_date = utcnow() - timedelta(days=tolerance_days)
        query = select(Job).where(
            and_(
                func.lower(Job.title) == title.lower(),
                func.lower(Job.company) == company.lower(),
                Job.source == source,
                Job.created_at >= cutoff_date,
            ),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_cross_source_duplicate(
        self,
        title: str,
        company: str,
        tolerance_days: int = 14,
    ) -> Job | None:
        """Find a job with the same normalized title+company from ANY source.

        The same posting is frequently scraped by several boards (e.g.
        LinkedIn India, Indeed India, TimesJobs, Internshala) under different
        URLs, so URL-based dedup lets 2-3 copies of the same job through.
        Candidates are fetched by company within a recent window, then the
        title is normalized (case-insensitive, punctuation/whitespace
        collapsed) in Python — SQL can't collapse punctuation portably
        across SQLite/Postgres.
        """
        cutoff_date = utcnow() - timedelta(days=tolerance_days)
        norm_title = _normalize_dedup_text(title)
        norm_company = _normalize_dedup_text(company)
        if not norm_title or not norm_company:
            return None
        query = (
            select(Job)
            .where(
                and_(
                    func.lower(Job.company) == company.lower(),
                    Job.created_at >= cutoff_date,
                ),
            )
            .order_by(Job.created_at.desc())
            .limit(50)
        )
        result = await self.session.execute(query)
        for candidate in result.scalars().all():
            if _normalize_dedup_text(str(candidate.title)) == norm_title:
                return candidate
        return None

    async def backfill_job_types(self, limit: int = 500) -> int:
        """Infer job_type for existing jobs still marked unknown.

        Returns the number of rows updated. Used after a deploy so the
        dashboard's job-type chart isn't all "unknown" (scrapers never
        populate job_type, so the classifier fills it in at save time for
        new jobs; this covers jobs saved before the classifier existed).
        """
        from interntrack.services.job_service import classify_job_type

        query = (
            select(Job)
            .where(
                or_(
                    Job.job_type.is_(None),
                    func.lower(Job.job_type) == "unknown",
                ),
            )
            .limit(limit)
        )
        result = await self.session.execute(query)
        jobs = list(result.scalars().all())
        for job in jobs:
            inferred = classify_job_type(str(job.title or ""))
            if inferred != "unknown" and (
                not job.job_type or job.job_type == "unknown"
            ):
                job.job_type = inferred  # type: ignore[assignment]
        await self.session.flush()
        return len([j for j in jobs if j.job_type and j.job_type != "unknown"])

    async def backfill_job_tags(self, limit: int = 500) -> int:
        """Auto-tag existing jobs that have no tags.

        Jobs saved before auto-tagging existed carry ``tags = []`` and
        therefore score ``match_score: null`` against every resume. This
        applies the same title+description keyword derivation to older
        rows so they earn real match/ATS scores too. Returns the number of
        rows updated.
        """
        from interntrack.services.job_service import auto_tag_job

        query = select(Job).order_by(Job.created_at.desc()).limit(int(limit) * 2 + 100)
        result = await self.session.execute(query)
        jobs = list(result.scalars().all())
        updated = 0
        for job in jobs:
            if job.tags:  # already tagged (list is truthy when non-empty)
                continue
            tagged = auto_tag_job({"title": job.title, "description": job.description})
            tags = tagged.get("tags")
            if tags:
                job.tags = tags
                updated += 1
                if updated >= int(limit):
                    break
        if updated:
            await self.session.flush()
        return updated

    async def backfill_engagement(self, limit: int = 1000) -> int:
        """Seed ``view_count`` from real application / bookmark activity.

        Jobs saved before view tracking existed carry ``view_count = 0``
        even when people applied to or bookmarked them, so 🔥 Trending
        under-ranks them. Every application or bookmark implies the job was
        at least viewed once, so this backfills
        ``view_count = max(current, applications + bookmarks)`` for the
        most recent rows. Returns the number of rows updated.
        """
        from interntrack.domain.models import Application, Bookmark

        query = (
            select(Job)
            .where(Job.is_active.is_(True))
            .order_by(Job.created_at.desc())
            .limit(int(limit))
        )
        result = await self.session.execute(query)
        jobs = list(result.scalars().all())
        if not jobs:
            return 0

        job_ids = [j.id for j in jobs]
        app_rows = (
            await self.session.execute(
                select(Application.job_id, func.count(Application.id))
                .where(Application.job_id.in_(job_ids))
                .group_by(Application.job_id)
            )
        ).all()
        app_counts: dict[str, int] = {str(rid): int(cnt) for rid, cnt in app_rows}
        bm_rows = (
            await self.session.execute(
                select(Bookmark.item_id, func.count(Bookmark.id))
                .where(
                    Bookmark.item_type == "job",
                    Bookmark.item_id.in_(job_ids),
                )
                .group_by(Bookmark.item_id)
            )
        ).all()
        bm_counts: dict[str, int] = {str(iid): int(cnt) for iid, cnt in bm_rows}

        pending: list[tuple[str, int]] = []
        for job in jobs:
            implied = app_counts.get(str(job.id), 0) + bm_counts.get(str(job.id), 0)
            if implied > (job.view_count or 0):
                pending.append((str(job.id), implied))
        for job_id, implied in pending:
            await self.session.execute(
                update(Job).where(Job.id == job_id).values(view_count=implied)
            )
        return len(pending)

    async def get_most_engaged(
        self,
        days: int = 7,
        limit: int = 5,
    ) -> list[dict]:
        """Most-engaged jobs of the last N days, for the weekly recap.

        Ranks jobs by the same engagement formula as 🔥 Trending (3 per
        application + 2 per bookmark + 0.5 per view) so the weekly digest
        can lead with what people actually applied to / saved / opened.
        Returns plain dicts (title / company / url / location / counts /
        score); never raises — a failure returns [] so the weekly digest
        is never broken by a stats hiccup.
        """
        try:
            from interntrack.domain.models import Application, Bookmark

            cutoff = utcnow() - timedelta(days=days)
            rows = (
                (
                    await self.session.execute(
                        select(Job).where(
                            Job.is_active.is_(True),
                            Job.created_at >= cutoff,
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not rows:
                return []
            job_ids = [j.id for j in rows]
            app_rows = (
                await self.session.execute(
                    select(Application.job_id, func.count(Application.id))
                    .where(Application.job_id.in_(job_ids))
                    .group_by(Application.job_id)
                )
            ).all()
            app_counts: dict[str, int] = {str(rid): int(cnt) for rid, cnt in app_rows}
            bm_rows = (
                await self.session.execute(
                    select(Bookmark.item_id, func.count(Bookmark.id))
                    .where(
                        Bookmark.item_type == "job",
                        Bookmark.item_id.in_(job_ids),
                    )
                    .group_by(Bookmark.item_id)
                )
            ).all()
            bm_counts: dict[str, int] = {str(iid): int(cnt) for iid, cnt in bm_rows}

            scored: list[dict] = []
            for job in rows:
                views = int(job.view_count or 0)
                apps = int(app_counts.get(str(job.id), 0))
                bms = int(bm_counts.get(str(job.id), 0))
                score = apps * 3 + bms * 2 + views * 0.5
                if score <= 0:
                    continue
                scored.append(
                    {
                        "id": str(job.id),
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "url": job.url,
                        "views": views,
                        "applications": apps,
                        "bookmarks": bms,
                        "engagement_score": round(score, 1),
                    }
                )
            scored.sort(key=lambda item: item["engagement_score"], reverse=True)
            return scored[: int(limit)]
        except Exception:  # noqa: BLE001 - never break the weekly digest
            return []

    async def get_active_jobs(
        self,
        skip: int = 0,
        limit: int = 100,
        job_type: JobType | None = None,
        is_remote: bool | None = None,
        company: str | None = None,
    ) -> list[Job]:
        """Get active jobs with filters."""
        query = select(Job).where(Job.is_active)

        if job_type:
            query = query.where(Job.job_type == job_type)
        if is_remote is not None:
            query = query.where(Job.is_remote == is_remote)
        if company:
            query = query.where(func.lower(Job.company) == company.lower())

        query = query.order_by(Job.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_jobs_by_source(self, source: JobSource) -> list[Job]:
        """Get all jobs from a specific source."""
        query = select(Job).where(Job.source == source)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent_jobs(self, days: int = 7) -> list[Job]:
        """Get active jobs created within the last ``days`` days.

        The window is enforced with a tz-safe string comparison against
        ``created_at`` (avoiding tz-aware / tz-naive comparison failures on
        Neon + asyncpg) so digests only ever see genuinely fresh listings —
        a 7-day window never returns weeks-old jobs, even on a first-ever
        alert when no ``since`` marker exists yet.
        Returns empty list for non-positive ``days``.
        """
        if days <= 0:
            return []
        cutoff = (utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        query = (
            select(Job).where(Job.is_active).order_by(Job.created_at.desc()).limit(500)
        )
        result = await self.session.execute(query)
        return [job for job in result.scalars().all() if _created_at_str(job) >= cutoff]

    async def get_closing_soon(self, days: int = 2) -> list[Job]:
        """Get jobs closing within N days."""
        now = utcnow()
        cutoff = now + timedelta(days=days)
        query = (
            select(Job)
            .where(
                and_(
                    Job.expires_at.isnot(None),
                    Job.expires_at <= cutoff,
                    Job.expires_at >= now,
                    Job.is_active,
                ),
            )
            .order_by(Job.expires_at)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_top_companies(self, limit: int = 10) -> list[tuple[str, int]]:
        """Get top companies by job count."""
        query = (
            select(Job.company, func.count(Job.id).label("count"))
            .where(Job.is_active)
            .group_by(Job.company)
            .order_by(func.count(Job.id).desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [tuple(row) for row in result.all()]

    async def search_jobs(self, query_str: str, limit: int = 50) -> list[Job]:
        """Search jobs by title, company, description, or location."""
        search_term = f"%{query_str}%"
        query = (
            select(Job)
            .where(
                and_(
                    Job.is_active,
                    (
                        Job.title.ilike(search_term)
                        | Job.company.ilike(search_term)
                        | Job.description.ilike(search_term)
                        | Job.location.ilike(search_term)
                    ),
                ),
            )
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_salary_statistics(self) -> dict:
        """Get salary statistics across all jobs."""
        query = select(
            func.min(Job.salary_min).label("min_salary"),
            func.max(Job.salary_max).label("max_salary"),
            func.avg(Job.salary_min).label("avg_min"),
            func.avg(Job.salary_max).label("avg_max"),
        ).where(
            and_(Job.salary_min.isnot(None), Job.salary_max.isnot(None)),
        )
        result = await self.session.execute(query)
        row = result.one()
        return {
            "min_salary": row.min_salary,
            "max_salary": row.max_salary,
            "avg_min": round(row.avg_min, 2) if row.avg_min else None,
            "avg_max": round(row.avg_max, 2) if row.avg_max else None,
        }

    async def get_job_type_distribution(self) -> list[tuple[JobType, int]]:
        """Get job type distribution."""
        query = (
            select(Job.job_type, func.count(Job.id).label("count"))
            .where(Job.is_active)
            .group_by(Job.job_type)
            .order_by(func.count(Job.id).desc())
        )
        result = await self.session.execute(query)
        return [tuple(row) for row in result.all()]

    async def deactivate_expired(self) -> int:
        """Deactivate expired jobs."""
        now = utcnow()
        expired_ids = (
            (
                await self.session.execute(
                    select(Job.id).where(
                        and_(
                            Job.expires_at.isnot(None),
                            Job.expires_at < now,
                            Job.is_active,
                        ),
                    ),
                )
            )
            .scalars()
            .all()
        )

        if expired_ids:
            await self.session.execute(
                update(Job).where(Job.id.in_(expired_ids)).values(is_active=False),
            )
            await self.session.flush()

        return len(expired_ids)

    async def archive_expired_jobs(self, days: int = 30) -> int:
        """Move jobs older than `days` to the expired_jobs archive table.

        Returns the number of jobs archived.
        """
        from datetime import timedelta

        from interntrack.domain.models import ExpiredJob

        cutoff = utcnow() - timedelta(days=days)

        # Find old jobs
        result = await self.session.execute(
            select(Job).where(
                and_(
                    Job.is_active,
                    Job.first_seen_at.isnot(None),
                    Job.first_seen_at < cutoff,
                )
            )
        )
        old_jobs = result.scalars().all()

        if not old_jobs:
            return 0

        archived = 0
        for job in old_jobs:
            # Create archive record
            expired = ExpiredJob(
                id=str(uuid4()),
                original_id=job.id,
                title=job.title,
                company=job.company,
                location=job.location,
                description=job.description,
                url=job.url,
                source=job.source.value if job.source else None,
                job_type=job.job_type.value if job.job_type else None,
                experience_level=job.experience_level.value
                if job.experience_level
                else None,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.salary_currency,
                is_remote=job.is_remote,
                tags=job.tags,
                expired_at=utcnow(),
                reason="stale",
                original_created_at=job.created_at,
            )
            self.session.add(expired)

            # Mark original as inactive
            job.is_active = False  # type: ignore[assignment]
            archived += 1

        await self.session.commit()
        return archived

    async def get_expired_jobs(self, limit: int = 50) -> list:
        """Get archived expired jobs."""
        from interntrack.domain.models import ExpiredJob

        result = await self.session.execute(
            select(ExpiredJob).order_by(ExpiredJob.expired_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def increment_view_count(self, job_id: str) -> int | None:
        """Increment a job's ``view_count``; returns the new count or None.

        Feeds the ``/jobs/trending`` engagement ranking. Returns ``None``
        when the job doesn't exist so callers can 404.
        """
        row = await self.session.execute(select(Job.view_count).where(Job.id == job_id))
        value = row.scalar_one_or_none()
        if value is None:
            return None
        await self.session.execute(
            update(Job).where(Job.id == job_id).values(view_count=Job.view_count + 1)
        )
        return int(value) + 1

    async def get_fresh_jobs(self, limit: int = 100) -> list[Job]:
        """Get only fresh jobs (not expired, not stale)."""
        from datetime import timedelta

        cutoff = utcnow() - timedelta(days=30)
        result = await self.session.execute(
            select(Job)
            .where(
                and_(
                    Job.is_active,
                    or_(
                        Job.first_seen_at.is_(None),
                        Job.first_seen_at >= cutoff,
                    ),
                )
            )
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
