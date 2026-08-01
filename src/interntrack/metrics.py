"""
Request Metrics Middleware

Collects in-memory request metrics (counts, error rate, latency) exposed via
``GET /metrics`` for monitoring and alerting (see TODO-CHECKLIST section 14).

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


# Global metrics store (one per process)
metrics_store = MetricsStore()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request count, status code, and latency for every request."""

    # Never record the metrics endpoint itself to keep its counters stable.
    EXEMPT_PATHS = {"/metrics"}

    async def dispatch(self, request, call_next):
        """Process request, timing it and recording the outcome."""
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        metrics_store.record(request.url.path, response.status_code, duration_ms)
        return response
