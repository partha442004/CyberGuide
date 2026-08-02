"""
Unit tests for the CyberGuide scheduler entry point
(``src/cybershield/scheduler/__main__.py``).

Covers ``create_scheduler()`` job registration and the graceful shutdown
paths of ``main()`` (KeyboardInterrupt / SystemExit), with the database,
scrapers, and engines mocked so the tests are hermetic.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cybershield.scheduler import __main__ as scheduler_main


class TestCreateScheduler:
    """The scheduler must register the six expected background jobs."""

    def test_registers_six_jobs(self):
        scheduler = scheduler_main.create_scheduler()
        # The scheduler is never started here; get_jobs() works on pending jobs.
        # (Calling shutdown() on a non-running AsyncIOScheduler raises
        # SchedulerNotRunningError, so there is no teardown needed.)
        jobs = scheduler.get_jobs()
        assert len(jobs) == 6

    def test_job_ids(self):
        scheduler = scheduler_main.create_scheduler()
        ids = {job.id for job in scheduler.get_jobs()}
        assert ids == {
            "job_discovery",
            "link_verification",
            "scam_analysis",
            "daily_report",
            "weekly_report",
            "monthly_report",
        }

    def test_job_trigger_types(self):
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = scheduler_main.create_scheduler()
        jobs = {job.id: job for job in scheduler.get_jobs()}
        # Interval-based jobs use IntervalTrigger.
        assert isinstance(jobs["job_discovery"].trigger, IntervalTrigger)
        assert isinstance(jobs["link_verification"].trigger, IntervalTrigger)
        assert isinstance(jobs["scam_analysis"].trigger, IntervalTrigger)
        # Report jobs use CronTrigger.
        assert isinstance(jobs["daily_report"].trigger, CronTrigger)
        assert isinstance(jobs["weekly_report"].trigger, CronTrigger)
        assert isinstance(jobs["monthly_report"].trigger, CronTrigger)


class TestMain:
    """main() must start the scheduler and stop gracefully on interrupt."""

    @pytest.mark.asyncio
    @patch("cybershield.scheduler.__main__.init_db", new_callable=AsyncMock)
    async def test_starts_scheduler_and_shuts_down_on_keyboard_interrupt(self, mock_init_db):
        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []

        with (
            patch(
                "cybershield.scheduler.__main__.create_scheduler",
                return_value=mock_scheduler,
            ),
            patch("cybershield.scheduler.__main__.signal.signal"),
            patch(
                "cybershield.scheduler.__main__.asyncio.sleep",
                side_effect=KeyboardInterrupt(),
            ),
        ):
            await scheduler_main.main()

        mock_init_db.assert_awaited_once()
        mock_scheduler.start.assert_called_once()
        mock_scheduler.shutdown.assert_called()

    @pytest.mark.asyncio
    @patch("cybershield.scheduler.__main__.init_db", new_callable=AsyncMock)
    async def test_shuts_down_on_system_exit(self, mock_init_db):
        # main() catches SystemExit itself and shuts the scheduler down, so it
        # must not propagate to the caller.
        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []

        with (
            patch(
                "cybershield.scheduler.__main__.create_scheduler",
                return_value=mock_scheduler,
            ),
            patch("cybershield.scheduler.__main__.signal.signal"),
            patch(
                "cybershield.scheduler.__main__.asyncio.sleep",
                side_effect=SystemExit(),
            ),
        ):
            await scheduler_main.main()

        mock_scheduler.shutdown.assert_called()


class TestJobFunctions:
    """The async job coroutines must tolerate failures (they log, not raise)."""

    @pytest.mark.asyncio
    async def test_job_discovery_logs_error_on_scraper_failure(self):
        # job_discovery does a lazy local import of ScraperRegistry, so the
        # patch must target the scrapers.registry module attribute itself.
        with patch(
            "cybershield.scrapers.registry.ScraperRegistry",
        ) as mock_registry:
            mock_registry.run_all = AsyncMock(side_effect=RuntimeError("boom"))
            # Should not raise: the coroutine catches and logs.
            await scheduler_main.job_discovery()

    @pytest.mark.asyncio
    async def test_link_verification_logs_error_on_db_failure(self):
        with patch(
            "cybershield.scheduler.__main__.get_db_session",
        ) as mock_session_ctx:
            mock_session_ctx.side_effect = RuntimeError("db down")
            # Should not raise: caught by the coroutine's try/except.
            await scheduler_main.link_verification()

    @pytest.mark.asyncio
    async def test_scam_analysis_logs_error_on_db_failure(self):
        with patch(
            "cybershield.scheduler.__main__.get_db_session",
        ) as mock_session_ctx:
            mock_session_ctx.side_effect = RuntimeError("db down")
            await scheduler_main.scam_analysis()

    @pytest.mark.asyncio
    async def test_daily_report_logs_error_on_db_failure(self):
        with patch(
            "cybershield.scheduler.__main__.get_db_session",
        ) as mock_session_ctx:
            mock_session_ctx.side_effect = RuntimeError("db down")
            await scheduler_main.daily_report()

    @pytest.mark.asyncio
    async def test_weekly_report_logs_error_on_db_failure(self):
        with patch(
            "cybershield.scheduler.__main__.get_db_session",
        ) as mock_session_ctx:
            mock_session_ctx.side_effect = RuntimeError("db down")
            await scheduler_main.weekly_report()

    @pytest.mark.asyncio
    async def test_monthly_report_logs_error_on_db_failure(self):
        with patch(
            "cybershield.scheduler.__main__.get_db_session",
        ) as mock_session_ctx:
            mock_session_ctx.side_effect = RuntimeError("db down")
            await scheduler_main.monthly_report()

    @pytest.mark.asyncio
    async def test_main_guard_uses_asyncio_run(self):
        """The __main__ guard calls asyncio.run(main())."""
        import inspect

        source = inspect.getsource(scheduler_main)
        assert "asyncio.run(main())" in source


class TestJobSuccessPaths:
    """The async job coroutines must run end-to-end when everything works."""

    @staticmethod
    def _mock_session(**overrides) -> MagicMock:
        """Build a session mock that satisfies the async DB context manager."""
        session = MagicMock()
        # execute() must resolve to a plain MagicMock so that sync helpers like
        # scalar_one_or_none() / scalars().all() work (an AsyncMock child would
        # return coroutines, which are truthy and break the logic).
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=result)
        session.scalar = AsyncMock(return_value=None)
        session.commit = AsyncMock()
        session.add = MagicMock()
        for key, value in overrides.items():
            setattr(session, key, value)
        return session

    @staticmethod
    def _session_context(session) -> MagicMock:
        """Wrap a session in an async context manager mock."""
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=None)
        return ctx

    @pytest.mark.asyncio
    async def test_job_discovery_stores_new_jobs(self):
        scraped = MagicMock()
        scraped.url = "https://example.com/job/1"
        scraped.title = "Security Engineer"
        scraped.company_name = "Acme"
        scraped.location = "Pune"
        scraped.country = "India"
        scraped.city = "Pune"
        scraped.description = "desc"
        scraped.apply_url = None
        scraped.source = "naukri"
        scraped.source_id = "1"
        scraped.salary_min = None
        scraped.salary_max = None
        scraped.salary_currency = None
        scraped.is_remote = False
        scraped.job_type = "full_time"
        scraped.experience_level = "mid"
        scraped.posting_date = None
        scraped.deadline = None
        scraped.required_skills = []
        scraped.preferred_skills = []
        scraped.raw_data = {}

        session = self._mock_session()
        # First execute (existing check) -> no existing job
        session.execute.return_value.scalar_one_or_none.return_value = None

        with (
            patch(
                "cybershield.scrapers.registry.ScraperRegistry.run_all",
                new_callable=AsyncMock,
                return_value=[scraped],
            ),
            patch(
                "cybershield.scheduler.__main__.get_db_session",
                return_value=self._session_context(session),
            ),
        ):
            await scheduler_main.job_discovery()

        session.commit.assert_awaited_once()
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_job_discovery_skips_existing_jobs(self):
        scraped = MagicMock()
        scraped.url = "https://example.com/job/dup"
        scraped.title = "Security Engineer"
        scraped.company_name = "Acme"
        scraped.location = None
        scraped.country = None
        scraped.city = None
        scraped.description = None
        scraped.apply_url = None
        scraped.source = "naukri"
        scraped.source_id = "1"
        scraped.salary_min = None
        scraped.salary_max = None
        scraped.salary_currency = None
        scraped.is_remote = False
        scraped.job_type = "full_time"
        scraped.experience_level = None
        scraped.posting_date = None
        scraped.deadline = None
        scraped.required_skills = []
        scraped.preferred_skills = []
        scraped.raw_data = {}

        session = self._mock_session()
        session.execute.return_value.scalar_one_or_none.return_value = MagicMock()  # exists

        with (
            patch(
                "cybershield.scrapers.registry.ScraperRegistry.run_all",
                new_callable=AsyncMock,
                return_value=[scraped],
            ),
            patch(
                "cybershield.scheduler.__main__.get_db_session",
                return_value=self._session_context(session),
            ),
        ):
            await scheduler_main.job_discovery()

        session.commit.assert_awaited_once()
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_link_verification_marks_verified(self):
        job = MagicMock()
        job.id = "job-1"
        job.url = "https://example.com/job/1"
        job.apply_url = None
        job.company = "Acme"
        job.expires_at = None
        job.is_verified = False

        session = self._mock_session()
        session.execute.return_value.scalars.return_value.all.return_value = [job]

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {"is_verified": True}

        with (
            patch(
                "cybershield.engines.verification.VerificationEngine",
            ) as mock_engine_cls,
            patch(
                "cybershield.scheduler.__main__.get_db_session",
                return_value=self._session_context(session),
            ),
        ):
            mock_engine_cls.return_value.process = AsyncMock(return_value=mock_result)
            await scheduler_main.link_verification()

        session.commit.assert_awaited_once()
        assert job.is_verified is True

    @pytest.mark.asyncio
    async def test_scam_analysis_creates_score(self):
        job = MagicMock()
        job.id = "job-2"
        job.title = "Security Engineer"
        job.company = "Acme"
        job.description = "desc"
        job.url = "https://example.com/job/2"
        job.scam_score = None

        session = self._mock_session()
        session.execute.return_value.scalars.return_value.all.return_value = [job]

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = {
            "scam_score": 10,
            "confidence": 0.9,
            "flags": ["urgent"],
            "reasons": ["pay"],
            "is_scam": False,
        }

        with (
            patch(
                "cybershield.engines.scam_detection.ScamDetectionEngine",
            ) as mock_engine_cls,
            patch(
                "cybershield.scheduler.__main__.get_db_session",
                return_value=self._session_context(session),
            ),
        ):
            mock_engine_cls.return_value.process = AsyncMock(return_value=mock_result)
            await scheduler_main.scam_analysis()

        session.commit.assert_awaited_once()
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_daily_report_sends_digest(self):
        session = self._mock_session()
        # 4 scalar calls: total (unused), new_today, expiring, high_match
        session.scalar.side_effect = [10, 3, 5, 7]

        mock_orchestrator = MagicMock()
        mock_orchestrator.send_daily_digest = AsyncMock()

        with (
            patch(
                "cybershield.notifications.orchestrator.NotificationOrchestrator",
                return_value=mock_orchestrator,
            ),
            patch("cybershield.scheduler.__main__.settings") as mock_settings,
            patch(
                "cybershield.scheduler.__main__.get_db_session",
                return_value=self._session_context(session),
            ),
        ):
            mock_settings.telegram_bot_token = None
            await scheduler_main.daily_report()

        mock_orchestrator.send_daily_digest.assert_awaited_once()
        payload = mock_orchestrator.send_daily_digest.await_args.args[0]
        assert payload["new_jobs"] == 3
        assert payload["expiring_soon"] == 5

    @pytest.mark.asyncio
    async def test_weekly_report_sends_report(self):
        session = self._mock_session()
        # 5 scalar calls: total, new, total_apps, apps_week, expiring_count
        session.scalar.side_effect = [100, 20, 15, 3, 2]
        # top_companies / top_skills execute results
        companies_result = MagicMock()
        companies_result.all.return_value = [("Microsoft", 5), ("Google", 3)]
        skills_result = MagicMock()
        skills_result.all.return_value = [("skill-1", 50)]
        session.execute.side_effect = [companies_result, skills_result]

        mock_orchestrator = MagicMock()
        mock_orchestrator.send_report = AsyncMock()

        with (
            patch(
                "cybershield.notifications.orchestrator.NotificationOrchestrator",
                return_value=mock_orchestrator,
            ),
            patch("cybershield.scheduler.__main__.settings") as mock_settings,
            patch(
                "cybershield.scheduler.__main__.get_db_session",
                return_value=self._session_context(session),
            ),
        ):
            mock_settings.telegram_bot_token = None
            await scheduler_main.weekly_report()

        mock_orchestrator.send_report.assert_awaited_once()
        report_type, payload = mock_orchestrator.send_report.await_args.args
        assert report_type == "weekly"
        assert payload["new_jobs"] == 20
        assert payload["total_jobs"] == 100
        assert payload["top_companies"][0] == ("Microsoft", 5)

    @pytest.mark.asyncio
    async def test_monthly_report_sends_report(self):
        session = self._mock_session()
        # 7 scalar calls: total, new, total_apps(unused), apps_month,
        # success_count, total_with_mode, remote_count
        session.scalar.side_effect = [
            1000,  # total_jobs
            150,  # new_this_month
            40,  # total_apps (unused)
            40,  # apps_this_month
            4,  # success_count
            10,  # total_with_mode
            5,  # remote_count
        ]
        companies_result = MagicMock()
        companies_result.all.return_value = [("Amazon", 9)]
        skills_result = MagicMock()
        skills_result.all.return_value = [("skill-2", 80)]
        salary_row = MagicMock()
        salary_row.avg_min = 50000
        salary_row.avg_max = 90000
        salary_result = MagicMock()
        salary_result.first.return_value = salary_row
        job_type_result = MagicMock()
        job_type_result.all.return_value = [("full_time", 8), ("remote", 2)]
        session.execute.side_effect = [
            companies_result,
            skills_result,
            salary_result,
            job_type_result,
        ]

        mock_orchestrator = MagicMock()
        mock_orchestrator.send_report = AsyncMock()

        with (
            patch(
                "cybershield.notifications.orchestrator.NotificationOrchestrator",
                return_value=mock_orchestrator,
            ),
            patch("cybershield.scheduler.__main__.settings") as mock_settings,
            patch(
                "cybershield.scheduler.__main__.get_db_session",
                return_value=self._session_context(session),
            ),
        ):
            mock_settings.telegram_bot_token = None
            await scheduler_main.monthly_report()

        mock_orchestrator.send_report.assert_awaited_once()
        report_type, payload = mock_orchestrator.send_report.await_args.args
        assert report_type == "monthly"
        assert payload["new_jobs"] == 150
        assert payload["success_rate"] == 10.0  # 4/40
        assert payload["avg_salary_range"] == "50000-90000"
        assert payload["remote_percentage"] == 50.0

    @pytest.mark.asyncio
    async def test_monthly_report_no_apps_zero_success_rate(self):
        session = self._mock_session()
        # 7 scalar calls with apps_this_month=0
        session.scalar.side_effect = [100, 10, 0, 0, 0, 1, 0]
        companies_result = MagicMock()
        companies_result.all.return_value = []
        skills_result = MagicMock()
        skills_result.all.return_value = []
        salary_result = MagicMock()
        salary_result.first.return_value = None  # no salary data
        job_type_result = MagicMock()
        job_type_result.all.return_value = []
        session.execute.side_effect = [
            companies_result,
            skills_result,
            salary_result,
            job_type_result,
        ]

        mock_orchestrator = MagicMock()
        mock_orchestrator.send_report = AsyncMock()

        with (
            patch(
                "cybershield.notifications.orchestrator.NotificationOrchestrator",
                return_value=mock_orchestrator,
            ),
            patch("cybershield.scheduler.__main__.settings") as mock_settings,
            patch(
                "cybershield.scheduler.__main__.get_db_session",
                return_value=self._session_context(session),
            ),
        ):
            mock_settings.telegram_bot_token = None
            await scheduler_main.monthly_report()

        mock_orchestrator.send_report.assert_awaited_once()
        report_type, payload = mock_orchestrator.send_report.await_args.args
        assert payload["success_rate"] == 0.0
        assert payload["avg_salary_range"] == "N/A"
        assert payload["remote_percentage"] == 0.0
