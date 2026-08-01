"""Tests for the Loki + Promtail log monitoring stack (v1.18.0).

These pin the log-monitoring assets to each other so the stack cannot drift:

- ``loki-config.yml`` stays a valid single-binary Loki config
- ``promtail-config.yml`` actually ships to ``loki:3100`` and discovers
  containers via the Docker socket
- docker-compose declares the ``loki`` + ``promtail`` services (monitoring profile)
- Grafana provisioning declares the ``loki`` datasource
- the InternTrack Logs dashboard is valid JSON and every panel expression is
  valid LogQL targeting the ``loki`` datasource
"""

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
LOKI_CONFIG = ROOT / "deploy" / "loki" / "loki-config.yml"
PROMTAIL_CONFIG = ROOT / "deploy" / "loki" / "promtail-config.yml"
DATASOURCES = (
    ROOT / "deploy" / "grafana" / "provisioning" / "datasources" / "datasource.yml"
)
LOGS_DASHBOARD = ROOT / "deploy" / "grafana" / "dashboards" / "logs.json"
COMPOSE = ROOT / "docker-compose.yml"


@pytest.fixture(scope="module")
def loki_config() -> dict:
    return yaml.safe_load(LOKI_CONFIG.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def promtail_config() -> dict:
    return yaml.safe_load(PROMTAIL_CONFIG.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def datasources() -> dict:
    return yaml.safe_load(DATASOURCES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def logs_dashboard() -> dict:
    return json.loads(LOGS_DASHBOARD.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_assets_exist() -> None:
    for asset in (LOKI_CONFIG, PROMTAIL_CONFIG, DATASOURCES, LOGS_DASHBOARD, COMPOSE):
        assert asset.is_file(), f"missing asset: {asset}"


def test_loki_config_has_single_binary_layout(loki_config: dict) -> None:
    assert loki_config["auth_enabled"] is False
    assert loki_config["server"]["http_listen_port"] == 3100
    chunks = loki_config["common"]["storage"]["filesystem"]["chunks_directory"]
    assert chunks == "/loki/chunks"
    assert loki_config["schema_config"]["configs"][0]["schema"] == "v13"
    assert loki_config["schema_config"]["configs"][0]["store"] == "tsdb"
    assert loki_config["limits_config"]["retention_period"] == "336h"


def test_promtail_ships_to_loki(promtail_config: dict) -> None:
    clients = promtail_config["clients"]
    assert clients, "promtail must declare at least one client"
    urls = [c["url"] for c in clients]
    assert all(u.startswith("http://loki:3100/") for u in urls)


def test_promtail_discovers_docker_socket(promtail_config: dict) -> None:
    scrape_jobs = {j["job_name"]: j for j in promtail_config["scrape_configs"]}
    assert "docker" in scrape_jobs
    sd = scrape_jobs["docker"]["docker_sd_configs"]
    assert sd
    assert sd[0]["host"] == "unix:///var/run/docker.sock"
    # The app emits structlog JSON keyed `timestamp`; that field must be parsed
    # so Loki uses the real log time instead of receive time.
    stages = scrape_jobs["docker"]["pipeline_stages"]
    assert any("timestamp" in stage for stage in stages)
    # compose_service relabel must exist so the dashboard's service template works.
    relabels = [
        r.get("target_label") for r in scrape_jobs["docker"].get("relabel_configs", [])
    ]
    assert "compose_service" in relabels
    assert "stream" in relabels


def test_compose_declares_loki_and_promtail(compose: dict) -> None:
    services = compose["services"]
    for name in ("loki", "promtail"):
        assert name in services, f"missing compose service: {name}"
        assert "monitoring" in services[name]["profiles"]
    assert "loki_data" in compose["volumes"]
    # promtail must wait for loki to be reachable.
    assert "loki" in services["promtail"].get("depends_on", [])
    # the compose mounts must match the -config.file flags
    assert "/etc/loki/loki-config.yml" in services["loki"]["volumes"][0]
    assert "/etc/promtail/promtail-config.yml" in services["promtail"]["volumes"][0]
    # promtail needs the docker socket to discover containers.
    assert "/var/run/docker.sock" in services["promtail"]["volumes"][1]


def test_grafana_provisioning_has_loki_datasource(datasources: dict) -> None:
    uids = {d["uid"] for d in datasources["datasources"]}
    assert "loki" in uids
    loki = next(d for d in datasources["datasources"] if d["uid"] == "loki")
    assert loki["type"] == "loki"
    assert loki["url"] == "http://loki:3100"


def test_logs_dashboard_title_and_uid(logs_dashboard: dict) -> None:
    assert logs_dashboard["title"] == "InternTrack Logs"
    assert logs_dashboard["uid"] == "interntrack-logs"
    assert len(logs_dashboard["panels"]) >= 3


def test_all_panels_use_loki_datasource(logs_dashboard: dict) -> None:
    for panel in logs_dashboard["panels"]:
        ds = panel.get("datasource") or {}
        assert ds.get("uid") == "loki", (
            f"panel {panel.get('id')} not on loki datasource"
        )
        for target in panel.get("targets", []):
            assert target["datasource"]["uid"] == "loki"


def test_logql_expressions_are_valid(logs_dashboard: dict) -> None:
    """Every LogQL expression must be a stream selector query.

    Range/instant queries must start with a ``{...}`` selector or a valid Loki
    aggregation (sum / topk) and reference the ``docker`` scrape job.
    """
    exprs = [t["expr"] for p in logs_dashboard["panels"] for t in p["targets"]]
    assert exprs
    for expr in exprs:
        starts_ok = expr.startswith(("{", "sum", "topk"))
        assert starts_ok, f"unexpected expr start: {expr}"
        assert 'job="docker"' in expr, f"missing stream selector: {expr}"


def test_templating_uses_loki_label_values(logs_dashboard: dict) -> None:
    variables = logs_dashboard["templating"]["list"]
    assert variables, "dashboard must declare a service template variable"
    service = next(v for v in variables if v["name"] == "service")
    assert service["datasource"]["uid"] == "loki"
    assert "label_values(compose_service)" in service["definition"]
