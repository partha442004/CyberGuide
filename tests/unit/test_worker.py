"""Unit tests for worker.py."""

import signal
from unittest.mock import MagicMock, patch

import pytest


class TestWorkerMain:
    """Tests for the worker main loop."""

    @patch("interntrack.worker.logger")
    @patch("interntrack.worker.setup_logging")
    @patch("interntrack.worker.setup_scheduler")
    @pytest.mark.asyncio
    async def test_main_sets_up_and_starts_scheduler(
        self,
        mock_setup_scheduler,
        mock_setup_logging,
        mock_logger,
    ):
        from interntrack.worker import main

        mock_scheduler = MagicMock()
        mock_setup_scheduler.return_value = mock_scheduler

        call_count = 0

        async def mock_sleep_fn(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt

        with (
            patch("asyncio.sleep", side_effect=mock_sleep_fn),
            patch("interntrack.worker.signal.signal"),
        ):
            await main()

        mock_setup_logging.assert_called_once()
        mock_setup_scheduler.assert_called_once()
        mock_scheduler.start.assert_called_once()
        # KeyboardInterrupt path shuts the scheduler down
        mock_scheduler.shutdown.assert_called_once()
        mock_logger.info.assert_any_call("Starting InternTrack worker...")

    @patch("interntrack.worker.logger")
    @patch("interntrack.worker.setup_logging")
    @patch("interntrack.worker.setup_scheduler")
    @pytest.mark.asyncio
    async def test_main_registers_signal_handlers(
        self,
        mock_setup_scheduler,
        mock_setup_logging,
        mock_logger,
    ):
        from interntrack.worker import main

        mock_scheduler = MagicMock()
        mock_setup_scheduler.return_value = mock_scheduler

        with (
            patch("asyncio.sleep", side_effect=KeyboardInterrupt),
            patch("interntrack.worker.signal.signal") as mock_signal,
        ):
            await main()

        # SIGINT and SIGTERM handlers are registered
        calls = [call.args[0] for call in mock_signal.call_args_list]
        assert signal.SIGINT in calls
        assert signal.SIGTERM in calls
        mock_scheduler.shutdown.assert_called_once()


class TestShutdownHandler:
    """Tests for the worker shutdown signal handler."""

    @patch("interntrack.worker.sys.exit")
    def test_shutdown_handler_stops_scheduler_and_exits(self, mock_exit):
        import asyncio

        from interntrack.worker import main

        mock_logger = MagicMock()
        mock_scheduler = MagicMock()

        # Capture the shutdown_handler defined inside main() via mocked signal
        # registration, then invoke it to verify shutdown + exit behavior.
        captured = {}

        def capture_signal(signum, handler):
            captured[signum] = handler

        with (
            patch("interntrack.worker.logger", mock_logger),
            patch("interntrack.worker.setup_logging"),
            patch(
                "interntrack.worker.setup_scheduler",
                return_value=mock_scheduler,
            ),
            patch(
                "interntrack.worker.signal.signal",
                side_effect=capture_signal,
            ),
            patch("asyncio.sleep", side_effect=KeyboardInterrupt),
        ):
            asyncio.run(main())
            # Invoke the captured handler while the module logger is still
            # patched, so the shutdown log is recorded on the mock.
            shutdown_handler = captured[signal.SIGINT]
            shutdown_handler(None, None)

        mock_scheduler.shutdown.assert_called()
        mock_exit.assert_called_once_with(0)
        mock_logger.info.assert_any_call("Shutting down worker...")


class TestWorkerEntrypoint:
    """Tests for the worker module entrypoint guard."""

    def test_module_has_entrypoint_guard(self):
        """The worker module guards asyncio.run behind __main__."""
        import inspect

        import interntrack.worker as worker_module

        source = inspect.getsource(worker_module)
        assert 'if __name__ == "__main__":' in source
        assert "asyncio.run(main())" in source
