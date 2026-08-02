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
