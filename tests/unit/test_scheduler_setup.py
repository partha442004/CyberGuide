"""Unit tests for scheduler/setup.py."""

from unittest.mock import MagicMock, patch


class TestSchedulerSetup:
    """Tests for scheduler setup."""

    @patch("interntrack.scheduler.setup.get_settings")
    @patch("interntrack.scheduler.setup.scheduler")
    def test_setup_scheduler_adds_jobs(self, mock_scheduler, mock_get_settings):
        from interntrack.scheduler.setup import setup_scheduler

        mock_settings = MagicMock()
        mock_settings.scrape_interval_minutes = 30
        mock_get_settings.return_value = mock_settings

        mock_scheduler.add_job = MagicMock()
        mock_scheduler.start = MagicMock()

        result = setup_scheduler()

        # 9 jobs: discovery, daily + weekly reports, link verification,
        # expiry cleanup, morning/evening closing-soon sweeps, daily
        # match-% progress snapshots, and the interview reminders.
        assert mock_scheduler.add_job.call_count == 9
        assert result == mock_scheduler

    @patch("interntrack.scheduler.setup.get_settings")
    @patch("interntrack.scheduler.setup.scheduler")
    def test_setup_scheduler_job_ids(self, mock_scheduler, mock_get_settings):
        from interntrack.scheduler.setup import setup_scheduler

        mock_settings = MagicMock()
        mock_settings.scrape_interval_minutes = 30
        mock_get_settings.return_value = mock_settings

        mock_scheduler.add_job = MagicMock()
        mock_scheduler.start = MagicMock()

        setup_scheduler()

        # Verify job IDs
        job_ids = [
            call.kwargs.get("id") for call in mock_scheduler.add_job.call_args_list
        ]
        assert "job_discovery" in job_ids
        assert "daily_report" in job_ids
        assert "weekly_report" in job_ids
        assert "link_verification" in job_ids
        assert "expire_jobs" in job_ids
        assert "closing_soon_alerts_morning" in job_ids
        assert "closing_soon_alerts_evening" in job_ids

    @patch("interntrack.scheduler.setup.get_settings")
    @patch("interntrack.scheduler.setup.scheduler")
    def test_setup_scheduler_replace_existing(self, mock_scheduler, mock_get_settings):
        from interntrack.scheduler.setup import setup_scheduler

        mock_settings = MagicMock()
        mock_settings.scrape_interval_minutes = 30
        mock_get_settings.return_value = mock_settings

        mock_scheduler.add_job = MagicMock()
        mock_scheduler.start = MagicMock()

        setup_scheduler()

        # All jobs should have replace_existing=True
        for call in mock_scheduler.add_job.call_args_list:
            assert call.kwargs.get("replace_existing") is True
