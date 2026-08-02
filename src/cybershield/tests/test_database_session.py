"""
Tests for the async database session management module.

Covers engine-kwargs selection (SQLite vs PostgreSQL), lazy initialization of
the engine and session factory, init_db/close_db, and the get_db_session /
get_db context managers — with the module globals reset between tests.
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import cybershield.database.session as session_module


@pytest.fixture(autouse=True)
def _reset_globals():
    """Reset the lazy-init globals before and after each test."""
    original_engine = session_module._engine
    original_factory = session_module._async_session_factory
    session_module._engine = None
    session_module._async_session_factory = None
    yield
    # Dispose any engine created during the test so the aiosqlite thread
    # pool is released before restoring the module globals.
    if session_module._engine is not None:
        import asyncio

        asyncio.run(session_module._engine.dispose())
    session_module._engine = original_engine
    session_module._async_session_factory = original_factory


class TestGetEngineKwargs:
    def test_sqlite_kwargs(self, monkeypatch):
        settings = SimpleNamespace(
            debug=False,
            database_url="sqlite+aiosqlite:///./data/test.db",
        )
        monkeypatch.setattr("cybershield.config.get_settings", lambda: settings)
        kwargs = session_module._get_engine_kwargs()
        assert kwargs["echo"] is False
        assert kwargs["pool_pre_ping"] is True
        assert kwargs["connect_args"] == {"check_same_thread": False}
        assert "pool_size" not in kwargs

    def test_postgres_kwargs(self, monkeypatch):
        settings = SimpleNamespace(
            debug=True,
            database_url="postgresql+asyncpg://user:pass@localhost/db",
        )
        monkeypatch.setattr("cybershield.config.get_settings", lambda: settings)
        kwargs = session_module._get_engine_kwargs()
        assert kwargs["echo"] is True
        assert kwargs["pool_size"] == 10
        assert kwargs["max_overflow"] == 20
        assert kwargs["pool_timeout"] == 30
        assert kwargs["pool_recycle"] == 1800
        assert "connect_args" not in kwargs


class TestLazyInitialization:
    def test_get_engine_lazy_creates_once(self, monkeypatch):
        settings = SimpleNamespace(
            debug=False,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        monkeypatch.setattr("cybershield.config.get_settings", lambda: settings)

        engine1 = session_module.get_engine()
        engine2 = session_module.get_engine()
        assert engine1 is engine2  # cached after first creation

    def test_get_session_factory_uses_engine(self, monkeypatch):
        settings = SimpleNamespace(
            debug=False,
            database_url="sqlite+aiosqlite:///:memory:",
        )
        monkeypatch.setattr("cybershield.config.get_settings", lambda: settings)

        factory = session_module.get_session_factory()
        assert factory is session_module.get_session_factory()  # cached
        assert factory.class_.__name__ == "AsyncSession"


class TestInitAndClose:
    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self, monkeypatch, tmp_path):
        db_path = tmp_path / "test.db"
        settings = SimpleNamespace(
            debug=False,
            database_url=f"sqlite+aiosqlite:///{db_path}",
        )
        monkeypatch.setattr("cybershield.config.get_settings", lambda: settings)

        await session_module.init_db()

        # Verify the side effect: the SQLite file now exists and contains
        # the model tables.
        from sqlalchemy import create_engine

        sync_engine = create_engine(f"sqlite:///{db_path}")
        with sync_engine.connect() as conn:
            tables = {
                row[0]
                for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")
            }
        sync_engine.dispose()
        assert "companies" in tables
        assert "jobs" in tables

        await session_module.close_db()

    @pytest.mark.asyncio
    async def test_close_db_disposes_engine(self):
        engine = AsyncMock()
        with patch.object(session_module, "_engine", engine):
            await session_module.close_db()
        engine.dispose.assert_awaited_once()


class TestGetDbSession:
    @staticmethod
    def _make_session_factory(session):
        """Return a get_session_factory stand-in yielding the given session.

        ``get_db_session`` calls ``get_session_factory()()`` — first call
        returns a sessionmaker (callable), second call returns the session.
        """

        def sessionmaker():
            return session

        def get_factory():
            return sessionmaker

        return get_factory

    @pytest.mark.asyncio
    async def test_commits_on_success(self):
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        with patch.object(
            session_module,
            "get_session_factory",
            self._make_session_factory(session),
        ):
            async with session_module.get_db_session() as s:
                assert s is session

        session.commit.assert_awaited_once()
        session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rolls_back_on_error(self):
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        with patch.object(
            session_module,
            "get_session_factory",
            self._make_session_factory(session),
        ):
            with pytest.raises(RuntimeError):
                async with session_module.get_db_session() as _s:
                    raise RuntimeError("boom")

        session.rollback.assert_awaited_once()
        session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        @asynccontextmanager
        async def fake_db_session():
            yield session

        with patch.object(session_module, "get_db_session", fake_db_session):
            yielded = [s async for s in session_module.get_db()]
        assert yielded == [session]
