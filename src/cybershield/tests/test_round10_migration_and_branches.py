"""
Round 10 coverage push — migration + last remaining source branches.

Targets the final under-covered code paths across the combined suite:

1. ``cybershield/alembic/versions/001_initial_schema.py`` (was **0%** — the
   only migration script, 73 statements never executed): runs the real
   ``upgrade()`` / ``downgrade()`` against an in-memory SQLite engine through
   an alembic ``Operations`` bound to a ``MigrationContext``.
2. ``cybershield/alembic/env.py`` line 27 (``fileConfig`` with a real config
   file name) and line 77 (the module-level online-mode dispatch).
3. ``cybershield/dashboard/app.py`` lines 591-592 (resume upload success
   branch) and 674 (Save Settings button).
4. ``cybershield/scrapers/usa/linkedin.py`` line 82 (title with a location
   that has more than one " in " segment).
5. ``interntrack/main.py`` line 54 (``RateLimitMiddleware`` registered when
   rate limiting is enabled).
6. ``cybershield/middleware/auth.py`` line 49 (API keys read from settings).
7. ``cybershield/engines/base.py`` line 57 and
   ``cybershield/scrapers/companies/base_company.py`` line 74 (abstract
   method bodies reached via ``super()``).
8. ``interntrack/api/v1/notifications.py`` lines 29 and 33 (email + slack
   channel listing).
"""

import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from cybershield.engines.base import BaseEngine, EngineResult
from cybershield.middleware.auth import APIKeyMiddleware
from cybershield.scrapers.companies.base_company import BaseCompanyScraper
from cybershield.scrapers.usa.linkedin import LinkedInScraper

# ---------------------------------------------------------------------------
# 1. Alembic migration (001_initial_schema.py) — 0% -> ~100%
# ---------------------------------------------------------------------------


class TestInitialMigration:
    """Run the real migration script against an in-memory SQLite engine."""

    def _load(self):
        return importlib.import_module("cybershield.alembic.versions.001_initial_schema")

    def test_upgrade_creates_all_tables(self):
        migration = self._load()
        engine = sa.create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            ops = Operations(ctx)
            with patch.object(migration, "op", ops):
                migration.upgrade()
            names = sa.inspect(conn).get_table_names()

        assert "users" in names
        assert "companies" in names
        assert "jobs" in names
        assert "applications" in names
        assert "skills" in names
        assert "watchlists" in names
        assert "notification_config" in names
        assert "resume_data" in names

    def test_downgrade_drops_everything(self):
        migration = self._load()
        engine = sa.create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            ops = Operations(ctx)
            with patch.object(migration, "op", ops):
                migration.upgrade()
                assert "users" in sa.inspect(conn).get_table_names()
                migration.downgrade()
            names = sa.inspect(conn).get_table_names()

        assert names == []

    def test_upgrade_downgrade_is_idempotent_cycle(self):
        """Upgrade then downgrade twice — every op is covered both ways."""
        migration = self._load()
        engine = sa.create_engine("sqlite:///:memory:")
        for _ in range(2):
            with engine.connect() as conn:
                ctx = MigrationContext.configure(conn)
                ops = Operations(ctx)
                with patch.object(migration, "op", ops):
                    migration.upgrade()
                    migration.downgrade()
            with engine.connect() as conn:
                assert sa.inspect(conn).get_table_names() == []


# ---------------------------------------------------------------------------
# 2. alembic/env.py — fileConfig line + module-level online dispatch
# ---------------------------------------------------------------------------


def _load_env_module(offline: bool, config_file_name: str | None):
    """Import env.py with a mocked alembic context."""
    mock_context = MagicMock()
    mock_context.is_offline_mode.return_value = offline
    mock_context.config.config_file_name = config_file_name
    mock_context.config.config_ini_section = "alembic"
    mock_context.config.get_section.return_value = {}
    mock_context.config.get_main_option.return_value = "sqlite+aiosqlite:///:memory:"
    mock_context.begin_transaction.return_value.__enter__.return_value = None

    sys.modules.pop("cybershield.alembic.env", None)
    with patch("alembic.context", mock_context):
        module = importlib.import_module("cybershield.alembic.env")
    return module


class TestAlembicEnvBranches:
    def test_fileconfig_runs_when_config_file_present(self):
        """env.py line 27: fileConfig() called when a config file name is set."""
        with patch("logging.config.fileConfig") as mock_fileconfig:
            _load_env_module(offline=True, config_file_name="alembic.ini")
            mock_fileconfig.assert_called_once()

    def test_module_level_online_dispatch(self):
        """env.py line 77: the else branch calls run_migrations_online()."""
        mock_connection = AsyncMock()
        mock_connection.run_sync = AsyncMock()
        context_manager = MagicMock()
        context_manager.__aenter__.return_value = mock_connection
        mock_connectable = AsyncMock()
        mock_connectable.connect = MagicMock(return_value=context_manager)
        mock_connectable.dispose = AsyncMock()

        mock_context = MagicMock()
        mock_context.is_offline_mode.return_value = False
        mock_context.config.config_file_name = None
        mock_context.config.config_ini_section = "alembic"
        mock_context.config.get_section.return_value = {}
        mock_context.config.get_main_option.return_value = "sqlite+aiosqlite:///:memory:"

        sys.modules.pop("cybershield.alembic.env", None)
        with (
            patch("alembic.context", mock_context),
            patch(
                "sqlalchemy.ext.asyncio.async_engine_from_config",
                return_value=mock_connectable,
            ),
        ):
            module = importlib.import_module("cybershield.alembic.env")

        # The module-level else-branch executed run_migrations_online() at
        # import time, which ran run_async_migrations() and disposed the engine.
        mock_connectable.dispose.assert_called()
        assert module.run_migrations_online is not None


# ---------------------------------------------------------------------------
# 3. dashboard/app.py — resume upload success + save settings branches
# ---------------------------------------------------------------------------

from cybershield.tests.test_dashboard_app import _ST, dashboard_app  # noqa: E402


class TestDashboardBranches:
    def test_show_resume_upload_success_branch(self, monkeypatch):
        """Lines 591-592: file uploaded -> success + analyze button."""
        _ST.calls.clear()
        monkeypatch.setattr(_ST, "file_uploader", lambda *a, **k: object())
        dashboard_app.show_resume()
        assert "success" in _ST.calls
        assert "button" in _ST.calls

    def test_show_settings_save_branch(self):
        """Line 674: Save Settings button pressed -> success."""
        _ST.values["💾 Save Settings"] = True
        _ST.calls.clear()
        dashboard_app.show_settings()
        assert "success" in _ST.calls
        _ST.values.pop("💾 Save Settings", None)


# ---------------------------------------------------------------------------
# 4. scrapers/usa/linkedin.py — line 82 (multiple ' in ' segments)
# ---------------------------------------------------------------------------


class TestLinkedInLocationBranch:
    def setup_method(self):
        self.scraper = LinkedInScraper()

    def test_company_name_when_multiple_in_segments(self):
        """'Engineer at Corp in City in Country' -> company kept whole."""
        entry = {
            "title": "Security Engineer at Example Corp in Bengaluru in India",
            "link": "https://www.linkedin.com/jobs/view/abc/1122334455",
            "summary": "SIEM and Python skills required.",
            "published": "2026-08-01T10:00:00Z",
        }
        job = self.scraper._parse_feed_entry(entry)
        assert job is not None
        assert job.title == "Security Engineer"
        assert job.company_name == "Example Corp in Bengaluru in India"
        assert job.location is None


# ---------------------------------------------------------------------------
# 5. interntrack/main.py — line 54 (RateLimitMiddleware when enabled)
# ---------------------------------------------------------------------------


class TestInterntrackMainRateLimitBranch:
    def test_rate_limit_middleware_registered_when_enabled(self, monkeypatch):
        import importlib as _il

        import interntrack.config as config_module
        import interntrack.main as main_module

        monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
        config_module.get_settings.cache_clear()
        try:
            _il.reload(main_module)
            names = [
                m.cls.__name__ if hasattr(m.cls, "__name__") else str(m.cls)
                for m in main_module.app.user_middleware
            ]
            assert "RateLimitMiddleware" in names
        finally:
            # Restore the canonical no-middleware module state for the suite.
            monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
            config_module.get_settings.cache_clear()
            _il.reload(main_module)


# ---------------------------------------------------------------------------
# 6. middleware/auth.py — line 49 (api_keys read from settings)
# ---------------------------------------------------------------------------


class TestAPIKeyMiddlewareSettingsBranch:
    def test_api_keys_from_settings_when_not_passed(self):
        settings_mock = type("Settings", (), {"api_keys": {"secret123"}})()
        with patch("cybershield.middleware.auth.get_settings", return_value=settings_mock):
            mw = APIKeyMiddleware(app=MagicMock())
        assert mw.api_keys == {"secret123"}


# ---------------------------------------------------------------------------
# 7. engines/base.py line 57 + base_company.py line 74 (abstract bodies)
# ---------------------------------------------------------------------------


class _ConcreteEngine(BaseEngine):
    async def process(self, data, **kwargs):
        return await super().process(data)  # type: ignore[safe-super]


class _ConcreteCompanyScraper(BaseCompanyScraper):
    async def scrape(self, **kwargs):
        return await super().scrape(**kwargs)  # type: ignore[safe-super]


class TestAbstractMethodBodies:
    @pytest.mark.asyncio
    async def test_engine_abstract_process_body(self):
        engine = _ConcreteEngine("test-engine")
        result = await engine.process({"data": 1})
        assert result is None  # the base 'pass' body

    @pytest.mark.asyncio
    async def test_company_scraper_abstract_scrape_body(self):
        scraper = _ConcreteCompanyScraper("Acme", "https://careers.acme.com")
        result = await scraper.scrape()
        assert result is None  # the base 'pass' body

    @pytest.mark.asyncio
    async def test_engine_result_to_dict(self):
        result = EngineResult(success=True, data={"x": 1}, errors=["e"], metadata={"m": 2})
        d = result.to_dict()
        assert d == {
            "success": True,
            "data": {"x": 1},
            "errors": ["e"],
            "metadata": {"m": 2},
        }


# ---------------------------------------------------------------------------
# 8. interntrack/api/v1/notifications.py — lines 29 & 33 (email + slack)
# ---------------------------------------------------------------------------


class TestInterntrackNotificationChannels:
    @pytest.mark.asyncio
    async def test_email_and_slack_channels_listed(self):
        from interntrack.api.v1.notifications import get_channels

        settings_mock = type(
            "Settings",
            (),
            {
                "is_telegram_configured": False,
                "is_email_configured": True,
                "is_discord_configured": False,
                "is_slack_configured": True,
            },
        )()
        with patch("interntrack.config.get_settings", return_value=settings_mock):
            resp = await get_channels()

        assert resp.channels == ["email", "slack"]
