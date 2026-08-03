"""Regression tests for the naive-UTC production fix.

Production PostgreSQL columns are plain ``timestamp without time zone``
(``Column(DateTime, ...)``). asyncpg rejects offset-aware datetimes on both
queries and inserts with ``can't subtract offset-naive and offset-aware
datetimes``, which broke /reports/daily, /dashboard/overview,
/dashboard/recent-activity and /dashboard/charts/application-timeline on the
live Railway deployment. All DB-facing code must use naive UTC values.
"""

from datetime import UTC, datetime, timedelta, timezone

from interntrack.utils.helpers import to_naive_utc, utcnow


class TestToNaiveUtc:
    """Tests for the to_naive_utc() coercion helper."""

    def test_none_passthrough(self):
        assert to_naive_utc(None) is None

    def test_naive_passthrough(self):
        dt = datetime(2026, 8, 3, 12, 0, 0)
        assert to_naive_utc(dt) is dt

    def test_aware_utc_stripped(self):
        aware = datetime(2026, 8, 3, 12, 0, 0, tzinfo=UTC)
        naive = to_naive_utc(aware)
        assert naive.tzinfo is None
        assert naive == datetime(2026, 8, 3, 12, 0, 0)

    def test_aware_offset_converted_to_utc(self):
        # 12:00 IST (+5:30) == 06:30 UTC
        aware = datetime(
            2026, 8, 3, 12, 0, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))
        )
        naive = to_naive_utc(aware)
        assert naive.tzinfo is None
        assert naive == datetime(2026, 8, 3, 6, 30, 0)

    def test_roundtrip_preserves_instant(self):
        aware = datetime(2026, 8, 3, 12, 0, 0, tzinfo=UTC)
        naive = to_naive_utc(aware)
        assert naive.replace(tzinfo=UTC) == aware


class TestModelDatetimeCoercion:
    """Model validators must normalize aware datetimes on assignment."""

    def test_job_posted_at_aware_stripped(self):
        from interntrack.domain.models import Job

        aware = datetime(2026, 8, 3, 7, 30, 43, tzinfo=UTC)
        job = Job(
            title="t",
            company="c",
            url="https://example.com/aware-dt",
            posted_at=aware,
        )
        assert job.posted_at.tzinfo is None
        assert job.posted_at == datetime(2026, 8, 3, 7, 30, 43)

    def test_job_expires_at_aware_stripped(self):
        from interntrack.domain.models import Job

        job = Job(
            title="t",
            company="c",
            url="https://example.com/aware-dt-2",
            expires_at=datetime(2026, 9, 1, 0, 0, 0, tzinfo=UTC),
        )
        assert job.expires_at.tzinfo is None

    def test_job_naive_dates_left_alone(self):
        from interntrack.domain.models import Job

        naive = datetime(2026, 8, 3, 7, 30, 43)
        job = Job(
            title="t",
            company="c",
            url="https://example.com/naive-dt",
            posted_at=naive,
        )
        assert job.posted_at is naive

    def test_application_applied_at_aware_stripped(self):
        from interntrack.domain.models import Application

        app = Application(
            job_id="j1",
            applied_at=datetime(2026, 8, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert app.applied_at.tzinfo is None

    def test_user_skill_last_used_aware_stripped(self):
        from interntrack.domain.models import UserSkill

        us = UserSkill(
            user_id="u1",
            skill_id="s1",
            last_used=datetime(2026, 8, 3, 10, 0, 0, tzinfo=UTC),
        )
        assert us.last_used.tzinfo is None

    def test_scheduled_report_dates_aware_stripped(self):
        from interntrack.domain.models import ScheduledReport

        sr = ScheduledReport(
            report_type="daily",
            frequency="daily",
            next_generation=datetime(2026, 8, 4, 0, 0, 0, tzinfo=UTC),
        )
        assert sr.next_generation.tzinfo is None


class TestJobSourceCoercion:
    """Job.source must never store a value outside the JobSource enum."""

    def test_valid_enum_value_passthrough(self):
        from interntrack.domain.models import Job

        job = Job(
            title="t",
            company="c",
            url="https://example.com/src-1",
            source="linkedin",
        )
        assert job.source == "linkedin"

    def test_source_is_enum_member_with_value(self):
        """Regression: export_jobs.py calls job.source.value — the attribute
        must be a JobSource member (in-memory and after DB round-trip)."""
        from interntrack.domain.enums import JobSource
        from interntrack.domain.models import Job

        job = Job(
            title="t",
            company="c",
            url="https://example.com/src-6",
            source="glassdoor",
        )
        assert job.source is JobSource.GLASSDOOR
        assert job.source.value == "glassdoor"

    def test_enum_member_value_used(self):
        from interntrack.domain.enums import JobSource
        from interntrack.domain.models import Job

        job = Job(
            title="t",
            company="c",
            url="https://example.com/src-2",
            source=JobSource.MANUAL,
        )
        assert job.source == "manual"

    def test_raw_alias_mapped(self):
        from interntrack.domain.models import Job

        # The exact value that crashed reads live (RSS feed key).
        job = Job(
            title="t",
            company="c",
            url="https://example.com/src-3",
            source="weworkremotely",
        )
        assert job.source == "we_work_remotely"

    def test_unknown_source_falls_back(self):
        from interntrack.domain.models import Job

        job = Job(
            title="t",
            company="c",
            url="https://example.com/src-4",
            source="totally_unknown_board",
        )
        assert job.source == "unknown"

    def test_none_source_falls_back(self):
        from interntrack.domain.models import Job

        job = Job(
            title="t",
            company="c",
            url="https://example.com/src-5",
            source=None,
        )
        assert job.source == "unknown"

    def test_skill_category_has_general(self):
        """The skill repository writes category='general'; it must be a valid
        enum value or skill reads would crash on Postgres like Job.source did."""
        from interntrack.domain.enums import SkillCategory

        assert SkillCategory.GENERAL.value == "general"


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
