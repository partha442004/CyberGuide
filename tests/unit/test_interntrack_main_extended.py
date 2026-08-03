"""
Unit Tests for the interntrack FastAPI app (extended).

Covers the application ``lifespan`` startup/shutdown sequence and the ``cli``
entry point.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interntrack.main import app, cli, lifespan


class TestLifespan:
    """Tests for the application lifespan manager."""

    @pytest.mark.asyncio
    async def test_startup_and_shutdown(self):
        """Should init DB on startup and close it on shutdown."""
        with (
            patch("interntrack.main.init_db", new=AsyncMock()) as mock_init,
            patch("interntrack.main.close_db", new=AsyncMock()) as mock_close,
        ):
            async with lifespan(app):
                mock_init.assert_awaited_once()
                mock_close.assert_not_awaited()

        mock_close.assert_awaited_once()


class TestCli:
    """Tests for the CLI entry point."""

    def test_cli_runs_uvicorn(self):
        """Should call uvicorn.run with the app string."""
        mock_run = MagicMock()
        with patch("uvicorn.run", mock_run):
            cli()
        mock_run.assert_called_once()
        assert mock_run.call_args.args[0] == "interntrack.main:app"
