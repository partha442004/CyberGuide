"""
Tests for the Prometheus alerting rules.

Validates that ``deploy/prometheus/alerts.yml`` is well-formed, declares the
expected rules, and that every PromQL expression references a metric the API
actually emits (``interntrack_http_*``) — so the alert rules can never
silently drift from the code. Also verifies the rules are wired into
``prometheus.yml`` (``rule_files``) and the docker-compose prometheus service.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
ALERTS = ROOT / "deploy" / "prometheus" / "alerts.yml"
PROMETHEUS = ROOT / "deploy" / "prometheus" / "prometheus.yml"
COMPOSE = ROOT / "docker-compose.yml"

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
EXPECTED_RULES = {"HighErrorRate", "HighLatency", "ServiceDown"}


class TestAlertRules:
    """The alerting rules file is valid and matches the emitted metrics."""

    @pytest.fixture
    def groups(self):
        data = yaml.safe_load(ALERTS.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "groups" in data
        return data["groups"]

    @pytest.fixture
    def rules(self, groups):
        return [rule for group in groups for rule in group.get("rules", [])]

    def test_alerts_file_exists(self):
        """The alerts file is present on disk."""
        assert ALERTS.is_file()

    def test_yaml_valid(self, groups):
        """The alerts file parses and contains at least one group."""
        assert len(groups) >= 1

    def test_expected_rules_present(self, rules):
        """The documented rule names are all declared."""
        names = {rule.get("alert") for rule in rules}
        assert names >= EXPECTED_RULES

    def test_every_rule_has_expr_and_for(self, rules):
        """Each rule has an expression and a duration before firing."""
        for rule in rules:
            assert rule.get("expr"), f"rule {rule.get('alert')} missing expr"
            assert rule.get("for"), f"rule {rule.get('alert')} missing for"

    def test_expressions_use_real_metrics(self, rules):
        """Every PromQL expr references a metric the API actually emits."""
        exprs = [rule["expr"] for rule in rules]
        assert exprs, "no rule expressions found"
        for expr in exprs:
            for match in _METRIC_RE.findall(expr):
                assert match in KNOWN_METRICS, f"{match!r} is not an emitted metric"

    def test_service_down_uses_up_metric(self, rules):
        """ServiceDown fires on the scrape target being absent."""
        service_down = next(r for r in rules if r["alert"] == "ServiceDown")
        assert service_down["expr"] == 'up{job="interntrack-api"} == 0'


class TestAlertWiring:
    """The rules are wired into prometheus.yml and docker-compose."""

    def test_rule_files_declared(self):
        """prometheus.yml loads the alerts file via rule_files."""
        config = yaml.safe_load(PROMETHEUS.read_text(encoding="utf-8"))
        assert "alerts.yml" in config["rule_files"]

    def test_compose_mounts_alerts(self):
        """The prometheus compose service mounts the alerts file read-only."""
        compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
        prometheus = compose["services"]["prometheus"]
        assert "alerts.yml" in " ".join(prometheus["volumes"])
