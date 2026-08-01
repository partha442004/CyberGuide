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


class BusinessMetricsStore:
    """In-memory business metrics collector.

    Tracks the non-HTTP signals the monitoring dashboards surface: database
    query times, scraper success/failure rates per source, and notification
    delivery/failure rates per channel. Dependency-free, same pattern as
    :class:`MetricsStore`; resets on process restart.
    """

    def __init__(self) -> None:
        self.db_queries = 0
        self.db_query_total_ms = 0.0
        self.scraper_runs: dict[str, int] = defaultdict(int)
        self.scraper_failures: dict[str, int] = defaultdict(int)
        self.notifications_sent: dict[str, int] = defaultdict(int)
        self.notification_failures: dict[str, int] = defaultdict(int)

    def record_db_query(self, duration_ms: float) -> None:
        """Record one completed database query and its duration."""
        self.db_queries += 1
        self.db_query_total_ms += duration_ms

    def record_scraper_run(self, source: str, success: bool) -> None:
        """Record one scraper run outcome for a given source."""
        self.scraper_runs[source] += 1
        if not success:
            self.scraper_failures[source] += 1

    def record_notification(self, channel: str, delivered: bool) -> None:
        """Record one notification delivery outcome for a given channel."""
        self.notifications_sent[channel] += 1
        if not delivered:
            self.notification_failures[channel] += 1

    def snapshot(self) -> dict:
        """Return a JSON-serializable snapshot of business metrics."""
        avg_db_ms = self.db_query_total_ms / self.db_queries if self.db_queries else 0.0
        return {
            "db_queries": self.db_queries,
            "avg_db_query_ms": round(avg_db_ms, 3),
            "scraper_runs": dict(self.scraper_runs),
            "scraper_failures": dict(self.scraper_failures),
            "notifications_sent": dict(self.notifications_sent),
            "notification_failures": dict(self.notification_failures),
        }

    def reset(self) -> None:
        """Clear all collected business metrics."""
        self.db_queries = 0
        self.db_query_total_ms = 0.0
        self.scraper_runs.clear()
        self.scraper_failures.clear()
        self.notifications_sent.clear()
        self.notification_failures.clear()

    def render_prometheus(self) -> str:
        """Render business metrics in Prometheus text exposition format."""
        avg_db_ms = self.db_query_total_ms / self.db_queries if self.db_queries else 0.0

        def escape_label(value: str) -> str:
            return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

        lines: list[str] = [
            "# HELP interntrack_db_queries_total Total database queries executed.",
            "# TYPE interntrack_db_queries_total counter",
            f"interntrack_db_queries_total {self.db_queries}",
            (
                "# HELP interntrack_db_query_duration_ms "
                "Average database query time in ms."
            ),
            "# TYPE interntrack_db_query_duration_ms gauge",
            f"interntrack_db_query_duration_ms {avg_db_ms:.3f}",
        ]
        if self.scraper_runs:
            lines.append(
                "# HELP interntrack_scraper_runs_total Total scraper runs per source.",
            )
            lines.append("# TYPE interntrack_scraper_runs_total counter")
            for source, count in sorted(self.scraper_runs.items()):
                src = escape_label(source)
                lines.append(
                    f'interntrack_scraper_runs_total{{source="{src}"}} {count}',
                )
        if self.scraper_failures:
            lines.append(
                "# HELP interntrack_scraper_failures_total "
                "Failed scraper runs per source.",
            )
            lines.append("# TYPE interntrack_scraper_failures_total counter")
            for source, count in sorted(self.scraper_failures.items()):
                src = escape_label(source)
                lines.append(
                    f'interntrack_scraper_failures_total{{source="{src}"}} {count}',
                )
        if self.notifications_sent:
            lines.append(
                "# HELP interntrack_notifications_total "
                "Notifications delivered per channel.",
            )
            lines.append("# TYPE interntrack_notifications_total counter")
            for channel, count in sorted(self.notifications_sent.items()):
                ch = escape_label(channel)
                lines.append(
                    f'interntrack_notifications_total{{channel="{ch}"}} {count}',
                )
        if self.notification_failures:
            lines.append(
                "# HELP interntrack_notification_failures_total "
                "Failed notifications per channel.",
            )
            lines.append("# TYPE interntrack_notification_failures_total counter")
            for channel, count in sorted(self.notification_failures.items()):
                ch = escape_label(channel)
                sample = (
                    f'interntrack_notification_failures_total{{channel="{ch}"}} {count}'
                )
                lines.append(sample)
        return "\n".join(lines) + "\n"


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


# Global metrics stores (one per process)
metrics_store = MetricsStore()
business_metrics_store = BusinessMetricsStore()


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
