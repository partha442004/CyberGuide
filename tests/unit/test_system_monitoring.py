"""
Tests for the node-exporter / host system monitoring stack.

Validates that the node-exporter service is wired into docker-compose and the
Prometheus scrape config, that the ``system`` alert group targets real
node-exporter metrics, and that the Grafana system dashboard's PromQL
expressions reference the same ``node_*`` metrics — so the monitoring assets
can never silently drift from the exporter they scrape.
"""

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSE = ROOT / "docker-compose.yml"
PROMETHEUS = ROOT / "deploy" / "prometheus" / "prometheus.yml"
ALERTS = ROOT / "deploy" / "prometheus" / "alerts.yml"
SYSTEM_DASHBOARD = ROOT / "deploy" / "grafana" / "dashboards" / "system.json"

# Metrics the node-exporter actually emits (v1.x).
NODE_METRICS = {
    "node_cpu_seconds_total",
    "node_memory_MemAvailable_bytes",
    "node_memory_MemTotal_bytes",
    "node_filesystem_avail_bytes",
    "node_filesystem_size_bytes",
    "node_network_receive_bytes_total",
    "node_network_transmit_bytes_total",
    "node_load1",
}

_METRIC_RE = re.compile(r"\bnode_[a-z_A-Z0-9]+")
SYSTEM_RULES = {"DiskSpaceLow", "MemoryHigh", "CpuHigh"}


class TestNodeExporterWiring:
    """node-exporter is wired into compose and the scrape config."""

    def test_compose_has_node_exporter_service(self):
        """docker-compose defines the node-exporter service behind monitoring."""
        compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
        service = compose["services"]["node-exporter"]
        assert service["image"].startswith("prom/node-exporter:")
        assert "9100:9100" in service["ports"]
        assert "monitoring" in service["profiles"]

    def test_scrape_config_targets_node_exporter(self):
        """Prometheus scrapes the node-exporter service on port 9100."""
        config = yaml.safe_load(PROMETHEUS.read_text(encoding="utf-8"))
        jobs = {job["job_name"]: job for job in config["scrape_configs"]}
        assert "node-exporter" in jobs
        targets = jobs["node-exporter"]["static_configs"][0]["targets"]
        assert "node-exporter:9100" in targets


class TestSystemAlerts:
    """The system alert group targets real node-exporter metrics."""

    @pytest.fixture
    def rules(self):
        data = yaml.safe_load(ALERTS.read_text(encoding="utf-8"))
        groups = {group["name"]: group for group in data["groups"]}
        assert "system" in groups
        return groups["system"]["rules"]

    def test_system_group_present(self, rules):
        """The system group declares the expected alerts."""
        names = {rule.get("alert") for rule in rules}
        assert names >= SYSTEM_RULES

    def test_expressions_use_node_metrics(self, rules):
        """Every PromQL expr references a real node-exporter metric."""
        for rule in rules:
            expr = rule["expr"]
            for match in _METRIC_RE.findall(expr):
                assert match in NODE_METRICS, f"{match!r} is not a node metric"


class TestSystemDashboard:
    """The system dashboard JSON is valid and matches node metrics."""

    @pytest.fixture
    def dashboard(self):
        data = json.loads(SYSTEM_DASHBOARD.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        return data

    def test_title_and_uid(self, dashboard):
        """The dashboard carries the expected identity."""
        assert dashboard["title"] == "InternTrack System"
        assert dashboard["uid"] == "interntrack-system"

    def test_panels_use_prometheus(self, dashboard):
        """Every panel targets the provisioned Prometheus datasource."""
        for panel in dashboard["panels"]:
            assert panel["datasource"]["uid"] == "prometheus"

    def test_expressions_use_node_metrics(self, dashboard):
        """Every PromQL expr references a real node-exporter metric."""
        exprs = []
        for panel in dashboard["panels"]:
            for target in panel.get("targets", []):
                exprs.append(target.get("expr", ""))
        assert exprs, "no PromQL expressions found in system dashboard"
        for expr in exprs:
            for match in _METRIC_RE.findall(expr):
                assert match in NODE_METRICS, f"{match!r} is not a node metric"
