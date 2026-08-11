"""Tests for match-% progress snapshots, the weekly application-stats block,
and the /reports/match-trend helpers."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest


class TestMatchSnapshot:
    """Daily resume-match % snapshots (the progress chart's data source)."""

    @pytest.mark.asyncio
    async def test_returns_none_without_resume(self, monkeypatch):
        from interntrack.scheduler.jobs import _record_match_snapshot

        async def _no_resume(session, user_id=None):
            return None

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._latest_resume_skill_names", _no_resume
        )
        assert await _record_match_snapshot(AsyncMock(), "u1") is None

    @pytest.mark.asyncio
    async def test_records_avg_min_max_and_commits(self, monkeypatch):
        from interntrack.scheduler.jobs import _record_match_snapshot

        async def _resume(session, user_id=None):
            return {"python"}

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._latest_resume_skill_names", _resume
        )

        class _Job:
            def __init__(self, jid):
                self.id = jid
                self.title = f"Job {jid}"
                self.company = "Acme"
                self.required_skills = []
                self.preferred_skills = []
                self.tags = []
                self.domain = "security"
                self.posted_at = None
                self.is_active = True

        jobs = [_Job("j1"), _Job("j2"), _Job("j3"), _Job("j4")]

        def _fake_score(resume_skills, job):
            return {"j1": 50.0, "j2": 70.0, "j3": 90.0, "j4": None}.get(job["id"])

        monkeypatch.setattr("interntrack.scheduler.jobs._job_match_score", _fake_score)

        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def scalars(self):
                return self

            def all(self):
                return self._rows

            def scalar_one_or_none(self):
                return self._rows[0] if self._rows else None

        results = [_Result(jobs), _Result([])]

        class _Session:
            def __init__(self):
                self.added = []
                self.committed = False

            async def execute(self, stmt):
                return results.pop(0)

            def add(self, obj):
                self.added.append(obj)

            async def commit(self):
                self.committed = True

        session = _Session()
        snap = await _record_match_snapshot(session, "u1", domains=["security"])
        assert snap is not None
        # j4 scored None and is skipped -> 3 jobs scored.
        assert snap["jobs_scored"] == 3
        assert snap["avg_match"] == 70.0
        assert snap["min_match"] == 50.0
        assert snap["max_match"] == 90.0
        assert session.committed
        assert len(session.added) == 1
        assert session.added[0].user_id == "u1"
        assert session.added[0].snapshot_date == datetime.now(UTC).date()

    @pytest.mark.asyncio
    async def test_updates_existing_row_for_same_day(self, monkeypatch):
        from interntrack.scheduler.jobs import _record_match_snapshot

        async def _resume(session, user_id=None):
            return {"python"}

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._latest_resume_skill_names", _resume
        )

        class _Job:
            id = "j1"
            title = "Job"
            company = "Acme"
            required_skills = []
            preferred_skills = []
            tags = []
            domain = "security"
            posted_at = None
            is_active = True

        def _fake_score(resume_skills, job):
            return 60.0

        monkeypatch.setattr("interntrack.scheduler.jobs._job_match_score", _fake_score)

        class _Existing:
            def __init__(self):
                self.user_id = "u1"
                self.snapshot_date = datetime.now(UTC).date()
                self.avg_match = 10.0
                self.min_match = 10.0
                self.max_match = 10.0
                self.jobs_scored = 1

        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def scalars(self):
                return self

            def all(self):
                return self._rows

            def scalar_one_or_none(self):
                return self._rows[0] if self._rows else None

        existing_row = _Existing()
        results = [_Result([_Job(), _Job(), _Job()]), _Result([existing_row])]

        class _Session:
            def __init__(self):
                self.added = []

            async def execute(self, stmt):
                return results.pop(0)

            def add(self, obj):
                self.added.append(obj)

            async def commit(self):
                pass

        session = _Session()
        snap = await _record_match_snapshot(session, "u1")
        assert snap is not None
        assert snap["avg_match"] == 60.0
        # Existing row updated in place, no duplicate added.
        assert session.added == []
        assert existing_row.avg_match == 60.0
        assert existing_row.jobs_scored == 3


class TestWeekApplicationStats:
    """The weekly digest's 'Your week in applications' block data."""

    @pytest.mark.asyncio
    async def test_counts_by_status(self):
        from interntrack.scheduler.jobs import _week_application_stats

        class _App:
            def __init__(self, status):
                self.status = status

        class _Result:
            def scalars(self):
                return self

            def all(self):
                return [
                    _App("applied"),
                    _App("applied"),
                    _App("interview"),
                    _App("rejected"),
                ]

        class _Session:
            async def execute(self, stmt):
                return _Result()

        stats = await _week_application_stats(_Session(), "u1")
        assert stats["total"] == 4
        assert stats["status_counts"] == {
            "applied": 2,
            "interview": 1,
            "rejected": 1,
        }

    @pytest.mark.asyncio
    async def test_empty_when_nothing_created(self):
        from interntrack.scheduler.jobs import _week_application_stats

        class _Result:
            def scalars(self):
                return self

            def all(self):
                return []

        class _Session:
            async def execute(self, stmt):
                return _Result()

        assert await _week_application_stats(_Session(), "u1") == {}

    def test_week_stats_parts_labels(self):
        from interntrack.scheduler.jobs import _week_stats_parts

        parts = _week_stats_parts({"applied": 2, "interview": 1})
        assert parts == ["2 applied", "1 interviews"]


class TestWeeklyWeekBlock:
    """The 'Your week in applications' block renders on weekly digests."""

    @pytest.mark.asyncio
    async def test_weekly_message_includes_week_stats(self, monkeypatch):
        from interntrack.scheduler.jobs import build_daily_report_message

        async def _fake_week(session, user_id, days=7):
            return {
                "total": 2,
                "status_counts": {"applied": 1, "interview": 1},
                "days": 7,
            }

        async def _no_salary(session, domains, user_location):
            return None

        async def _no_gap(session, sections, user_id=None, limit=5):
            return []

        async def _no_watched(session, user_id=None):
            return []

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._week_application_stats", _fake_week
        )
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._weekly_salary_insight", _no_salary
        )
        monkeypatch.setattr("interntrack.scheduler.jobs._weekly_skill_gap", _no_gap)
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._watched_company_names", _no_watched
        )

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "Security Engineer",
                    "company": "Acme Corp",
                    "url": "https://acme.example/apply",
                    "tags": ["security"],
                }
            ],
        }
        message = await build_daily_report_message(
            report, None, weekly=True, user_id="u1"
        )
        assert "📊 Your week in applications" in message
        assert "1 applied" in message
        assert "1 interviews" in message

    @pytest.mark.asyncio
    async def test_daily_message_has_no_week_block(self, monkeypatch):
        from interntrack.scheduler.jobs import build_daily_report_message

        async def _no_salary(session, domains, user_location):
            return None

        async def _no_gap(session, sections, user_id=None, limit=5):
            return []

        async def _no_watched(session, user_id=None):
            return []

        monkeypatch.setattr(
            "interntrack.scheduler.jobs._weekly_salary_insight", _no_salary
        )
        monkeypatch.setattr("interntrack.scheduler.jobs._weekly_skill_gap", _no_gap)
        monkeypatch.setattr(
            "interntrack.scheduler.jobs._watched_company_names", _no_watched
        )

        report = {
            "summary": {"new_jobs": 1, "new_applications": 0, "total_applications": 0},
            "new_jobs": [
                {
                    "id": "job-1",
                    "title": "Security Engineer",
                    "company": "Acme Corp",
                    "url": "https://acme.example/apply",
                    "tags": ["security"],
                }
            ],
        }
        message = await build_daily_report_message(report, None, user_id="u1")
        assert "Your week in applications" not in message


class TestMatchTrendHelpers:
    """Pure helpers behind GET /reports/match-trend."""

    def test_points_from_rows(self):
        from interntrack.api.v1.reports import _match_trend_points

        class _Row:
            def __init__(self, d, avg, jobs):
                self.snapshot_date = d
                self.avg_match = avg
                self.min_match = 10.0
                self.max_match = 90.0
                self.jobs_scored = jobs

        points = _match_trend_points([_Row(date(2026, 8, 1), 42.0, 5)])
        assert points == [
            {
                "date": "2026-08-01",
                "avg_match": 42.0,
                "min_match": 10.0,
                "max_match": 90.0,
                "jobs_scored": 5,
            }
        ]

    def test_delta_none_with_less_than_two_points(self):
        from interntrack.api.v1.reports import _match_trend_delta

        assert _match_trend_delta([]) is None
        assert _match_trend_delta([{"avg_match": 40.0}]) is None

    def test_delta_rounded_over_range(self):
        from interntrack.api.v1.reports import _match_trend_delta

        points = [
            {"avg_match": 41.25},
            {"avg_match": 46.0},
            {"avg_match": 51.75},
        ]
        assert _match_trend_delta(points) == 10.5

    def test_delta_none_when_missing_values(self):
        from interntrack.api.v1.reports import _match_trend_delta

        assert _match_trend_delta([{"avg_match": None}, {"avg_match": 50.0}]) is None
