"""Tests for the business metrics store and its instrumentation (v1.19.0).

Covers:

- :class:`BusinessMetricsStore` counters (DB queries, scraper runs/failures,
  notification delivery/failures) + Prometheus rendering
- the instrumentation hooks: the SQLAlchemy cursor event listener in
  ``database/session.py``, ``ScraperRegistry.fetch_all`` success/failure
  recording, and ``NotificationManager.notify`` per-channel delivery
- the InternTrack Business Grafana dashboard: valid JSON, every panel on the
  ``prometheus`` datasource, every PromQL expr referencing a metric the API
  actually emits
"""

import json
import re
from pathlib import Path

import pytest

from interntrack.metrics import BusinessMetricsStore, business_metrics_store
from interntrack.scrapers.registry import ScraperRegistry
from interntrack.services.notification_service import NotificationManager

ROOT = Path(__file__).resolve().parents[2]
BUSINESS_DASHBOARD = ROOT / "deploy" / "grafana" / "dashboards" / "business.json"

# Metrics the API actually emits from BusinessMetricsStore.render_prometheus.
KNOWN_METRICS = {
    "interntrack_db_queries_total",
    "interntrack_db_query_duration_ms",
    "interntrack_scraper_runs_total",
    "interntrack_scraper_failures_total",
    "interntrack_notifications_total",
    "interntrack_notification_failures_total",
}
_METRIC_RE = re.compile(r"\binterntrack_(?:db|scraper|notification[a-z]*)_[a-z_]+")


@pytest.fixture(autouse=True)
def _clean_store():
    business_metrics_store.reset()
    yield
    business_metrics_store.reset()


class TestBusinessMetricsStore:
    def setup_method(self):
        self.store = BusinessMetricsStore()

    def test_starts_empty(self):
        snap = self.store.snapshot()
        assert snap["db_queries"] == 0
        assert snap["avg_db_query_ms"] == 0.0
        assert snap["scraper_runs"] == {}
        assert snap["scraper_failures"] == {}
        assert snap["notifications_sent"] == {}
        assert snap["notification_failures"] == {}

    def test_record_db_query_tracks_count_and_avg(self):
        self.store.record_db_query(10.0)
        self.store.record_db_query(30.0)
        snap = self.store.snapshot()
        assert snap["db_queries"] == 2
        assert snap["avg_db_query_ms"] == 20.0

    def test_record_scraper_run_success_and_failure(self):
        self.store.record_scraper_run("hackernews", success=True)
        self.store.record_scraper_run("hackernews", success=False)
        snap = self.store.snapshot()
        assert snap["scraper_runs"] == {"hackernews": 2}
        assert snap["scraper_failures"] == {"hackernews": 1}

    def test_record_notification_delivery_and_failure(self):
        self.store.record_notification("telegram", delivered=True)
        self.store.record_notification("telegram", delivered=False)
        snap = self.store.snapshot()
        assert snap["notifications_sent"] == {"telegram": 2}
        assert snap["notification_failures"] == {"telegram": 1}

    def test_render_prometheus_empty(self):
        text = self.store.render_prometheus()
        assert "# HELP interntrack_db_queries_total" in text
        assert "# TYPE interntrack_db_queries_total counter" in text
        assert "interntrack_db_queries_total 0" in text
        assert "interntrack_db_query_duration_ms 0.000" in text
        # labeled families absent when empty
        assert "interntrack_scraper_runs_total{" not in text
        assert "interntrack_notifications_total{" not in text

    def test_render_prometheus_recorded(self):
        self.store.record_db_query(5.0)
        self.store.record_scraper_run("remoteok", success=True)
        self.store.record_scraper_run("remoteok", success=False)
        self.store.record_notification("slack", delivered=True)
        self.store.record_notification("slack", delivered=False)
        text = self.store.render_prometheus()
        assert "interntrack_db_queries_total 1" in text
        assert "interntrack_db_query_duration_ms 5.000" in text
        assert 'interntrack_scraper_runs_total{source="remoteok"} 2' in text
        assert 'interntrack_scraper_failures_total{source="remoteok"} 1' in text
        assert 'interntrack_notifications_total{channel="slack"} 2' in text
        assert 'interntrack_notification_failures_total{channel="slack"} 1' in text

    def test_reset_clears(self):
        self.store.record_db_query(1.0)
        self.store.record_scraper_run("x", success=False)
        self.store.reset()
        snap = self.store.snapshot()
        assert snap["db_queries"] == 0
        assert snap["scraper_runs"] == {}
        assert snap["notification_failures"] == {}


class TestDbQueryListenerInstrumentation:
    @pytest.mark.asyncio
    async def test_listener_records_query_on_live_engine(self):
        """The SQLAlchemy event listener records real query durations.

        Installs the same listener helper used by ``database/session.py`` on a
        fresh in-memory engine, runs a query, and asserts the global store
        recorded it (regression guard for the event-signature wiring).
        """
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        from interntrack.database.session import install_db_query_metrics

        test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        install_db_query_metrics(test_engine.sync_engine)
        try:
            async with test_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            snap = business_metrics_store.snapshot()
            assert snap["db_queries"] >= 1
            assert snap["avg_db_query_ms"] >= 0.0
        finally:
            await test_engine.dispose()


class TestScraperRegistryInstrumentation:
    @pytest.mark.asyncio
    async def test_fetch_all_records_success_and_failure(self):
        class GoodScraper:
            source_name = "good"

            async def fetch(self, query, location=None, limit=100):
                return []

            async def close(self):
                pass

        class BadScraper:
            source_name = "bad"

            async def fetch(self, query, location=None, limit=100):
                raise RuntimeError("boom")

            async def close(self):
                pass

        registry = ScraperRegistry()
        registry.register(GoodScraper())
        registry.register(BadScraper())
        await registry.fetch_all("python")

        snap = business_metrics_store.snapshot()
        assert snap["scraper_runs"] == {"good": 1, "bad": 1}
        assert snap["scraper_failures"] == {"bad": 1}


class TestNotificationInstrumentation:
    @pytest.mark.asyncio
    async def test_notify_records_per_channel_delivery(self):
        class DummyManager(NotificationManager):
            def __init__(self):
                pass

        class FakeChannel:
            async def send(self, _message, _subject=None):
                return True

        manager = DummyManager()
        manager._channels = {"ok": FakeChannel(), "missing": None}
        results = await manager.notify(["ok", "missing"], "hi")

        assert results == {"ok": True, "missing": False}
        snap = business_metrics_store.snapshot()
        assert snap["notifications_sent"] == {"ok": 1, "missing": 1}
        assert snap["notification_failures"] == {"missing": 1}


class TestBusinessDashboard:
    def test_dashboard_exists_and_shape(self):
        dashboard = json.loads(BUSINESS_DASHBOARD.read_text(encoding="utf-8"))
        assert dashboard["title"] == "InternTrack Business"
        assert dashboard["uid"] == "interntrack-business"
        assert len(dashboard["panels"]) >= 3

    def test_all_panels_use_prometheus_datasource(self):
        dashboard = json.loads(BUSINESS_DASHBOARD.read_text(encoding="utf-8"))
        for panel in dashboard["panels"]:
            ds = panel.get("datasource") or {}
            assert ds.get("uid") == "prometheus"
            for target in panel.get("targets", []):
                assert target["datasource"]["uid"] == "prometheus"

    def test_expressions_reference_emitted_metrics(self):
        dashboard = json.loads(BUSINESS_DASHBOARD.read_text(encoding="utf-8"))
        exprs = [t["expr"] for p in dashboard["panels"] for t in p["targets"]]
        assert exprs
        for expr in exprs:
            matches = set(_METRIC_RE.findall(expr))
            assert matches, f"no interntrack metric in expr: {expr}"
            for match in matches:
                assert match in KNOWN_METRICS, f"{match!r} is not an emitted metric"
