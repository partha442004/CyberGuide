"""
Request Metrics Middleware

Collects in-memory request metrics (counts, error rate, latency) exposed via
``GET /metrics`` (JSON for humans) and ``GET /metrics/prometheus`` (Prometheus
text exposition format for scrapers) for monitoring and alerting (see
TODO-CHECKLIST section 14).

The store is a lightweight in-memory counter keyed by request path and HTTP
status. It is deliberately dependency-free (no Prometheus client required) and
resets on process restart, which is fine for light monitoring.
"""

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware


class MetricsStore:
    """In-memory request metrics collector."""

    def __init__(self) -> None:
        self.total_requests = 0
        self.total_errors = 0
        self.total_latency_ms = 0.0
        self.path_counts: dict[str, int] = defaultdict(int)
        self.path_errors: dict[str, int] = defaultdict(int)
        self.status_counts: dict[int, int] = defaultdict(int)

    def record(self, path: str, status_code: int, duration_ms: float) -> None:
        """Record a single completed request."""
        self.total_requests += 1
        self.total_latency_ms += duration_ms
        self.path_counts[path] += 1
        self.status_counts[status_code] += 1
        if status_code >= 500:
            self.total_errors += 1
            self.path_errors[path] += 1

    def snapshot(self) -> dict:
        """Return a copy of the current metrics as a JSON-serializable dict."""
        avg_latency_ms = (
            self.total_latency_ms / self.total_requests if self.total_requests else 0.0
        )
        error_rate = (
            self.total_errors / self.total_requests if self.total_requests else 0.0
        )
        return {
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate": round(error_rate, 6),
            "avg_latency_ms": round(avg_latency_ms, 3),
            "requests_per_path": dict(self.path_counts),
            "errors_per_path": dict(self.path_errors),
            "status_codes": {str(k): v for k, v in sorted(self.status_counts.items())},
        }

    def reset(self) -> None:
        """Clear all collected metrics."""
        self.total_requests = 0
        self.total_errors = 0
        self.total_latency_ms = 0.0
        self.path_counts.clear()
        self.path_errors.clear()
        self.status_counts.clear()

    def render_prometheus(self) -> str:
        """Render the current metrics in Prometheus text exposition format.

        Dependency-free: emits the classic ``# HELP`` / ``# TYPE`` + sample
        lines that the Prometheus text format expects (see
        https://prometheus.io/docs/instrumenting/exposition_formats/) without
        pulling in ``prometheus_client``. Labels are escaped per the format
        (backslash, double-quote and newline).
        """
        avg_latency_ms = (
            self.total_latency_ms / self.total_requests if self.total_requests else 0.0
        )
        error_rate = (
            self.total_errors / self.total_requests if self.total_requests else 0.0
        )

        def escape_label(value: str) -> str:
            return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

        # The unlabeled totals overlap intentionally with the labeled families
        # (total == sum of *_by_path_total); keep them in sync when editing.
        lines: list[str] = [
            "# HELP interntrack_http_requests_total Total HTTP requests.",
            "# TYPE interntrack_http_requests_total counter",
            f"interntrack_http_requests_total {self.total_requests}",
            "# HELP interntrack_http_errors_total Total HTTP 5xx responses.",
            "# TYPE interntrack_http_errors_total counter",
            f"interntrack_http_errors_total {self.total_errors}",
            "# HELP interntrack_http_error_rate Fraction of requests with 5xx.",
            "# TYPE interntrack_http_error_rate gauge",
            f"interntrack_http_error_rate {error_rate}",
            "# HELP interntrack_http_request_duration_ms Average latency in ms.",
            "# TYPE interntrack_http_request_duration_ms gauge",
            f"interntrack_http_request_duration_ms {avg_latency_ms:.3f}",
        ]
        if self.path_counts:
            lines.append(
                "# HELP interntrack_http_requests_by_path_total "
                "Total HTTP requests per path.",
            )
            lines.append("# TYPE interntrack_http_requests_by_path_total counter")
            for path, count in sorted(self.path_counts.items()):
                path_label = escape_label(path)
                lines.append(
                    f'interntrack_http_requests_by_path_total{{path="{path_label}"}} '
                    f"{count}",
                )
        if self.path_errors:
            lines.append(
                "# HELP interntrack_http_errors_by_path_total "
                "Total HTTP 5xx responses per path.",
            )
            lines.append("# TYPE interntrack_http_errors_by_path_total counter")
            for path, count in sorted(self.path_errors.items()):
                path_label = escape_label(path)
                lines.append(
                    f'interntrack_http_errors_by_path_total{{path="{path_label}"}} '
                    f"{count}",
                )
        if self.status_counts:
            lines.append(
                "# HELP interntrack_http_requests_by_status_total "
                "Total HTTP requests per status.",
            )
            lines.append("# TYPE interntrack_http_requests_by_status_total counter")
            for status, count in sorted(self.status_counts.items()):
                lines.append(
                    f'interntrack_http_requests_by_status_total{{status="{status}"}} '
                    f"{count}",
                )
        return "\n".join(lines) + "\n"


# Global metrics store (one per process)
metrics_store = MetricsStore()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request count, status code, and latency for every request."""

    # Never record the metrics endpoints themselves to keep counters stable.
    EXEMPT_PATHS = {"/metrics", "/metrics/prometheus"}

    async def dispatch(self, request, call_next):
        """Process request, timing it and recording the outcome."""
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        metrics_store.record(request.url.path, response.status_code, duration_ms)
        return response
