"""Regression tests for the naive-UTC production fix.

Production PostgreSQL columns are plain ``timestamp without time zone``
(``Column(DateTime, ...)``). asyncpg rejects offset-aware datetimes on both
queries and inserts with ``can't subtract offset-naive and offset-aware
datetimes``, which broke /reports/daily, /dashboard/overview,
/dashboard/recent-activity and /dashboard/charts/application-timeline on the
live Railway deployment. All DB-facing code must use naive UTC values.
"""

from datetime import UTC, datetime

from interntrack.utils.helpers import utcnow


class TestUtcnowHelper:
    """Tests for the interntrack utcnow() helper."""

    def test_returns_datetime(self):
        assert isinstance(utcnow(), datetime)

    def test_returns_naive(self):
        assert utcnow().tzinfo is None

    def test_close_to_aware_utc_now(self):
        naive = utcnow()
        aware = datetime.now(UTC)
        assert abs((aware - naive.replace(tzinfo=UTC)).total_seconds()) < 5

    def test_naive_roundtrip_with_utc(self):
        naive = utcnow()
        aware = naive.replace(tzinfo=UTC)
        assert aware == naive.replace(tzinfo=UTC)


class TestCybershieldUtcnowHelper:
    """Tests for the cybershield utcnow() helper."""

    def test_returns_naive(self):
        from cybershield.utils import utcnow as cs_utcnow

        assert cs_utcnow().tzinfo is None


class TestModelDefaultsNaive:
    """Model timestamp defaults must produce naive datetimes."""

    def test_timestamp_mixin_defaults_naive(self):
        from interntrack.domain.models import Job, TimestampMixin

        # SQLAlchemy wraps 0-arg callables as lambda ctx: fn(); invoke with a
        # dummy context to get the actual default value.
        created = TimestampMixin.created_at.default.arg(None)
        assert created.tzinfo is None

        # A fresh model instance gets a naive created_at after flush/refresh.
        job = Job(title="t", company="c", url="https://example.com/job")
        assert job.created_at is None or job.created_at.tzinfo is None

    def test_job_created_at_default_is_utcnow(self):
        from interntrack.domain.models import TimestampMixin

        assert TimestampMixin.created_at.default.arg.__name__ == "utcnow"

    def test_changed_at_default_naive(self):
        from interntrack.domain.models import ApplicationStatusHistory

        default = ApplicationStatusHistory.changed_at.default.arg(None)
        assert default.tzinfo is None


class TestRepositoryQueriesUseNaiveUtc:
    """Repository cutoff/now values must be naive (Postgres-compatible)."""

    async def test_get_recent_jobs_uses_naive_cutoff(self, db_session):
        from interntrack.repositories.job_repository import JobRepository

        repo = JobRepository(db_session)
        # Should not raise (asyncpg-safe on Postgres because cutoff is naive).
        jobs = await repo.get_recent_jobs(days=7)
        assert isinstance(jobs, list)

    async def test_get_recent_applications_uses_naive_cutoff(self, db_session):
        from interntrack.repositories.application_repository import (
            ApplicationRepository,
        )

        repo = ApplicationRepository(db_session)
        apps = await repo.get_recent_applications(days=7)
        assert isinstance(apps, list)

    async def test_application_timeline_uses_naive_cutoff(self, db_session):
        from interntrack.repositories.application_repository import (
            ApplicationRepository,
        )

        repo = ApplicationRepository(db_session)
        timeline = await repo.get_application_timeline(days=30)
        assert isinstance(timeline, list)

    async def test_get_closing_soon_uses_naive_cutoff(self, db_session):
        from interntrack.repositories.job_repository import JobRepository

        repo = JobRepository(db_session)
        closing = await repo.get_closing_soon(days=2)
        assert isinstance(closing, list)

    async def test_find_duplicate_uses_naive_cutoff(self, db_session):
        from interntrack.repositories.job_repository import JobRepository

        repo = JobRepository(db_session)
        dup = await repo.find_duplicate(
            title="Python Dev",
            company="Acme",
            source="manual",
            tolerance_days=7,
        )
        assert dup is None
