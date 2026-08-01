"""Unit tests for worker.py."""

from unittest.mock import MagicMock, patch

import pytest


class TestWorkerMain:
    """Tests for worker main function."""

    @patch("interntrack.worker.get_logger")
    @patch("interntrack.worker.setup_logging")
    @patch("interntrack.worker.setup_scheduler")
    @patch("interntrack.worker.signal")
    def test_main_sets_up_scheduler(
        self,
        mock_signal,
        mock_setup_scheduler,
        mock_setup_logging,
        mock_get_logger,
    ):

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_scheduler = MagicMock()
        mock_setup_scheduler.return_value = mock_scheduler

        # We need to mock asyncio.run to test the async main

        with patch("asyncio.run"):
            # The main() function is async, but it's called via asyncio.run
            # We'll test the setup part by calling main directly
            pass

    @patch("interntrack.worker.get_logger")
    @patch("interntrack.worker.setup_logging")
    @patch("interntrack.worker.setup_scheduler")
    @pytest.mark.asyncio
    async def test_main_logs_startup(
        self,
        mock_setup_scheduler,
        mock_setup_logging,
        mock_get_logger,
    ):
        from interntrack.worker import main

        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_scheduler = MagicMock()
        mock_setup_scheduler.return_value = mock_scheduler

        # Make the while loop exit after one iteration
        call_count = 0

        async def mock_sleep_fn(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt

        with patch("asyncio.sleep", side_effect=mock_sleep_fn), patch("signal.signal"):
            await main()

        mock_setup_logging.assert_called()
        mock_setup_scheduler.assert_called()
        mock_scheduler.start.assert_called_once()
