"""Unit tests for API v1 endpoint functions directly (mocked services)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import make_app_mock as _make_app_mock
from tests.conftest import make_job_mock as _make_job_mock


class TestJobsAPIUnit:
    """Unit tests for jobs API endpoint functions."""

    @pytest.mark.asyncio
    async def test_list_jobs(self):
        from interntrack.api.v1.jobs import list_jobs

        mock_service = MagicMock()
        mock_service.get_jobs = AsyncMock(return_value=[])
        mock_service.job_repo.count = AsyncMock(return_value=0)

        with patch("interntrack.api.v1.jobs.JobService", return_value=mock_service):
            result = await list_jobs(skip=0, limit=10, db=AsyncMock())

        assert result.total == 0
        assert result.jobs == []

    @pytest.mark.asyncio
    async def test_list_jobs_with_filters(self):
        from interntrack.api.v1.jobs import list_jobs

        mock_service = MagicMock()
        mock_service.get_jobs = AsyncMock(return_value=[_make_job_mock(id="j1")])
        mock_service.job_repo.count = AsyncMock(return_value=1)

        with patch("interntrack.api.v1.jobs.JobService", return_value=mock_service):
            result = await list_jobs(
                skip=0,
                limit=10,
                job_type="full_time",
                is_remote=True,
                company="Tech",
                db=AsyncMock(),
            )

        assert result.total == 1
        mock_service.get_jobs.assert_called_once_with(
            skip=0,
            limit=10,
            job_type="full_time",
            is_remote=True,
            company="Tech",
        )

    @pytest.mark.asyncio
    async def test_get_job_found(self):
        from interntrack.api.v1.jobs import get_job

        mock_service = MagicMock()
        mock_service.get_job = AsyncMock(return_value=_make_job_mock())

        with patch("interntrack.api.v1.jobs.JobService", return_value=mock_service):
            result = await get_job("job-1", db=AsyncMock())

        assert result["id"] == "job-1"

    @pytest.mark.asyncio
    async def test_get_job_not_found(self):
        from interntrack.api.v1.jobs import get_job

        mock_service = MagicMock()
        mock_service.get_job = AsyncMock(return_value=None)

        with (
            patch("interntrack.api.v1.jobs.JobService", return_value=mock_service),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_job("nonexistent", db=AsyncMock())

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_job_success(self):
        from interntrack.api.schemas.job import JobCreate
        from interntrack.api.v1.jobs import create_job

        mock_service = MagicMock()
        mock_service.create_job = AsyncMock(return_value=_make_job_mock(id="new-job"))

        job_data = JobCreate(title="Dev", company="Co", url="https://example.com")

        with patch("interntrack.api.v1.jobs.JobService", return_value=mock_service):
            result = await create_job(job_data, db=AsyncMock())

        assert result["id"] == "new-job"

    @pytest.mark.asyncio
    async def test_create_job_duplicate(self):
        from interntrack.api.schemas.job import JobCreate
        from interntrack.api.v1.jobs import create_job
        from interntrack.domain.exceptions import DuplicateJobError

        mock_service = MagicMock()
        mock_service.create_job = AsyncMock(side_effect=DuplicateJobError("Dev", "Co"))

        job_data = JobCreate(title="Dev", company="Co", url="https://example.com")

        with (
            patch("interntrack.api.v1.jobs.JobService", return_value=mock_service),
            pytest.raises(HTTPException) as exc_info,
        ):
            await create_job(job_data, db=AsyncMock())

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_update_job_found(self):
        from interntrack.api.schemas.job import JobUpdate
        from interntrack.api.v1.jobs import update_job

        mock_service = MagicMock()
        mock_service.job_repo.update = AsyncMock(
            return_value=_make_job_mock(title="Updated"),
        )

        with patch("interntrack.api.v1.jobs.JobService", return_value=mock_service):
            result = await update_job(
                "job-1",
                JobUpdate(title="Updated"),
                db=AsyncMock(),
            )

        assert result["title"] == "Updated"

    @pytest.mark.asyncio
    async def test_update_job_not_found(self):
        from interntrack.api.schemas.job import JobUpdate
        from interntrack.api.v1.jobs import update_job

        mock_service = MagicMock()
        mock_service.job_repo.update = AsyncMock(return_value=None)

        with (
            patch("interntrack.api.v1.jobs.JobService", return_value=mock_service),
            pytest.raises(HTTPException) as exc_info,
        ):
            await update_job("nonexistent", JobUpdate(title="X"), db=AsyncMock())

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_job_found(self):
        from interntrack.api.v1.jobs import delete_job

        mock_service = MagicMock()
        mock_service.job_repo.delete = AsyncMock(return_value=True)

        with patch("interntrack.api.v1.jobs.JobService", return_value=mock_service):
            result = await delete_job("job-1", db=AsyncMock())

        assert result is None  # 204 No Content

    @pytest.mark.asyncio
    async def test_delete_job_not_found(self):
        from interntrack.api.v1.jobs import delete_job

        mock_service = MagicMock()
        mock_service.job_repo.delete = AsyncMock(return_value=False)

        with (
            patch("interntrack.api.v1.jobs.JobService", return_value=mock_service),
            pytest.raises(HTTPException) as exc_info,
        ):
            await delete_job("nonexistent", db=AsyncMock())

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_search_jobs(self):
        from interntrack.api.schemas.job import JobSearchRequest
        from interntrack.api.v1.jobs import search_jobs

        mock_service = MagicMock()
        mock_service.search_jobs = AsyncMock(return_value=[])

        with patch("interntrack.api.v1.jobs.JobService", return_value=mock_service):
            result = await search_jobs(
                JobSearchRequest(query="python", limit=5),
                db=AsyncMock(),
            )

        assert result.total == 0

    @pytest.mark.asyncio
    async def test_get_job_statistics(self):
        from interntrack.api.v1.jobs import get_job_statistics

        mock_service = MagicMock()
        mock_service.get_job_statistics = AsyncMock(
            return_value={
                "total_jobs": 10,
                "salary_stats": {"avg_min": 80000},
                "top_companies": [],
                "job_types": [],
            },
        )

        with patch("interntrack.api.v1.jobs.JobService", return_value=mock_service):
            result = await get_job_statistics(db=AsyncMock())

        assert result["total_jobs"] == 10

    @pytest.mark.asyncio
    async def test_get_closing_soon(self):
        from interntrack.api.v1.jobs import get_closing_soon

        mock_service = MagicMock()
        mock_service.get_closing_soon = AsyncMock(return_value=[])

        with patch("interntrack.api.v1.jobs.JobService", return_value=mock_service):
            result = await get_closing_soon(days=3, db=AsyncMock())

        assert result == []

    @pytest.mark.asyncio
    async def test_run_discovery(self):
        from interntrack.api.v1.jobs import run_discovery

        mock_registry = MagicMock()
        mock_registry.fetch_all = AsyncMock(return_value=[{"title": "Job 1"}])

        mock_service = MagicMock()
        mock_service.save_jobs = AsyncMock(return_value=[{"title": "Job 1"}])

        with (
            patch("interntrack.api.v1.jobs.JobService", return_value=mock_service),
            patch(
                "interntrack.scrapers.registry.get_default_registry",
                return_value=mock_registry,
            ),
        ):
            result = await run_discovery(
                source="hackernews",
                query="python",
                db=AsyncMock(),
            )

        assert result["discovered"] == 1
        assert result["saved"] == 1

    @pytest.mark.asyncio
    async def test_run_discovery_body_query_wins(self):
        """Dashboard sends the query in the JSON body; it must win over the default."""
        from interntrack.api.v1.jobs import run_discovery

        mock_registry = MagicMock()
        mock_registry.fetch_all = AsyncMock(return_value=[{"title": "Intern Job"}])

        mock_service = MagicMock()
        mock_service.save_jobs = AsyncMock(return_value=[{"title": "Intern Job"}])

        with (
            patch("interntrack.api.v1.jobs.JobService", return_value=mock_service),
            patch(
                "interntrack.scrapers.registry.get_default_registry",
                return_value=mock_registry,
            ),
        ):
            result = await run_discovery(
                body={"query": "data science internship"},
                db=AsyncMock(),
            )

        assert result["discovered"] == 1
        mock_registry.fetch_all.assert_awaited_once_with(
            query="data science internship",
            sources=None,
        )

    @pytest.mark.asyncio
    async def test_run_discovery_query_param_still_works(self):
        """Query-param form (curl/API docs) must keep working."""
        from interntrack.api.v1.jobs import run_discovery

        mock_registry = MagicMock()
        mock_registry.fetch_all = AsyncMock(return_value=[])

        mock_service = MagicMock()
        mock_service.save_jobs = AsyncMock(return_value=[])

        with (
            patch("interntrack.api.v1.jobs.JobService", return_value=mock_service),
            patch(
                "interntrack.scrapers.registry.get_default_registry",
                return_value=mock_registry,
            ),
        ):
            result = await run_discovery(
                query="python developer",
                body=None,
                db=AsyncMock(),
            )

        assert result["discovered"] == 0
        mock_registry.fetch_all.assert_awaited_once_with(
            query="python developer",
            sources=None,
        )


class TestApplicationsAPIUnit:
    """Unit tests for applications API endpoint functions."""

    @pytest.mark.asyncio
    async def test_list_applications(self):
        from interntrack.api.v1.applications import list_applications

        mock_service = MagicMock()
        mock_service.app_repo.get_all = AsyncMock(return_value=[])

        with patch(
            "interntrack.api.v1.applications.ApplicationService",
            return_value=mock_service,
        ):
            result = await list_applications(skip=0, limit=10, db=AsyncMock())

        assert result.total == 0

    @pytest.mark.asyncio
    async def test_list_applications_with_status(self):
        from interntrack.api.v1.applications import list_applications

        mock_service = MagicMock()
        mock_service.get_applications_by_status = AsyncMock(
            return_value=[_make_app_mock()],
        )

        with patch(
            "interntrack.api.v1.applications.ApplicationService",
            return_value=mock_service,
        ):
            result = await list_applications(
                status="saved",
                skip=0,
                limit=10,
                db=AsyncMock(),
            )

        assert result.total == 1

    @pytest.mark.asyncio
    async def test_get_application_found(self):
        from interntrack.api.v1.applications import get_application

        mock_service = MagicMock()
        mock_service.get_application = AsyncMock(return_value=_make_app_mock())

        with patch(
            "interntrack.api.v1.applications.ApplicationService",
            return_value=mock_service,
        ):
            result = await get_application("app-1", db=AsyncMock())

        assert result["id"] == "app-1"

    @pytest.mark.asyncio
    async def test_get_application_not_found(self):
        from interntrack.api.v1.applications import get_application

        mock_service = MagicMock()
        mock_service.get_application = AsyncMock(return_value=None)

        with (
            patch(
                "interntrack.api.v1.applications.ApplicationService",
                return_value=mock_service,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_application("nonexistent", db=AsyncMock())

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_application(self):
        from interntrack.api.schemas.application import ApplicationCreate
        from interntrack.api.v1.applications import create_application

        mock_service = MagicMock()
        mock_service.get_application_for_job = AsyncMock(return_value=None)
        mock_service.create_application = AsyncMock(
            return_value=_make_app_mock(id="new-app"),
        )

        with patch(
            "interntrack.api.v1.applications.ApplicationService",
            return_value=mock_service,
        ):
            result = await create_application(
                ApplicationCreate(job_id="job-1"),
                db=AsyncMock(),
            )

        assert result["id"] == "new-app"
        mock_service.get_application_for_job.assert_awaited_once_with(
            "job-1",
            user_id=None,
        )

    @pytest.mark.asyncio
    async def test_update_application_found(self):
        from interntrack.api.schemas.application import ApplicationUpdate
        from interntrack.api.v1.applications import update_application

        mock_service = MagicMock()
        mock_service.app_repo.update = AsyncMock(return_value=_make_app_mock())

        with patch(
            "interntrack.api.v1.applications.ApplicationService",
            return_value=mock_service,
        ):
            result = await update_application(
                "app-1",
                ApplicationUpdate(),
                db=AsyncMock(),
            )

        assert result["id"] == "app-1"

    @pytest.mark.asyncio
    async def test_update_application_not_found(self):
        from interntrack.api.schemas.application import ApplicationUpdate
        from interntrack.api.v1.applications import update_application

        mock_service = MagicMock()
        mock_service.app_repo.update = AsyncMock(return_value=None)

        with (
            patch(
                "interntrack.api.v1.applications.ApplicationService",
                return_value=mock_service,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await update_application(
                "nonexistent",
                ApplicationUpdate(),
                db=AsyncMock(),
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_application_found(self):
        from interntrack.api.v1.applications import delete_application

        mock_service = MagicMock()
        mock_service.app_repo.delete = AsyncMock(return_value=True)

        with patch(
            "interntrack.api.v1.applications.ApplicationService",
            return_value=mock_service,
        ):
            result = await delete_application("app-1", db=AsyncMock())

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_application_not_found(self):
        from interntrack.api.v1.applications import delete_application

        mock_service = MagicMock()
        mock_service.app_repo.delete = AsyncMock(return_value=False)

        with (
            patch(
                "interntrack.api.v1.applications.ApplicationService",
                return_value=mock_service,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await delete_application("nonexistent", db=AsyncMock())

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_status_found(self):
        from interntrack.api.schemas.application import ApplicationStatusUpdate
        from interntrack.api.v1.applications import update_status

        mock_service = MagicMock()
        mock_service.update_status = AsyncMock(
            return_value=_make_app_mock(status="applied"),
        )

        with patch(
            "interntrack.api.v1.applications.ApplicationService",
            return_value=mock_service,
        ):
            result = await update_status(
                "app-1",
                ApplicationStatusUpdate(status="applied"),
                db=AsyncMock(),
            )

        assert result["status"] == "applied"

    @pytest.mark.asyncio
    async def test_update_status_not_found(self):
        from interntrack.api.schemas.application import ApplicationStatusUpdate
        from interntrack.api.v1.applications import update_status

        mock_service = MagicMock()
        mock_service.update_status = AsyncMock(return_value=None)

        with (
            patch(
                "interntrack.api.v1.applications.ApplicationService",
                return_value=mock_service,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await update_status(
                "nonexistent",
                ApplicationStatusUpdate(status="applied"),
                db=AsyncMock(),
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_metrics(self):
        from interntrack.api.v1.applications import get_metrics

        mock_service = MagicMock()
        mock_service.get_metrics = AsyncMock(
            return_value={
                "total_applications": 5,
                "status_counts": {},
                "rejection_rate": 0.1,
                "response_rate": 0.5,
                "recent_applications": 2,
            },
        )

        with patch(
            "interntrack.api.v1.applications.ApplicationService",
            return_value=mock_service,
        ):
            result = await get_metrics(db=AsyncMock())

        assert result["total_applications"] == 5

    @pytest.mark.asyncio
    async def test_get_timeline(self):
        from interntrack.api.v1.applications import get_timeline

        mock_service = MagicMock()
        mock_service.get_application_timeline = AsyncMock(return_value=[])

        with patch(
            "interntrack.api.v1.applications.ApplicationService",
            return_value=mock_service,
        ):
            result = await get_timeline(days=30, db=AsyncMock())

        assert result == []


class TestReportsAPIUnit:
    """Unit tests for reports API endpoint functions."""

    @pytest.mark.asyncio
    async def test_daily_report(self):
        from interntrack.api.v1.reports import get_daily_report

        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "report_type": "daily",
                "generated_at": "2026-01-01",
                "summary": {"new_jobs": 5},
            },
        )

        with patch(
            "interntrack.api.v1.reports.ReportService",
            return_value=mock_service,
        ):
            result = await get_daily_report(db=AsyncMock())

        assert result["report_type"] == "daily"

    @pytest.mark.asyncio
    async def test_weekly_report(self):
        from interntrack.api.v1.reports import get_weekly_report

        mock_service = MagicMock()
        mock_service.generate_weekly_report = AsyncMock(
            return_value={
                "report_type": "weekly",
                "generated_at": "2026-01-01",
                "summary": {},
            },
        )

        with patch(
            "interntrack.api.v1.reports.ReportService",
            return_value=mock_service,
        ):
            result = await get_weekly_report(db=AsyncMock())

        assert result["report_type"] == "weekly"

    @pytest.mark.asyncio
    async def test_daily_report_uses_slot_domains(self):
        """?slot=morning filters the digest to that slot's saved categories."""
        from interntrack.api.v1.reports import get_daily_report

        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "report_type": "daily",
                "generated_at": "2026-01-01",
                "summary": {"new_jobs": 2},
                "new_jobs": [{}, {}],
            },
        )
        mock_manager = MagicMock()
        mock_manager.get_configured_channels.return_value = []

        with (
            patch(
                "interntrack.api.v1.reports.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.scheduler.jobs._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "domains": ["coding"],
                        "channels": [],
                        "min_match_score": None,
                        "is_enabled": True,
                        "slot_domains": {"morning": ["security"]},
                        "weekly_enabled": True,
                        "last_alert_at": None,
                    }
                ),
            ),
            patch(
                "interntrack.scheduler.jobs._mark_alert_sent",
                new=AsyncMock(),
            ),
            patch(
                "interntrack.services.notification_service.NotificationManager",
                return_value=mock_manager,
            ),
        ):
            result = await get_daily_report(db=AsyncMock(), slot="morning")

        # Slot domains override the general preference for this send.
        mock_service.generate_daily_report.assert_called_once_with(
            domains=["security"],
            min_match_score=None,
            since=None,
        )
        assert result["report_type"] == "daily"

    @pytest.mark.asyncio
    async def test_daily_report_unconfigured_slot_uses_default(self):
        """A slot with no saved categories falls back to its default bucket."""
        from interntrack.api.v1.reports import get_daily_report

        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "report_type": "daily",
                "generated_at": "2026-01-01",
                "summary": {"new_jobs": 1},
                "new_jobs": [{}],
            },
        )
        mock_manager = MagicMock()
        mock_manager.get_configured_channels.return_value = []

        with (
            patch(
                "interntrack.api.v1.reports.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.scheduler.jobs._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "domains": ["coding"],
                        "channels": [],
                        "min_match_score": None,
                        "is_enabled": True,
                        "slot_domains": {},
                        "weekly_enabled": True,
                        "last_alert_at": None,
                    }
                ),
            ),
            patch(
                "interntrack.scheduler.jobs._mark_alert_sent",
                new=AsyncMock(),
            ),
            patch(
                "interntrack.services.notification_service.NotificationManager",
                return_value=mock_manager,
            ),
        ):
            result = await get_daily_report(db=AsyncMock(), slot="morning")

        # No slot_domains saved -> DEFAULT_SLOT_DOMAINS["morning"] = security.
        mock_service.generate_daily_report.assert_called_once_with(
            domains=["security"],
            min_match_score=None,
            since=None,
        )
        assert result["report_type"] == "daily"

    @pytest.mark.asyncio
    async def test_daily_report_unknown_slot_falls_back(self):
        """An unknown slot keeps the general preference filter."""
        from interntrack.api.v1.reports import get_daily_report

        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "report_type": "daily",
                "generated_at": "2026-01-01",
                "summary": {"new_jobs": 1},
                "new_jobs": [{}],
            },
        )
        mock_manager = MagicMock()
        mock_manager.get_configured_channels.return_value = []

        with (
            patch(
                "interntrack.api.v1.reports.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.scheduler.jobs._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "domains": ["coding"],
                        "channels": [],
                        "min_match_score": None,
                        "is_enabled": True,
                        "slot_domains": {"morning": ["security"]},
                        "weekly_enabled": True,
                        "last_alert_at": None,
                    }
                ),
            ),
            patch(
                "interntrack.scheduler.jobs._mark_alert_sent",
                new=AsyncMock(),
            ),
            patch(
                "interntrack.services.notification_service.NotificationManager",
                return_value=mock_manager,
            ),
        ):
            result = await get_daily_report(db=AsyncMock(), slot="midnight")

        mock_service.generate_daily_report.assert_called_once_with(
            domains=["coding"],
            min_match_score=None,
            since=None,
        )
        assert result["report_type"] == "daily"

    @pytest.mark.asyncio
    async def test_weekly_alert_sends_digest(self):
        """Sunday weekly-alert endpoint recaps the week and records history."""
        from interntrack.api.v1.reports import get_weekly_alert

        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "report_type": "daily",
                "generated_at": "2026-01-01",
                "summary": {"new_jobs": 3},
                "new_jobs": [{}, {}, {}],
            },
        )
        mock_manager = MagicMock()
        mock_manager.get_configured_channels.return_value = ["email"]
        mock_manager.notify = AsyncMock(return_value={"email": True})
        recorder = AsyncMock()

        with (
            patch(
                "interntrack.api.v1.reports.ReportService",
                return_value=mock_service,
            ),
            patch(
                "interntrack.scheduler.jobs._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "domains": ["security"],
                        "channels": ["email"],
                        "min_match_score": None,
                        "is_enabled": True,
                        "slot_domains": {},
                        "weekly_enabled": True,
                    }
                ),
            ),
            patch(
                "interntrack.services.notification_service.NotificationManager",
                return_value=mock_manager,
            ),
            patch(
                "interntrack.scheduler.jobs._record_alert_history",
                new=recorder,
            ),
            patch(
                "interntrack.scheduler.jobs.build_daily_report_html",
                new=AsyncMock(return_value="weekly text"),
            ),
        ):
            result = await get_weekly_alert(db=AsyncMock())

        assert result["report_type"] == "weekly"
        assert result["summary"]["new_jobs"] == 3
        mock_manager.notify.assert_awaited_once_with(
            ["email"], "weekly text", subject="Weekly Digest (security)"
        )
        recorder.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_weekly_alert_disabled_skips_send(self):
        """weekly_enabled=False short-circuits the Sunday recap."""
        from interntrack.api.v1.reports import get_weekly_alert

        with (
            patch(
                "interntrack.scheduler.jobs._load_alert_preferences",
                new=AsyncMock(
                    return_value={
                        "domains": [],
                        "channels": [],
                        "is_enabled": True,
                        "weekly_enabled": False,
                    }
                ),
            ),
            patch(
                "interntrack.api.v1.reports.ReportService",
                return_value=MagicMock(),
            ),
        ):
            result = await get_weekly_alert(db=AsyncMock())

        assert result["summary"]["skipped"] == "weekly digest disabled"

    @pytest.mark.asyncio
    async def test_monthly_report(self):
        from interntrack.api.v1.reports import get_monthly_report

        mock_service = MagicMock()
        mock_service.generate_monthly_report = AsyncMock(
            return_value={
                "report_type": "monthly",
                "generated_at": "2026-01-01",
                "summary": {},
            },
        )

        with patch(
            "interntrack.api.v1.reports.ReportService",
            return_value=mock_service,
        ):
            result = await get_monthly_report(db=AsyncMock())

        assert result["report_type"] == "monthly"

    @pytest.mark.asyncio
    async def test_report_html_daily(self):
        from interntrack.api.v1.reports import get_report_html

        mock_service = MagicMock()
        mock_service.generate_daily_report = AsyncMock(
            return_value={
                "report_type": "daily",
                "generated_at": "2026-01-01",
                "summary": {},
            },
        )
        mock_service.render_report = AsyncMock(return_value="<html>daily</html>")

        with patch(
            "interntrack.api.v1.reports.ReportService",
            return_value=mock_service,
        ):
            result = await get_report_html("daily", db=AsyncMock())

        assert "daily" in result.body.decode()

    @pytest.mark.asyncio
    async def test_report_html_weekly(self):
        from interntrack.api.v1.reports import get_report_html

        mock_service = MagicMock()
        mock_service.generate_weekly_report = AsyncMock(
            return_value={
                "report_type": "weekly",
                "generated_at": "2026-01-01",
                "summary": {},
            },
        )
        mock_service.render_report = AsyncMock(return_value="<html>weekly</html>")

        with patch(
            "interntrack.api.v1.reports.ReportService",
            return_value=mock_service,
        ):
            result = await get_report_html("weekly", db=AsyncMock())

        assert "weekly" in result.body.decode()

    @pytest.mark.asyncio
    async def test_report_html_monthly(self):
        from interntrack.api.v1.reports import get_report_html

        mock_service = MagicMock()
        mock_service.generate_monthly_report = AsyncMock(
            return_value={
                "report_type": "monthly",
                "generated_at": "2026-01-01",
                "summary": {},
            },
        )
        mock_service.render_report = AsyncMock(return_value="<html>monthly</html>")

        with patch(
            "interntrack.api.v1.reports.ReportService",
            return_value=mock_service,
        ):
            result = await get_report_html("monthly", db=AsyncMock())

        assert "monthly" in result.body.decode()

    @pytest.mark.asyncio
    async def test_report_html_invalid_type(self):
        from interntrack.api.v1.reports import get_report_html

        result = await get_report_html("invalid", db=AsyncMock())

        assert result.status_code == 400


class TestNotificationsAPIUnit:
    """Unit tests for notifications API endpoint functions."""

    @pytest.mark.asyncio
    async def test_get_channels(self):
        from interntrack.api.v1.notifications import get_channels

        with patch("interntrack.config.get_settings") as mock_settings:
            mock_settings.return_value.is_telegram_configured = True
            mock_settings.return_value.is_email_configured = False
            mock_settings.return_value.is_discord_configured = True
            mock_settings.return_value.is_slack_configured = False

            result = await get_channels()

        assert "telegram" in result.channels
        assert "discord" in result.channels
        assert "email" not in result.channels

    @pytest.mark.asyncio
    async def test_get_channels_none_configured(self):
        from interntrack.api.v1.notifications import get_channels

        with patch("interntrack.config.get_settings") as mock_settings:
            mock_settings.return_value.is_telegram_configured = False
            mock_settings.return_value.is_email_configured = False
            mock_settings.return_value.is_discord_configured = False
            mock_settings.return_value.is_slack_configured = False

            result = await get_channels()

        assert result.channels == []

    @pytest.mark.asyncio
    async def test_test_notification(self):
        from interntrack.api.schemas.notification import NotificationTestRequest
        from interntrack.api.v1.notifications import send_test_notification

        mock_manager = MagicMock()
        mock_manager.notify = AsyncMock(return_value={"email": True})
        mock_manager.get_configured_channels.return_value = ["email"]

        with patch(
            "interntrack.api.v1.notifications.NotificationManager",
            return_value=mock_manager,
        ):
            result = await send_test_notification(
                NotificationTestRequest(channels=["email"], message="Test"),
                db=AsyncMock(),
            )

        assert "email" in result.results

    @pytest.mark.asyncio
    async def test_send_notification(self):
        from interntrack.api.v1.notifications import send_notification

        mock_manager = MagicMock()
        mock_manager.notify = AsyncMock(return_value={"telegram": True})

        with patch(
            "interntrack.api.v1.notifications.NotificationManager",
            return_value=mock_manager,
        ):
            result = await send_notification(
                channels=["telegram"],
                message="Hello",
                subject="Test",
                db=AsyncMock(),
            )

        assert result["results"]["telegram"] is True


class TestDashboardAPIUnit:
    """Unit tests for dashboard API endpoint functions."""

    @pytest.mark.asyncio
    async def test_dashboard_overview(self):
        from interntrack.api.v1.dashboard import get_dashboard_overview

        mock_job_service = MagicMock()
        mock_job_service.get_job_statistics = AsyncMock(return_value={"total_jobs": 10})

        mock_app_service = MagicMock()
        mock_app_service.get_metrics = AsyncMock(return_value={"total_applications": 5})

        with (
            patch(
                "interntrack.api.v1.dashboard.JobService",
                return_value=mock_job_service,
            ),
            patch(
                "interntrack.api.v1.dashboard.ApplicationService",
                return_value=mock_app_service,
            ),
        ):
            result = await get_dashboard_overview(db=AsyncMock())

        assert "jobs" in result
        assert "applications" in result

    @pytest.mark.asyncio
    async def test_job_type_chart(self):
        from interntrack.api.v1.dashboard import get_job_type_chart

        mock_service = MagicMock()
        mock_service.get_job_statistics = AsyncMock(
            return_value={
                "job_types": [("full_time", 5), ("remote", 3)],
            },
        )

        with patch(
            "interntrack.api.v1.dashboard.JobService",
            return_value=mock_service,
        ):
            result = await get_job_type_chart(db=AsyncMock())

        assert "data" in result

    @pytest.mark.asyncio
    async def test_application_timeline_chart(self):
        from interntrack.api.v1.dashboard import get_application_timeline_chart

        mock_service = MagicMock()
        mock_service.get_application_timeline = AsyncMock(return_value=[])

        with patch(
            "interntrack.api.v1.dashboard.ApplicationService",
            return_value=mock_service,
        ):
            result = await get_application_timeline_chart(db=AsyncMock())

        assert "data" in result

    @pytest.mark.asyncio
    async def test_top_companies_chart(self):
        from interntrack.api.v1.dashboard import get_top_companies_chart

        mock_service = MagicMock()
        mock_service.get_job_statistics = AsyncMock(
            return_value={
                "top_companies": [("TechCorp", 10)],
            },
        )

        with patch(
            "interntrack.api.v1.dashboard.JobService",
            return_value=mock_service,
        ):
            result = await get_top_companies_chart(db=AsyncMock())

        assert "data" in result

    @pytest.mark.asyncio
    async def test_salary_chart(self):
        from interntrack.api.v1.dashboard import get_salary_chart

        mock_service = MagicMock()
        mock_service.get_job_statistics = AsyncMock(
            return_value={
                "salary_stats": {"avg_min": 80000},
            },
        )

        with patch(
            "interntrack.api.v1.dashboard.JobService",
            return_value=mock_service,
        ):
            result = await get_salary_chart(db=AsyncMock())

        assert "data" in result

    @pytest.mark.asyncio
    async def test_recent_activity(self):
        from interntrack.api.v1.dashboard import get_recent_activity

        mock_job_service = MagicMock()
        mock_job_service.job_repo.get_recent_jobs = AsyncMock(return_value=[])

        mock_app_service = MagicMock()
        mock_app_service.app_repo.get_recent_applications = AsyncMock(return_value=[])

        with (
            patch(
                "interntrack.api.v1.dashboard.JobService",
                return_value=mock_job_service,
            ),
            patch(
                "interntrack.api.v1.dashboard.ApplicationService",
                return_value=mock_app_service,
            ),
        ):
            result = await get_recent_activity(db=AsyncMock())

        assert "recent_jobs" in result
        assert "recent_applications" in result


class TestSkillsAPIUnit:
    """Unit tests for skills API endpoint functions."""

    @pytest.mark.asyncio
    async def test_list_skills_all(self):
        from interntrack.api.v1.skills import list_skills

        mock_repo = MagicMock()
        mock_repo.get_active_skills = AsyncMock(
            return_value=[
                MagicMock(
                    id="1",
                    name="python",
                    category=MagicMock(value="programming"),
                    difficulty_level=2,
                ),
            ],
        )

        with patch("interntrack.api.v1.skills.SkillRepository", return_value=mock_repo):
            result = await list_skills(db=AsyncMock())

        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_list_skills_by_search(self):
        from interntrack.api.v1.skills import list_skills

        mock_repo = MagicMock()
        mock_repo.search_skills = AsyncMock(
            return_value=[
                MagicMock(
                    id="1",
                    name="python",
                    category=MagicMock(value="programming"),
                    difficulty_level=2,
                ),
            ],
        )

        with patch("interntrack.api.v1.skills.SkillRepository", return_value=mock_repo):
            result = await list_skills(search="python", db=AsyncMock())

        assert result["total"] == 1
        mock_repo.search_skills.assert_called_once_with("python")

    @pytest.mark.asyncio
    async def test_list_skills_by_category(self):
        from interntrack.api.v1.skills import list_skills

        mock_repo = MagicMock()
        mock_repo.get_by_category = AsyncMock(
            return_value=[
                MagicMock(
                    id="1",
                    name="python",
                    category=MagicMock(value="programming"),
                    difficulty_level=2,
                ),
            ],
        )

        with patch("interntrack.api.v1.skills.SkillRepository", return_value=mock_repo):
            result = await list_skills(category="programming", db=AsyncMock())

        assert result["total"] == 1
