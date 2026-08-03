"""
Unit tests for the remaining uncovered branches of the CyberGuide scheduler
entry point (``src/cybershield/scheduler/__main__.py``).

Covers: Telegram notifier registration inside daily/weekly/monthly report
jobs, the ``continue`` path in ``scam_analysis`` for already-scored jobs, the
``shutdown(signum, frame)`` signal handler, and the job listing log loop in
``main()``.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cybershield.scheduler import __main__ as scheduler_main


class TestTelegramBranches:
    """Report jobs must register a Telegram notifier when configured."""

    @staticmethod
    def _mock_session(**overrides) -> MagicMock:
        session = MagicMock()
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
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=None)
        return ctx

    @pytest.mark.asyncio
    async def test_daily_report_registers_telegram_when_token_set(self):
        session = self._mock_session()
        session.scalar.side_effect = [10, 3, 5, 7]

        mock_orchestrator = MagicMock()
        mock_orchestrator.send_daily_digest = AsyncMock()
        mock_notifier = MagicMock()

        with (
            patch(
                "cybershield.notifications.orchestrator.NotificationOrchestrator",
                return_value=mock_orchestrator,
            ),
            patch(
                "cybershield.notifications.telegram.TelegramNotifier",
                return_value=mock_notifier,
            ),
            patch("cybershield.scheduler.__main__.settings") as mock_settings,
            patch(
                "cybershield.scheduler.__main__.get_db_session",
                return_value=self._session_context(session),
            ),
        ):
            mock_settings.telegram_bot_token = "bot-token"
            mock_settings.telegram_chat_id = "chat-id"
            await scheduler_main.daily_report()

        mock_orchestrator.register.assert_called_once_with("telegram", mock_notifier)
        mock_orchestrator.send_daily_digest.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_weekly_report_registers_telegram_when_token_set(self):
        session = self._mock_session()
        session.scalar.side_effect = [100, 20, 15, 3, 2]
        companies_result = MagicMock()
        companies_result.all.return_value = [("Microsoft", 5)]
        skills_result = MagicMock()
        skills_result.all.return_value = [("skill-1", 50)]
        session.execute.side_effect = [companies_result, skills_result]

        mock_orchestrator = MagicMock()
        mock_orchestrator.send_report = AsyncMock()
        mock_notifier = MagicMock()

        with (
            patch(
                "cybershield.notifications.orchestrator.NotificationOrchestrator",
                return_value=mock_orchestrator,
            ),
            patch(
                "cybershield.notifications.telegram.TelegramNotifier",
                return_value=mock_notifier,
            ),
            patch("cybershield.scheduler.__main__.settings") as mock_settings,
            patch(
                "cybershield.scheduler.__main__.get_db_session",
                return_value=self._session_context(session),
            ),
        ):
            mock_settings.telegram_bot_token = "bot-token"
            mock_settings.telegram_chat_id = "chat-id"
            await scheduler_main.weekly_report()

        mock_orchestrator.register.assert_called_once_with("telegram", mock_notifier)
        mock_orchestrator.send_report.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_monthly_report_registers_telegram_when_token_set(self):
        session = self._mock_session()
        session.scalar.side_effect = [
            1000,
            150,
            40,
            40,
            4,
            10,
            5,
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
        job_type_result.all.return_value = [("full_time", 8)]
        session.execute.side_effect = [
            companies_result,
            skills_result,
            salary_result,
            job_type_result,
        ]

        mock_orchestrator = MagicMock()
        mock_orchestrator.send_report = AsyncMock()
        mock_notifier = MagicMock()

        with (
            patch(
                "cybershield.notifications.orchestrator.NotificationOrchestrator",
                return_value=mock_orchestrator,
            ),
            patch(
                "cybershield.notifications.telegram.TelegramNotifier",
                return_value=mock_notifier,
            ),
            patch("cybershield.scheduler.__main__.settings") as mock_settings,
            patch(
                "cybershield.scheduler.__main__.get_db_session",
                return_value=self._session_context(session),
            ),
        ):
            mock_settings.telegram_bot_token = "bot-token"
            mock_settings.telegram_chat_id = "chat-id"
            await scheduler_main.monthly_report()

        mock_orchestrator.register.assert_called_once_with("telegram", mock_notifier)
        mock_orchestrator.send_report.assert_awaited_once()


class TestScamSkipPath:
    """scam_analysis must skip jobs that already have a scam score."""

    @pytest.mark.asyncio
    async def test_skips_jobs_with_existing_scam_score(self):
        scored_job = MagicMock()
        scored_job.id = "job-scored"
        scored_job.title = "Security Engineer"
        scored_job.company = "Acme"
        scored_job.description = "desc"
        scored_job.url = "https://example.com/job/scored"
        scored_job.scam_score = 85  # already scored -> continue

        session = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [scored_job]
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        session.add = MagicMock()

        engine = MagicMock()
        engine.process = AsyncMock()

        with (
            patch(
                "cybershield.engines.scam_detection.ScamDetectionEngine",
                return_value=engine,
            ),
            patch(
                "cybershield.scheduler.__main__.get_db_session",
                return_value=self._session_context(session),
            ),
        ):
            await scheduler_main.scam_analysis()

        engine.process.assert_not_awaited()
        session.add.assert_not_called()
        session.commit.assert_awaited_once()

    @staticmethod
    def _session_context(session) -> MagicMock:
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=session)
        ctx.__aexit__ = AsyncMock(return_value=None)
        return ctx


class TestMainShutdownAndLogging:
    """main() shutdown handler and job-list logging."""

    @pytest.mark.asyncio
    @patch("cybershield.scheduler.__main__.init_db", new_callable=AsyncMock)
    async def test_shutdown_signal_handler_stops_scheduler(self, mock_init_db):
        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []
        captured = {}

        def capture_signal(signum, handler):
            captured["handler"] = handler

        with (
            patch(
                "cybershield.scheduler.__main__.create_scheduler",
                return_value=mock_scheduler,
            ),
            patch("cybershield.scheduler.__main__.signal.signal", side_effect=capture_signal),
            patch(
                "cybershield.scheduler.__main__.asyncio.sleep",
                side_effect=KeyboardInterrupt(),
            ),
        ):
            await scheduler_main.main()

        # The registered SIGINT/SIGTERM handler must call scheduler.shutdown().
        import signal as signal_module

        captured["handler"](signal_module.SIGTERM, None)
        mock_scheduler.shutdown.assert_called()

    @pytest.mark.asyncio
    @patch("cybershield.scheduler.__main__.init_db", new_callable=AsyncMock)
    async def test_main_logs_registered_jobs(self, mock_init_db):
        mock_scheduler = MagicMock()
        job = MagicMock()
        job.name = "job_discovery"
        job.id = "job_discovery"
        job.trigger = "interval[minutes=30]"
        mock_scheduler.get_jobs.return_value = [job]

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
            patch("cybershield.scheduler.__main__.logger") as mock_logger,
        ):
            await scheduler_main.main()

        mock_scheduler.start.assert_called_once()
        mock_logger.info.assert_any_call(f"  - {job.name} ({job.id}): {job.trigger}")
