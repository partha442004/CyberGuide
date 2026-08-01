"""
Unit tests for the request metrics store and the /metrics endpoint.
"""

import pytest
from httpx import AsyncClient

from interntrack.metrics import MetricsMiddleware, MetricsStore, metrics_store


class TestMetricsStore:
    """Tests for the in-memory MetricsStore counters."""

    def setup_method(self):
        self.store = MetricsStore()

    def test_starts_empty(self):
        snapshot = self.store.snapshot()
        assert snapshot["total_requests"] == 0
        assert snapshot["total_errors"] == 0
        assert snapshot["error_rate"] == 0.0
        assert snapshot["avg_latency_ms"] == 0.0
        assert snapshot["requests_per_path"] == {}
        assert snapshot["status_codes"] == {}

    def test_record_ok_request(self):
        self.store.record("/api/v1/jobs/", 200, 12.5)
        snapshot = self.store.snapshot()
        assert snapshot["total_requests"] == 1
        assert snapshot["total_errors"] == 0
        assert snapshot["error_rate"] == 0.0
        assert snapshot["avg_latency_ms"] == 12.5
        assert snapshot["requests_per_path"] == {"/api/v1/jobs/": 1}
        assert snapshot["status_codes"] == {"200": 1}

    def test_record_5xx_counts_as_error(self):
        self.store.record("/api/v1/boom", 500, 30.0)
        snapshot = self.store.snapshot()
        assert snapshot["total_errors"] == 1
        assert snapshot["error_rate"] == 1.0
        assert snapshot["errors_per_path"] == {"/api/v1/boom": 1}
        assert snapshot["status_codes"] == {"500": 1}

    def test_error_rate_mixes_ok_and_failures(self):
        self.store.record("/a", 200, 1.0)
        self.store.record("/b", 503, 2.0)
        self.store.record("/c", 200, 3.0)
        snapshot = self.store.snapshot()
        assert snapshot["total_requests"] == 3
        assert snapshot["total_errors"] == 1
        assert snapshot["error_rate"] == round(1 / 3, 6)
        assert snapshot["avg_latency_ms"] == 2.0
        assert snapshot["requests_per_path"] == {"/a": 1, "/b": 1, "/c": 1}

    def test_record_4xx_is_not_an_error(self):
        self.store.record("/missing", 404, 1.0)
        snapshot = self.store.snapshot()
        assert snapshot["total_errors"] == 0
        assert snapshot["status_codes"] == {"404": 1}

    def test_reset_clears_everything(self):
        self.store.record("/a", 200, 1.0)
        self.store.reset()
        snapshot = self.store.snapshot()
        assert snapshot["total_requests"] == 0
        assert snapshot["requests_per_path"] == {}
        assert snapshot["status_codes"] == {}


class TestMetricsMiddleware:
    """Tests for the MetricsMiddleware wiring and the /metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_snapshot(self, client: AsyncClient):
        """GET /metrics returns the metrics snapshot shape."""
        metrics_store.reset()
        response = await client.get("/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "error_rate" in data
        assert "avg_latency_ms" in data
        assert "requests_per_path" in data
        assert "status_codes" in data

    @pytest.mark.asyncio
    async def test_requests_are_recorded(self, client: AsyncClient):
        """Hitting a real endpoint increments the request counters."""
        metrics_store.reset()
        await client.get("/health")
        await client.get("/api/v1/jobs/")
        await client.get("/api/v1/does-not-exist")

        snapshot = metrics_store.snapshot()
        assert snapshot["total_requests"] == 3
        assert "/health" in snapshot["requests_per_path"]
        assert snapshot["status_codes"].get("200")
        assert snapshot["status_codes"].get("404")

    @pytest.mark.asyncio
    async def test_metrics_endpoint_not_recorded(self, client: AsyncClient):
        """The /metrics endpoint itself is exempt from recording."""
        metrics_store.reset()
        await client.get("/metrics")
        snapshot = metrics_store.snapshot()
        assert snapshot["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_middleware_exempt_paths_constant(self):
        """/metrics is in the middleware exempt set."""
        assert "/metrics" in MetricsMiddleware.EXEMPT_PATHS
