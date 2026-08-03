"""
Unit Tests for interntrack database session management (extended).

Covers ``close_db``, ``get_db_session`` (commit + rollback paths) and
``get_db``.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interntrack.database import session as session_module
from interntrack.database.session import close_db, get_db, get_db_session


class TestCloseDb:
    """Tests for close_db."""

    @pytest.mark.asyncio
    async def test_disposes_engine(self):
        """Should dispose the engine on close."""
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        with patch.object(session_module, "engine", mock_engine):
            await close_db()
            mock_engine.dispose.assert_awaited_once()


class TestGetDbSession:
    """Tests for the get_db_session context manager."""

    def _mock_factory(self, session):
        """Build a session-factory mock supporting async context protocol."""
        context_manager = MagicMock()
        context_manager.__aenter__ = AsyncMock(return_value=session)
        context_manager.__aexit__ = AsyncMock(return_value=False)
        return MagicMock(return_value=context_manager)

    @pytest.mark.asyncio
    async def test_commits_on_success(self):
        """Should commit and close on clean exit."""
        session = AsyncMock()
        factory = self._mock_factory(session)

        with patch.object(session_module, "async_session_factory", factory):
            async with get_db_session() as yielded:
                assert yielded is session

        session.commit.assert_awaited_once()
        session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rolls_back_on_exception(self):
        """Should roll back and re-raise on error."""
        session = AsyncMock()
        session.commit.side_effect = RuntimeError("boom")
        factory = self._mock_factory(session)

        with (
            patch.object(session_module, "async_session_factory", factory),
            pytest.raises(RuntimeError),
        ):
            async with get_db_session():
                pass

        session.rollback.assert_awaited_once()
        session.close.assert_awaited_once()


class TestDbQueryMetrics:
    """Tests for the DB query duration metrics instrumentation."""

    @pytest.mark.asyncio
    async def test_query_records_metric(self, monkeypatch):
        """A real DB query should record a duration through the metrics store."""
        from interntrack.metrics import business_metrics_store

        record_mock = MagicMock()
        monkeypatch.setattr(business_metrics_store, "record_db_query", record_mock)

        # Use a hermetic in-memory engine (the module-level engine points at a
        # file DB that does not exist on CI), wire the metrics listeners, then
        # run a trivial query so the before/after handlers fire.
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_module.install_db_query_metrics(engine.sync_engine)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()

        record_mock.assert_called_once()
        (duration_ms,) = record_mock.call_args.args
        assert duration_ms >= 0


class TestGetDb:
    """Tests for the get_db FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_yields_session_from_context_manager(self):
        """Should delegate to get_db_session and yield its session."""
        session = AsyncMock()
        context_manager = MagicMock()
        context_manager.__aenter__ = AsyncMock(return_value=session)
        context_manager.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "interntrack.database.session.get_db_session",
            MagicMock(return_value=context_manager),
        ):
            generator = get_db()
            result = await generator.__anext__()
            assert result is session
            with pytest.raises(StopAsyncIteration):
                await generator.__anext__()
