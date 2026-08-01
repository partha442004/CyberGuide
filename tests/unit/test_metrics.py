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


class TestRenderPrometheus:
    """Tests for the dependency-free Prometheus text exposition renderer."""

    def setup_method(self):
        self.store = MetricsStore()

    def test_empty_store_emits_help_and_zero_samples(self):
        """Empty store still emits HELP/TYPE headers with zero counters."""
        text = self.store.render_prometheus()
        assert text.endswith("\n")
        assert "# HELP interntrack_http_requests_total Total HTTP requests." in text
        assert "# TYPE interntrack_http_requests_total counter" in text
        assert "interntrack_http_requests_total 0" in text
        assert "interntrack_http_errors_total 0" in text
        assert "interntrack_http_error_rate 0.0" in text

    def test_renders_recorded_samples(self):
        """Recorded requests appear as labeled samples."""
        self.store.record("/api/v1/jobs/", 200, 10.0)
        self.store.record("/api/v1/boom", 500, 20.0)
        text = self.store.render_prometheus()
        assert "interntrack_http_requests_total 2" in text
        assert "interntrack_http_errors_total 1" in text
        assert 'interntrack_http_requests_by_path_total{path="/api/v1/jobs/"} 1' in text
        assert 'interntrack_http_requests_by_path_total{path="/api/v1/boom"} 1' in text
        assert 'interntrack_http_errors_by_path_total{path="/api/v1/boom"} 1' in text
        assert 'interntrack_http_requests_by_status_total{status="200"} 1' in text
        assert 'interntrack_http_requests_by_status_total{status="500"} 1' in text

    def test_escapes_label_values(self):
        """Label values escape backslash, double-quote and newline."""
        self.store.record("/weird\\path", 200, 1.0)
        self.store.record('/with"quote', 200, 1.0)
        self.store.record("/with\nnewline", 200, 1.0)
        text = self.store.render_prometheus()
        assert 'path="/weird\\\\path"' in text
        assert 'path="/with\\"quote"' in text
        assert 'path="/with\\nnewline"' in text


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
        # business metrics (DB / scrapers / notifications) ride on /metrics too
        assert "business" in data

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
    async def test_prometheus_endpoint_returns_text_format(self, client: AsyncClient):
        """GET /metrics/prometheus returns Prometheus text exposition format."""
        metrics_store.reset()
        response = await client.get("/metrics/prometheus")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        text = response.text
        assert "# HELP interntrack_http_requests_total" in text
        assert "# TYPE interntrack_http_requests_total counter" in text
        assert "interntrack_http_requests_total 0" in text

    @pytest.mark.asyncio
    async def test_prometheus_reflects_recorded_requests(self, client: AsyncClient):
        """The Prometheus output reflects requests recorded so far."""
        metrics_store.reset()
        await client.get("/health")
        await client.get("/api/v1/jobs/")
        text = (await client.get("/metrics/prometheus")).text
        assert "interntrack_http_requests_total 2" in text
        assert 'interntrack_http_requests_by_path_total{path="/health"} 1' in text
        assert 'interntrack_http_requests_by_path_total{path="/api/v1/jobs/"} 1' in text

    @pytest.mark.asyncio
    async def test_prometheus_endpoint_not_recorded(self, client: AsyncClient):
        """The /metrics/prometheus endpoint itself is exempt from recording."""
        metrics_store.reset()
        await client.get("/metrics/prometheus")
        snapshot = metrics_store.snapshot()
        assert snapshot["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_middleware_exempt_paths_constant(self):
        """/metrics and /metrics/prometheus are in the middleware exempt set."""
        assert "/metrics" in MetricsMiddleware.EXEMPT_PATHS
        assert "/metrics/prometheus" in MetricsMiddleware.EXEMPT_PATHS
