"""
Unit tests for the CyberGuide startup script (``src/cybershield/start.py``).

Covers the three service launchers (API, dashboard, scheduler) and the
``main()`` orchestration: success paths, error paths, Ctrl+C shutdown, and
process-exit handling — all with mocked ``subprocess.Popen``.
"""

from unittest.mock import MagicMock, patch

import pytest

from cybershield import start


class TestStartApi:
    def test_spawns_uvicorn_with_expected_args(self):
        proc = MagicMock()
        with patch("cybershield.start.subprocess.Popen", return_value=proc) as popen:
            result = start.start_api()

        assert result is proc
        cmd = popen.call_args[0][0]
        assert "uvicorn" in cmd
        assert "cybershield.main:app" in cmd
        assert "--host" in cmd
        assert "8000" in cmd

    def test_returns_none_on_error(self):
        with patch(
            "cybershield.start.subprocess.Popen",
            side_effect=OSError("no uvicorn"),
        ):
            assert start.start_api() is None


class TestStartDashboard:
    def test_spawns_streamlit_with_expected_args(self):
        proc = MagicMock()
        with patch("cybershield.start.subprocess.Popen", return_value=proc) as popen:
            result = start.start_dashboard()

        assert result is proc
        cmd = popen.call_args[0][0]
        assert "streamlit" in cmd
        assert "cybershield/dashboard/app.py" in cmd
        assert "--server.port" in cmd
        assert "8501" in cmd

    def test_returns_none_on_error(self):
        with patch(
            "cybershield.start.subprocess.Popen",
            side_effect=OSError("no streamlit"),
        ):
            assert start.start_dashboard() is None


class TestStartScheduler:
    def test_spawns_scheduler_module(self):
        proc = MagicMock()
        with patch("cybershield.start.subprocess.Popen", return_value=proc) as popen:
            result = start.start_scheduler()

        assert result is proc
        cmd = popen.call_args[0][0]
        assert "-m" in cmd
        assert "cybershield.scheduler" in cmd

    def test_returns_none_on_error(self):
        with patch(
            "cybershield.start.subprocess.Popen",
            side_effect=OSError("no scheduler"),
        ):
            assert start.start_scheduler() is None


def _fake_proc(poll_result=None, returncode=0):
    """A minimal stand-in for a subprocess.Popen object."""
    proc = MagicMock()
    proc.poll.return_value = poll_result
    proc.returncode = returncode
    proc.pid = 12345
    return proc


class TestMain:
    def test_starts_all_services_and_handles_ctrl_c(self):
        """Ctrl+C during the loop stops all services and exits 0."""
        proc = _fake_proc()
        with (
            patch("cybershield.start.start_api", return_value=proc),
            patch("cybershield.start.start_dashboard", return_value=proc),
            patch("cybershield.start.start_scheduler", return_value=proc),
            patch(
                "cybershield.start.time.sleep",
                side_effect=[None, None, KeyboardInterrupt()],
            ),
            patch("cybershield.start.sys.exit") as mock_exit,
        ):
            start.main()

        proc.terminate.assert_called()
        mock_exit.assert_called_once_with(0)

    def test_exits_when_api_fails_to_start(self):
        """If the API server can't start, main exits 1 immediately.

        sys.exit is patched with side_effect=SystemExit so main actually stops
        there (a plain mock would let it continue into real subprocesses).
        """
        with (
            patch("cybershield.start.start_api", return_value=None),
            patch("cybershield.start.start_dashboard"),
            patch("cybershield.start.start_scheduler"),
            patch("cybershield.start.time.sleep"),
            patch(
                "cybershield.start.sys.exit",
                side_effect=SystemExit(1),
            ) as mock_exit,
        ):
            with pytest.raises(SystemExit):
                start.main()

        mock_exit.assert_called_once_with(1)

    def test_stops_all_when_a_process_exits(self):
        """A child process exiting stops the remaining services and exits 1.

        sys.exit is patched with side_effect=SystemExit so the loop actually
        stops on the first detected exit (a plain mock would loop forever).
        """
        api_proc = _fake_proc()
        dashboard_proc = _fake_proc(poll_result=1, returncode=1)
        scheduler_proc = _fake_proc()
        with (
            patch("cybershield.start.start_api", return_value=api_proc),
            patch("cybershield.start.start_dashboard", return_value=dashboard_proc),
            patch("cybershield.start.start_scheduler", return_value=scheduler_proc),
            # Never raise: the loop must run until the poll detects the exit.
            patch("cybershield.start.time.sleep", return_value=None),
            patch(
                "cybershield.start.sys.exit",
                side_effect=SystemExit(1),
            ) as mock_exit,
        ):
            with pytest.raises(SystemExit):
                start.main()

        # dashboard_proc itself already exited; the others get terminated.
        api_proc.terminate.assert_called()
        scheduler_proc.terminate.assert_called()
        mock_exit.assert_called_once_with(1)
