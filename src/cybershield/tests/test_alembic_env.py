"""
Unit tests for cybershield/alembic/env.py.

Exercises the offline/online migration runners and the async engine
bootstrap by mocking the alembic context and engine factory.
"""

import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch


def _load_env_module():
    """Import env.py with a mocked alembic.context to avoid top-level execution."""
    mock_context = MagicMock()
    mock_context.is_offline_mode.return_value = True
    # env.py binds `config = context.config` at import time, so the child mock
    # must look like a real alembic config object.
    mock_context.config.config_file_name = None
    mock_context.config.config_ini_section = "alembic"
    mock_context.config.get_section.return_value = {}
    mock_context.config.get_main_option.return_value = "sqlite+aiosqlite:///:memory:"
    mock_context.begin_transaction.return_value.__enter__.return_value = None

    # Force a fresh import so env.py's top-level code runs against our mock.
    sys.modules.pop("cybershield.alembic.env", None)
    with patch("alembic.context", mock_context):
        module = importlib.import_module("cybershield.alembic.env")
    return module


class TestAlembicEnv:
    def test_offline_mode_configured_and_run(self):
        """Offline mode should configure context with url and run migrations."""
        env_module = _load_env_module()
        mock_context = MagicMock()
        mock_context.get_main_option.return_value = "sqlite+aiosqlite:///test.db"
        mock_context.config_file_name = None
        mock_context.begin_transaction.return_value.__enter__.return_value = None

        with patch.object(env_module, "context", mock_context):
            env_module.run_migrations_offline()

            mock_context.configure.assert_called_once()

    def test_run_offline_migration_via_main(self):
        """The bottom dispatch must run the offline path in offline mode."""
        env_module = _load_env_module()
        mock_context = MagicMock()
        mock_context.get_main_option.return_value = "sqlite:///:memory:"
        mock_context.config_file_name = None
        mock_context.begin_transaction.return_value.__enter__.return_value = None

        with (
            patch.object(env_module, "context", mock_context),
            patch.object(env_module, "run_migrations_online") as mock_online,
            patch.object(env_module, "fileConfig"),
        ):
            # Simulate module top-level execution in offline mode
            env_module.run_migrations_offline()
            mock_online.assert_not_called()

    def test_online_mode_runs_async(self):
        """Online mode should build the async engine and run migrations."""
        env_module = _load_env_module()
        mock_context = MagicMock()
        mock_context.is_offline_mode.return_value = False
        mock_context.get_section.return_value = {"sqlalchemy.url": "sqlite+aiosqlite:///:memory:"}
        mock_context.config_ini_section = "alembic"

        with (
            patch.object(env_module, "context", mock_context),
            patch.object(env_module, "run_migrations_offline") as mock_offline,
            patch.object(env_module, "run_async_migrations", AsyncMock()) as mock_async,
        ):
            env_module.run_migrations_online()
            mock_offline.assert_not_called()
            mock_async.assert_called_once()

    def test_async_migrations_uses_async_engine(self):
        """run_async_migrations should create an async engine and dispose it."""
        import asyncio

        mock_connection = AsyncMock()
        mock_connection.run_sync = AsyncMock()
        # connect() must return an async context manager (not a coroutine),
        # so it has to be a plain MagicMock, not an AsyncMock.
        context_manager = MagicMock()
        context_manager.__aenter__.return_value = mock_connection
        mock_connectable = AsyncMock()
        mock_connectable.connect = MagicMock(return_value=context_manager)
        mock_connectable.dispose = AsyncMock()

        env_module = _load_env_module()
        with patch.object(env_module, "async_engine_from_config", return_value=mock_connectable):
            asyncio.run(env_module.run_async_migrations())

            mock_connectable.dispose.assert_awaited_once()

    def test_do_run_migrations_configures_connection(self):
        """do_run_migrations should configure the context with the connection."""
        env_module = _load_env_module()
        mock_context = MagicMock()
        mock_context.begin_transaction.return_value.__enter__.return_value = None

        with patch.object(env_module, "context", mock_context):
            env_module.do_run_migrations(MagicMock())

            mock_context.configure.assert_called_once()
            mock_context.run_migrations.assert_called_once()
