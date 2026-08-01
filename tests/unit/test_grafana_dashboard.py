"""
Tests for the Grafana monitoring stack assets.

Validates that the provisioned dashboard JSON and datasource/dashboard provider
YAML are well-formed and that every PromQL expression references a metric the
API actually emits (``interntrack_http_*``), so the dashboard can never
silently drift from the code.
"""

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
DASHBOARD = ROOT / "deploy" / "grafana" / "dashboards" / "interntrack.json"
DATASOURCE = (
    ROOT / "deploy" / "grafana" / "provisioning" / "datasources" / "datasource.yml"
)
PROVIDER = (
    ROOT / "deploy" / "grafana" / "provisioning" / "dashboards" / "dashboards.yml"
)

# Metrics the API actually emits (see src/interntrack/metrics.py).
KNOWN_METRICS = {
    "interntrack_http_requests_total",
    "interntrack_http_errors_total",
    "interntrack_http_requests_by_path_total",
    "interntrack_http_errors_by_path_total",
    "interntrack_http_requests_by_status_total",
    "interntrack_http_error_rate",
    "interntrack_http_request_duration_ms",
}

_METRIC_RE = re.compile(r"\binterntrack_http_[a-z_]+")


class TestDashboardJson:
    """The dashboard JSON is valid and matches the emitted metrics."""

    @pytest.fixture
    def dashboard(self):
        data = json.loads(DASHBOARD.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        return data

    def test_assets_exist(self):
        """All provisioning assets are present on disk."""
        assert DASHBOARD.is_file()
        assert DATASOURCE.is_file()
        assert PROVIDER.is_file()

    def test_title_and_uid(self, dashboard):
        """The dashboard carries the expected identity."""
        assert dashboard["title"] == "InternTrack API"
        assert dashboard["uid"] == "interntrack-api"

    def test_has_panels(self, dashboard):
        """The dashboard defines panels and every one uses Prometheus."""
        panels = dashboard["panels"]
        assert len(panels) >= 4
        for panel in panels:
            assert panel["type"] in {"timeseries", "stat", "bargauge"}
            assert panel["datasource"]["type"] == "prometheus"

    def test_panel_expressions_use_real_metrics(self, dashboard):
        """Every PromQL expr references a metric the API actually emits."""
        exprs = []
        for panel in dashboard["panels"]:
            for target in panel.get("targets", []):
                exprs.append(target.get("expr", ""))

        assert exprs, "no PromQL expressions found in dashboard"
        for expr in exprs:
            for match in _METRIC_RE.findall(expr):
                assert match in KNOWN_METRICS, f"{match!r} is not an emitted metric"

    def test_refresh_interval(self, dashboard):
        """The dashboard auto-refreshes on the scrape cadence."""
        assert dashboard["refresh"] == "15s"

    def test_datasource_uid_matches_provisioning(self):
        """Dashboard datasource uid matches the provisioned datasource."""
        ds = yaml.safe_load(DATASOURCE.read_text(encoding="utf-8"))
        uid = ds["datasources"][0]["uid"]
        assert uid == "prometheus"

        data = json.loads(DASHBOARD.read_text(encoding="utf-8"))
        for panel in data["panels"]:
            assert panel["datasource"]["uid"] == uid


class TestProvisioningYaml:
    """The provisioning YAML is well-formed and points at Prometheus."""

    def test_datasource_points_at_prometheus_service(self):
        """The datasource targets the compose prometheus service."""
        ds = yaml.safe_load(DATASOURCE.read_text(encoding="utf-8"))
        datasource = ds["datasources"][0]
        assert datasource["type"] == "prometheus"
        assert datasource["url"] == "http://prometheus:9090"
        assert datasource["isDefault"] is True

    def test_dashboard_provider_loads_mounted_dir(self):
        """The provider config maps the mounted dashboards directory."""
        provider = yaml.safe_load(PROVIDER.read_text(encoding="utf-8"))
        options = provider["providers"][0]["options"]
        assert options["path"] == "/var/lib/grafana/dashboards"
