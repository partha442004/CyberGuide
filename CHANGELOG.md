# Changelog

All notable changes to the InternTrack project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.20.0] - 2026-08-02

### Added

#### CyberGuide Coverage Push (notifications / auth / session / repositories)
- `test_notifications_channels.py` (26 tests) — `DiscordNotifier`,
  `SlackNotifier`, `TelegramNotifier`: embed / Block Kit / message building
  (priority colors, URL + data fields, truncation limits), send success &
  failure paths, `test_connection`, and the no-config / exception fallbacks —
  all against a fake `httpx.AsyncClient` (no network)
- `test_api_key_middleware.py` (7 tests) — `APIKeyMiddleware`: exempt paths,
  missing key → 401 `MISSING_API_KEY`, invalid key → 403 `INVALID_API_KEY`,
  valid key sets `request.state.api_key`, custom header name, and open mode
  (no keys). An autouse fixture patches `get_settings` so open-mode behavior
  is deterministic regardless of ambient `API_KEYS` env vars (Starlette
  instantiates middleware lazily on the first request)
- `test_database_session.py` (10 tests) — engine kwargs (SQLite vs
  PostgreSQL pooling), lazy `get_engine`/`get_session_factory` caching,
  `init_db` side-effect assertion (tables exist in the SQLite file),
  `close_db`, `get_db_session` commit/rollback, and `get_db` yield; module
  globals reset per test and engines disposed on teardown
- `test_repositories.py` (22 tests) — `BaseRepository` CRUD (create with
  generated/provided ids, get, get_or_raise → `NotFoundError`, get_all with
  pagination/filters/list-IN, count, update, delete, exists, search) and
  `CompanyRepository` (get_by_name, get_or_create_by_name, get_with_jobs,
  search_companies, get_top_hiring_companies, get_trusted_companies,
  update_trust_status) against the in-memory-SQLite `db_session` fixture

#### Smoke Script Windows Cleanup
- `scripts/smoke_test.py` finally-block now retries the temp DB/log unlink
  (5 attempts, 200ms apart) — the aiosqlite worker thread can briefly hold
  the file after the server exits on Windows; CI (Ubuntu) is unaffected but
  local `make smoke` on Windows is now reliable

#### CyberGuide Coverage Push (orchestrator / websocket / repositories)
- `test_notifications_orchestrator.py` (24 tests) — channel
  register/unregister/list, single / multi / all sends with enabled +
  exclusion semantics, job-alert / scam-alert / daily-digest / weekly-report
  message builders, formatting fallbacks, send stats, and
  `create_default_orchestrator` — all against fake channels (no network)
- `test_notifications_base.py` (11 tests) — `BaseNotifier` enable/disable,
  `send_safe` success / failure / disabled / exception paths, and the
  job-alert + daily-digest formatters via a concrete test notifier
- `test_websocket_endpoint.py` (8 tests) — `api/v1/websocket.py` endpoint
  through a `FakeWebSocket` that raises `WebSocketDisconnect` on queue
  exhaustion: welcome message, ping→pong, subscribe/unsubscribe (room
  membership), rooms listing, unknown message type, invalid JSON, and
  disconnect cleanup
- `test_repositories_extended.py` (25 tests) — `JobRepository` (search,
  get_high_scam_risk, mark_duplicates, pagination), `SkillRepository`
  (user skills add/list/remove, get_or_create, search), `UserRepository`
  (create, get_by_email, get_by_username), `ApplicationRepository`
  (get_application_metrics, status transitions) against the
  in-memory-SQLite `db_session` fixture

### Fixed
- `SkillRepository.add_user_skill` could raise an `IntegrityError` (500) when
  the skill name had not been seen before — `Skill.category` is NOT NULL.
  New skills now default to `category="general"`.

#### Railway.app hosted deployment (no credit card)
- Deployment target pivoted to **Railway.app** (`railway.toml` refined): Nixpacks
  build, `alembic upgrade head && uvicorn ... --port $PORT` start command,
  `/health` healthcheck, `PYTHONPATH=src`, `APP_VERSION=1.20.0`, `DEBUG=false`
- The Railway **Postgres plugin** auto-injects `DATABASE_URL` (migrations run
  automatically on every deploy); Redis is optional (the app falls back to
  in-memory rate-limit/cache stores); `SECRET_KEY` placeholder documented to be
  overridden in the Railway dashboard
- New `deploy/railway/RAILWAY-DEPLOY.md` — signup → connect repo → add
  Postgres → set variables → troubleshooting; no credit card required (Oracle
  Cloud asks for a card at signup)
- Oracle Cloud SSH deploy (`cd.yml` deploy job) remains as the self-hosted
  option and self-skips until server secrets are added

#### Continuous Deployment (v1.20.0 tag)
- `DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN` secrets configured in the repo;
  CD image namespace corrected to `kira2004/cybershield` (was
  `cybershield/cybershield`, which could never push)
- The deploy job's `if` was rewritten: the `secrets` context is not valid in
  `if` conditionals (`Unrecognized named-value: 'secrets'` — GitHub rejects it
  at both job and step level), so a tiny shell step reads the server secrets
  as env vars and emits `configured=true|false`; the SSH deploy step runs only
  when `steps.check.outputs.configured == 'true'`
- CD verified end-to-end on the `v1.20.0` tag: **Build & push Docker image ✓**
  (image live on Docker Hub: `kira2004/cybershield` tags `1.20.0` / `1.20` /
  `latest` / `sha-aed7427`), **Deploy to server ✓** (skipped gracefully —
  `SERVER_HOST` / `SERVER_USER` / `SSH_PRIVATE_KEY` not configured yet; add
  them to GitHub → Settings → Secrets → Actions to enable auto-deploy)

### Changed
- **Full suite: 1421 passed** (924 InternTrack + 497 CyberGuide; was 1353);
  combined coverage **83%** (12,037 lines; was 80% / 11,461 lines)
- Coverage gains (round 2): `notifications/orchestrator.py` 27% → **98%**,
  `notifications/base.py` 55% → **99%**, `api/v1/websocket.py` 20% → **92%**,
  `application_repository.py` 42% → **100%**, `user_repository.py`
  62% → **100%**, `job_repository.py` 50% → **96%**, `skill_repository.py`
  50% → **93%**
- Coverage gains (round 1): `database/session.py` 31% → **100%**,
  `middleware/auth.py` 30% → **97%**, discord 25% → **100%**, slack
  31% → **100%**, telegram 31% → **100%**, `repositories/base.py`
  37% → **97%**, `company_repository.py` 39% → **100%**
- Version bumped to **1.20.0** across both packages, `.env`/`.env.example`,
  root `pyproject.toml`, Helm chart, Oracle deploy files, dashboard
  `DEFAULT_VERSION`, docs, and version canaries — `make version-check` exit 0
- README badges refreshed: 1421 tests, 83% coverage

## [2026-08-02] — CI test-job fix + entry-point coverage push

### Fixed

#### CI Tests job failure: `unable to open database file` (Linux runner)
- The Tests (pytest) job failed on the Ubuntu runner with 26 failures in
  `tests/unit/test_api_v1_full.py`, all `sqlite3.OperationalError: unable to
  open database file`. Root cause (confirmed from the job log via `gh run
  view --log`): that file defined its **own** local `client` fixture —
  `TestClient(app)` against the real app — so requests hit the real
  `DATABASE_URL` (`sqlite+aiosqlite:///./data/interntrack.db`). The `data/`
  directory is gitignored and absent on the fresh CI runner, so SQLite could
  not open the DB file. It passed locally only because `data/` exists on the
  dev machine. This was unrelated to the previously-fixed pytest-asyncio
  event-loop flakiness.
- Fix: the local `client` fixture now builds a **hermetic temp-file SQLite
  DB** (`tmp_path`), creates tables via `Base.metadata.create_all`, overrides
  the `get_db` dependency on the app, and swaps
  `interntrack.database.session.async_session_factory` for the test factory;
  the fixture restores both in `finally` and disposes the async engine so no
  connection leaks across loops. The app's real `./data` DB is never touched.
- Verification: `test_api_v1_full.py` passes (32 tests) in the exact CI
  environment (Python 3.11.9 + pytest-asyncio 1.4.0), and the full suite
  passes with the `data/` scenario removed from the equation entirely.

### Added

#### Entry-point module tests (CyberGuide, previously 0% coverage)
- `src/cybershield/tests/test_start_script.py` — `start.py` launcher
  (`start_api`/`start_dashboard`/`start_scheduler`/`main`) with mocked
  `subprocess.Popen`, including Ctrl-C shutdown and process-exit handling;
  `sys.exit` patched with `side_effect=SystemExit` so tests terminate
  deterministically (no real subprocesses / infinite loops)
- `src/cybershield/tests/test_check_routes.py` — route-listing script runs
  via `runpy` and prints the OpenAPI path summary; asserts non-empty,
  versioned paths with lowercase HTTP methods
- `src/cybershield/tests/test_scheduler_main.py` — scheduler entry point
  `create_scheduler` (job ids, trigger types), `main` argument handling and
  guard, plus the discovery/job functions with mocked `ScraperRegistry` and
  error-path coverage; avoids `shutdown()` on a never-started
  `AsyncIOScheduler` (raises `SchedulerNotRunningError`)
- `src/cybershield/tests/test_dashboard_app.py` — Streamlit dashboard entry
  point exercised with injected fake `streamlit`/`plotly` modules (persistent
  `sys.modules` fakes, no streamlit dependency in the backend suite): page
  routing to each of the 13 renderers, default-page selection, and one
  smoke test per `show_*` renderer (renders without raising and calls
  streamlit)
- Resulting coverage (previously 0%): `start.py` → **98%**,
  `check_routes.py` → **100%**, `dashboard/app.py` → **99%**,
  `scheduler/__main__.py` → **50%**

### Changed
- Full suite (exact CI command, Python 3.11.9 + pytest-asyncio 1.4.0):
  **1288 passed, 0 failed** (was 1247); combined coverage (interntrack +
  cybershield) **77%** (10,944 lines) — up from 72.1% (10,619 lines)
- Validation clean: ruff check + format (CI scope `src/ tests/ dashboard/`),
  mypy (186 files, `warn_unused_ignores` clean), `scripts/check_versions.py`
  exit 0 (all sources 1.19.0)
- README badges refreshed: tests 1247 → **1288 passed**, coverage 67% → **77%**
- Docs re-synced to the new numbers: PROJECT-STATUS.md, PROJECT-PROGRESS.md,
  TODO-CHECKLIST.md (new HARDENING PASS 18 entry), src/cybershield/PROGRESS.md
  (323 → 364 tests + entry-point coverage table), docs/cscip/17-cicd.md
  (1247 → 1288 tests)

## [Merged] - 2026-08-01 — origin/master reconciled into local master

### Fixed

#### CI Pipeline (GitHub Actions)
- **trivy-action tag**: `aquasecurity/trivy-action@0.30.0` → `@v0.30.0`
  (Actions resolves action refs to exact tags; the upstream repo only
  publishes `v`-prefixed tags, so the Security job could not resolve the
  action at all)
- **mypy version drift**: `requirements-dev.txt` `mypy>=1.7.0` →
  `mypy>=1.20,<2`. CI installs mypy fresh, which had resolved to the newly
  released major version **2.3.0** and broke the `warn_unused_ignores`
  typecheck build. Pinning to the validated 1.x line (resolves to 1.20.x)
  restores a deterministic gate; local mypy upgraded to match
- **mypy overrides**: `pyproject.toml` `ignore_missing_imports` now also
  covers `elasticsearch`, `elasticsearch.*`, and `pymupdf` (optional,
  lazy-imported runtime dependencies with graceful fallback)
- **17 mypy 1.20.x version-drift fixes across 8 files**: `int(success)` in
  `elasticsearch_service.py`; removed 3 unused `type: ignore[import-untyped]`
  in `dashboard/app.py`; `doc: Any` for pymupdf + removed unused ignore in
  `resume_service.py`; `deactivate_expired` rewritten to select-then-update
  (avoids `CursorResult.rowcount` typing entirely, behaviorally equivalent);
  `data: list[dict[str, Any]]` in `export_jobs.py`; `_parse_job_card(card:
  Tag)` + `str(href)` coercion in `usa/indeed.py`; version-agnostic
  `ASGITransport(app=cast(Any, app))` in `test_middleware.py` and
  `conftest.py`
- Pre-commit mypy hook aligned to `v1.20.2`
- Validation: mypy 1.20.2 clean (182 files, local + fresh-CI venv), ruff
  clean, format clean, 1247 tests passing, `make version-check` exit 0

#### Trivy Security Gate (dependency CVEs)
- `trivy-action@v0.30.0` replaced with `aquasecurity/setup-trivy@v0.3.1` +
  a direct `trivy fs` run. Root cause: `trivy-action@v0.30.0`'s composite
  action internally pins `aquasecurity/setup-trivy@v0.2.2`, which does not
  exist (setup-trivy only publishes v0.2.6+) — GitHub Actions could not
  resolve the transitive action and the Security job failed at the action
  resolution stage
- Once the scan actually ran, it surfaced **8 HIGH CVEs**, all in
  `src/cybershield/requirements.txt` (the only exact-pinned pip manifest
  under `src/`; the root `requirements.txt` uses `>=` ranges and is not
  resolvable by trivy without a lockfile). Pins bumped to patched versions:
  - `aiohttp 3.9.3 → 3.13.4` — CVE-2024-30251 (DoS, fix 3.9.4) +
    CVE-2025-69223 (zip-bomb DoS, fix 3.13.3)
  - `black 24.1.1 → 26.3.1` — CVE-2026-32274 (arbitrary file writes)
  - `lxml 5.1.0 → 6.1.0` — CVE-2026-41066 (XXE local-file disclosure)
  - `python-multipart 0.0.9 → 0.0.30` — CVE-2024-53981 (boundary DoS),
    CVE-2026-24486 (path-traversal file write), CVE-2026-42561 (header DoS),
    CVE-2026-53539 (urlencoded DoS)
- `mypy==1.8.0` in the same file aligned to `mypy>=1.20,<2` to match the
  repo-wide standard
- Verified locally with trivy 0.72.0 (identical command + skip-dirs as CI):
  `cybershield/requirements.txt` now reports **0 vulnerabilities**, exit 0

#### Tests Job flakiness (pytest-asyncio 1.x event-loop drift)
- The Tests (pytest) job failed on the Ubuntu runner with 6 `Event loop is
  closed` errors while the identical command passed locally and in a fresh
  `python:3.11` Linux Docker container (1247 tests). Root cause:
  pytest-asyncio 1.4.0 (resolved from `pytest-asyncio>=0.23.0`) removed
  support for custom `event_loop` fixtures — both `tests/conftest.py` and
  `src/cybershield/tests/conftest.py` still defined deprecated session-scoped
  `event_loop` fixtures (creating/closing a loop via
  `asyncio.get_event_loop_policy().new_event_loop()`), a documented source of
  `Event loop is closed` flakiness under pytest-asyncio 1.x with coverage
- Removed the unused `event_loop` fixtures from both conftest files (and the
  now-unused `asyncio`/`Generator` imports); `pyproject.toml`
  `[tool.pytest.ini_options]` gained `asyncio_default_fixture_loop_scope =
  "function"` (explicit function-scoped fixture loops, matching all existing
  async fixtures)
- Verified: full suite (with coverage, as CI runs it) passes twice in a row
  in the Linux Docker reproduction environment

## [Unreleased]

### Changed

#### Ruff Configuration Cleanup
- `pyproject.toml` `[tool.ruff.lint]` `ignore` now includes `COM812` —
  ruff itself warns this rule conflicts with the formatter; disabling it
  silences the warning on every lint run (config-only, no behavior change)
- `.gitignore` now ignores `coverage.xml` (generated artifact from the CI
  coverage step / local `make test` runs; should never be committed)

#### Local Full-Stack Verification (CI-equivalent)
- **Full test suite** (exact CI command): **1247 passed, 0 failed, 0 skipped**;
  no `Event loop is closed` errors — confirms the pytest-asyncio flakiness
  fix holds across a full run
- **ruff** lint + format clean (250 files); **mypy** clean (182 files);
  **bandit** `-ll` clean; **safety** 0 vulnerabilities; **version-check**
  exit 0 (all sources 1.19.0); **smoke test** all 17 checks pass
- **trivy fs** v0.72.0 (CI-equivalent command + skip-dirs) against `src/`:
  `cybershield/requirements.txt` — **0 vulnerabilities**, exit 0
- Combined coverage (interntrack + cybershield): **72.1%** (10,619 lines,
  2,967 misses). Lowest-covered areas are the CyberGuide scrapers
  (indeed/naukri/hackernews ~11–19%) and entry-point modules
  (`start.py`, `scheduler/__main__.py`, `dashboard/app.py` at 0%) —
  candidates for future coverage work

## [Merged] - 2026-08-01 — origin/master reconciled into local master

### Merged
- Reconciled the divergent histories (local master had 18 commits: hardening
  v1.10 → v1.19; origin/master had 31 commits: notification system, coverage
  push, Render/Railway deployment configs). All 60 conflicting files resolved
  keeping the **local (newer, validated) line**; merge base `4ca12b0`.
- Adopted 25 remote-only new files: `Procfile`, `railway.toml`,
  `render.yaml`, root `alembic.ini`, `src/interntrack/reports/__init__.py`,
  and 20 new test files.
- Test triage of the 20 remote test files against the kept source:
  - 15 files (341 tests) passed as-is and are retained
  - 2 obsolete `src/cybershield/tests/test_notification_*` files removed
    (tested the old notification API superseded by the kept line)
  - 2 ABC-enforcement tests dropped from `test_notification_service_v2.py`
    (our `NotificationChannel` is a plain base class, not `abc.ABC`)
  - API mismatches fixed: `export_jobs(file_format=...)` and
    `send_test_notification` (matching kept source signatures)
  - 32 ruff errors fixed across 7 test files (SIM117, ARG005, B017/PT011,
    S106, E501, PTH123)
- `tests/conftest.py`: ported `make_job`, `make_job_mock`, `make_app_mock`
  helpers from the remote line (needed by the adopted test files);
  C408 dict() → literals, E501 docstring wrap.
- `test_notification_service.py`: replaced an auto-merged remote ABC
  assertion with `test_base_send_not_implemented` (matches kept plain-base
  implementation).
- Test suite now **1247 passing** (924 InternTrack + 323 CyberGuide);
  ruff + format clean, mypy clean, `make version-check` exit 0.
- Docs re-synced: README badge, PROJECT-PROGRESS, PROJECT-STATUS,
  TODO-CHECKLIST, docs/cscip/17-cicd.md, src/cybershield/PROGRESS.md.

## [1.19.0] - 2026-08-01

### Added

#### Business Metrics Instrumentation (InternTrack)
- `BusinessMetricsStore` in `src/interntrack/metrics.py` — dependency-free
  collector + Prometheus renderer for DB query times, scraper success rates
  and notification delivery rates; global `business_metrics_store`
- Instrumentation wiring:
  - `database/session.py` — SQLAlchemy `before/after_cursor_execute` event
    listeners (positional signature, timestamp on `conn.info`) record query
    durations into `interntrack_db_queries_total` /
    `interntrack_db_query_duration_ms`
  - `scrapers/registry.py` — `fetch_all` records per-source runs/failures
    (`interntrack_scraper_runs_total{source}` /
    `interntrack_scraper_failures_total{source}`)
  - `services/notification_service.py` — `notify` records per-channel
    delivery/failures (`interntrack_notifications_total{channel}` /
    `interntrack_notification_failures_total{channel}`)
- `main.py` — `/metrics` gains a `business` key; `/metrics/prometheus`
  concatenates both renders
- `deploy/grafana/dashboards/business.json` — **InternTrack Business**
  dashboard (uid `interntrack-business`): DB query latency, scraper runs vs
  failures per source, notification delivery vs failures per channel
- `tests/unit/test_business_metrics.py` (13 tests) — store behavior,
  DB-listener wiring (regression guard for the event-signature bug),
  scraper/notification instrumentation, dashboard exprs pinned to emitted
  metrics

### Changed
- Both packages + `.env`/`.env.example` + `pyproject.toml` + deployment
  artifacts synced to **1.19.0**; `make version-check` exit 0

## [1.18.0] - 2026-08-01

### Added

#### Loki + Promtail Log Monitoring (InternTrack)
- `deploy/loki/loki-config.yml` — single-binary Loki (tsdb schema v13,
  filesystem storage, 336h retention, `max_line_size` 1MB)
- `deploy/loki/promtail-config.yml` — Docker-socket service discovery
  (`docker_sd_configs`, 5s refresh) shipping to `http://loki:3100`; parses the
  app's structlog JSON (`timestamp`/`level` labels + RFC3339 timestamp) and
  relabels to `container`/`compose_service`/`compose_project`/`stream`
- `docker-compose.yml` `loki` (3.4.2, port 3100) + `promtail` (3.4.2,
  port 9080, docker.sock read-only, depends_on loki) services + `loki_data`
  volume, all in the `monitoring` profile
- Grafana provisioning adds a **Loki** datasource (uid `loki`,
  `http://loki:3100`)
- `deploy/grafana/dashboards/logs.json` — **InternTrack Logs** dashboard
  (uid `interntrack-logs`): log volume by service, error-level rate,
  top log producers, live `{job="docker"} | json` log panel + service template
- `tests/unit/test_log_monitoring.py` (10 tests) pin the configs to each other
  (loki layout, promtail→loki clients + docker socket, compose services,
  loki datasource, valid LogQL exprs + template var)

### Changed
- Both packages + `.env`/`.env.example` + `pyproject.toml` + deployment
  artifacts synced to **1.18.0**; `make version-check` exit 0

## [1.17.0] - 2026-08-01

### Added

#### Node-Exporter System Monitoring (InternTrack)
- `docker-compose.yml`: new `node-exporter` service
  (`prom/node-exporter:v1.8.2`, port 9100, host `/proc`/`/sys`/`/` mounted
  read-only with `--path.procfs`/`--path.sysfs`/`--path.rootfs`, `monitoring`
  profile) so host CPU/memory/disk/network metrics are scrapeable
- `deploy/prometheus/prometheus.yml`: new `node-exporter` scrape job
  (target `node-exporter:9100`, `component: node-exporter` label)
- `deploy/prometheus/alerts.yml`: new `system` alert group —
  `DiskSpaceLow` (root filesystem free < 10%, critical, 5m), `MemoryHigh`
  (memory usage > 90%, warning, 5m), `CpuHigh` (CPU usage > 90%, warning,
  10m) — all targeting real `node_*` metrics (completes the TODO-CHECKLIST
  System Metrics + disk/memory alerting items)
- `deploy/grafana/dashboards/system.json`: **InternTrack System** dashboard
  (uid `interntrack-system`) — CPU, memory, and disk stat panels plus
  network traffic (`rate(node_network_receive/transmit_bytes_total[5m])`)
  and system load (`node_load1`) timeseries
- Tests: `tests/unit/test_system_monitoring.py` (7 tests) — node-exporter
  service + scrape job wiring, the `system` alert group, and that every
  PromQL expression (alerts + dashboard) references a real node-exporter
  metric; `node_load1` used directly (it's a gauge — `rate()` would be
  invalid PromQL)
- `docs/SECURITY-AND-METHODOLOGIES.md` §7.3 note updated: system alerts now
  ship with the node-exporter target (no longer a future requirement)

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.17.0`; root `pyproject.toml`
  synced — verified by `make version-check` (exit 0)

## [1.16.0] - 2026-08-01

### Added

#### Prometheus Alerting Rules (InternTrack)
- New `deploy/prometheus/alerts.yml` — app-level alert rules in the
  `interntrack-api` group, all targeting the **actual** metrics the API emits
  at `/metrics/prometheus`:
  - `HighErrorRate` — 5xx rate / request rate > 0.1 for 5m (critical)
  - `HighLatency` — `interntrack_http_request_duration_ms > 1000` for 5m
    (warning)
  - `ServiceDown` — `up{job="interntrack-api"} == 0` for 1m (critical)
- `deploy/prometheus/prometheus.yml` now declares `rule_files: [alerts.yml]`
  (resolved relative to the config, i.e. `/etc/prometheus/alerts.yml`), and
  the compose `prometheus` service mounts `./deploy/prometheus/alerts.yml`
  read-only — alerts viewable at `http://localhost:9090/alerts`
- `docs/SECURITY-AND-METHODOLOGIES.md` §7.3 example replaced: it previously
  documented a generic `alerts.yml` using metrics that don't exist
  (`http_requests_total{status=~"5.."}`, `histogram_quantile(...
  http_request_duration_seconds)`); the section now documents the real rules
- Tests: `tests/unit/test_prometheus_alerts.py` (8 tests) — validates the
  rules YAML, expected rule names, every rule has `expr`+`for`, every PromQL
  expression references an emitted `interntrack_http_*` metric (guards against
  drift), `ServiceDown` uses `up{}`, `rule_files` is declared, and the compose
  service mounts the alerts file
- `05-api-design.md`: monitoring-stack section documents the alert table
  (rule / expression / severity / `for`) and the `/alerts` endpoint

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.16.0`; root `pyproject.toml`
  synced — verified by `make version-check` (exit 0)

## [1.15.0] - 2026-08-01

### Added

#### Grafana Monitoring Stack (InternTrack)
- New `deploy/grafana/` assets behind the compose `monitoring` profile:
  - `provisioning/datasources/datasource.yml` — Prometheus datasource (uid
    `prometheus`, url `http://prometheus:9090`, isDefault, 15s timeInterval)
  - `provisioning/dashboards/dashboards.yml` — file provider loading the
    mounted dashboards dir; provisioned dashboards are read-only
    (`allowUiUpdates: false`, `disableDeletion: true`)
  - `dashboards/interntrack.json` — **InternTrack API** dashboard (uid
    `interntrack-api`) with 5 panels: request rate
    (`rate(interntrack_http_requests_total[5m])`), 5xx error rate (5xx rate /
    clamped request rate), average latency stat
    (`interntrack_http_request_duration_ms`), requests by status code
    (`..._by_status_total`), and top paths by request rate
    (`topk(10, ..._by_path_total)`); 15s refresh matching the scrape interval
- `docker-compose.yml`: new `grafana` service
  (`grafana/grafana:11.1.0`, port 3000, env-overridable
  `GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD`, `GF_USERS_ALLOW_SIGN_UP=false`,
  provisioning + dashboards mounted read-only, `grafana_data` volume,
  `depends_on: prometheus`, `monitoring` profile)
- Tests: `tests/unit/test_grafana_dashboard.py` (8 tests) — validates the
  dashboard JSON structure and that **every PromQL expression references a
  metric the API actually emits** (guards against dashboard drift), the
  datasource uid matches provisioning, and the provisioning YAML points at
  `prometheus:9090`
- `pyyaml>=6.0` added to `requirements-dev.txt` (the dashboard tests import
  yaml directly instead of relying on bandit's transitive dependency)
- `05-api-design.md` monitoring-stack section: `docker compose --profile
  monitoring up -d prometheus grafana` + production warning to override the
  default `admin`/`admin` Grafana credentials

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.15.0`; root `pyproject.toml`
  synced — verified by `make version-check` (exit 0)

## [1.14.0] - 2026-08-01

### Added

#### Redis-Backed Rate Limiting (InternTrack)
- New `RedisRateLimitStore` in `middleware/rate_limit.py` — multi-instance
  safe sliding-window limiter using an atomic Lua script over a Redis ZSET
  (prune, count, and record in one round trip); lazily connects via
  `redis.asyncio` (already a dependency, `REDIS_URL` already in compose); the
  `rl:{key}` ZSET **and** the `rl:{key}:seq` member counter both get an
  `EXPIRE` in lockstep so neither leaks in Redis
- On a Redis outage `is_allowed_async` falls back to an in-memory store
  (once-only warning, never fails closed) so the API keeps serving with
  per-instance limits during the outage (the store stays degraded until
  process restart; it never re-attempts Redis to avoid hammering it with
  2s timeouts)
- `get_rate_limit_store()` factory: returns the Redis store when `REDIS_URL`
  is configured, else the global in-memory store; `RateLimitMiddleware` now
  takes a `store` parameter and `main.py` passes the factory result
- `RateLimitStore` gained an async `is_allowed_async` alias so the middleware
  shares one code path across both stores
- `X-RateLimit-Reset` semantics aligned between the in-memory and Redis
  stores (`int(now + window_seconds)` — the window end)
- Tests (12 new): `TestRedisRateLimitStore` via fakeredis (allows, blocks,
  independent keys, window expiry, clear specific/all), fallback tests
  (broken Redis client degrades to in-memory), factory selection tests, the
  async-alias parity test, and a middleware-over-Redis HTTP test
- Dev dependency `fakeredis[lua]>=2.0.0` added to `requirements-dev.txt`
  (lupa is required for the Lua script to run in fakeredis)
- Smoke test now sets `REDIS_URL=''` so the live burst stays deterministic
  even on machines with a local Redis running

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.14.0`; root `pyproject.toml`
  synced — verified by `make version-check` (exit 0)

## [1.13.0] - 2026-08-01

### Added

#### Prometheus Integration (InternTrack)
- `MetricsStore.render_prometheus()` — dependency-free renderer emitting the
  standard Prometheus text exposition format (`# HELP` / `# TYPE` + labeled
  samples) with proper label escaping (backslash, double-quote, newline); no
  `prometheus_client` dependency required
- New `GET /metrics/prometheus` endpoint serving the same in-memory counters
  (`interntrack_http_requests_total`, `interntrack_http_errors_total`,
  `interntrack_http_error_rate`, `interntrack_http_request_duration_ms`) with
  per-path and per-status labels
- `/metrics/prometheus` added to the rate-limiter exempt paths and the
  `MetricsMiddleware` exempt set so scrapers stay reliable and counters stay
  stable
- New `deploy/prometheus/prometheus.yml` scrape config (job
  `interntrack-api`, 15s interval, target `api:8000`) + `prometheus` service
  (`prom/prometheus:v2.53.0`) in `docker-compose.yml` behind the `monitoring`
  profile with a `prometheus_data` volume — `docker compose --profile monitoring up -d prometheus`
- `prometheus.io/scrape|path|port` annotations added to the `k8s/raw/06-api.yaml`
  Service for `kubernetes_sd_configs`-based scraping
- Tests: `TestRenderPrometheus` (format, HELP/TYPE headers, labeled samples,
  label escaping) + middleware tests (endpoint returns `text/plain` text
  format, reflects recorded requests, is not recorded itself) + rate-limit
  exempt-path coverage for `/metrics/prometheus`

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.13.0`; root `pyproject.toml`
  synced — verified by `make version-check` (exit 0)

## [1.12.0] - 2026-08-01

### Added

#### Live Smoke Test
- New `scripts/smoke_test.py` — boots the **real uvicorn server** on an
  ephemeral port against a temp SQLite DB (rate limit enabled, 3/min) and
  verifies over HTTP: `GET /` 200, `GET /health` 200 with
  `version == interntrack.__version__` and `status: healthy`, `GET /metrics`
  snapshot shape, CORS preflight 200 with `access-control-allow-origin: *`,
  unknown route 404 (checked before the burst so the exhausted limit can't
  mask it), rate-limit burst `200 200 429 429 429` (the pre-burst 404 consumes
  one of the 3 credits) with the `RATE_LIMITED` contract; cleans up temp DB
  and log in `finally`; exits non-zero on any failure
- Wired into CI as a new **smoke** job (gated after test) and a
  `make smoke` target

#### Bandit Scope + Makefile Targets
- `dashboard/` and `scripts/` added to the bandit scan scope in CI and
  `make security` / `make security-report`
- `make test` / `test-unit` / `test-integration` / `test-cov` now run the full
  suite (`tests/` + `src/cybershield/tests`) with `PYTHONPATH=src` and
  `--cov=interntrack --cov=cybershield`, matching CI exactly

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.12.0`; root `pyproject.toml`
  synced — verified by `make version-check` (exit 0)

## [1.11.0] - 2026-08-01

### Changed

#### Dashboard Lint Cleanup
- `dashboard/app.py` + `dashboard/components/*`: fixed all 24 pre-existing ruff
  errors (unused imports, unused widget locals, S110 `try/except/pass` →
  `contextlib.suppress`, C408 `dict()` → literals, PIE810, ARG001, E501 long
  lines, COM812) — dashboard now passes `ruff check` and `ruff format` cleanly
- `job_card()` now renders a **View Job** link when a `url` is provided
  (previously the argument was unused)
- `dashboard/` added to the **CI lint/format scope** (`ruff check` +
  `ruff format --check` now cover `src/ tests/ dashboard/`) and to the
  `make lint` / `make format` / `make format-check` targets

#### Rate-Limit Exemption Coverage
- `tests/unit/test_rate_limit.py`: the exempt-paths test now also verifies
  `GET /metrics` bypasses the rate limit (loop of 5 returns 200); the minimal
  `_build_app` test app registers a `/metrics` route so the assertion is real

#### Version
- Both packages, `.env`/`.env.example`, canaries, Helm chart, Oracle
  deployment files, and docs bumped to `1.11.0`; root `pyproject.toml`
  version synced — verified by `make version-check` (exit 0)
- Live smoke test (real uvicorn, temp DB/port): `/health` reports
  `{"version": "1.11.0"}`, `/metrics` returns the snapshot shape, CORS
  preflight 200, rate-limit burst `200 200 200 429 429` (limit=3)

## [1.10.0] - 2026-08-01

### Added

#### Version Consistency Gate
- New `scripts/check_versions.py` — standalone checker verifying
  `interntrack.__version__ == cybershield.__version__ == .env.example
  APP_VERSION == pyproject.toml version`; exits non-zero on any drift so CI
  fails on the kind of silent version skew that historically crept in
- Wired into CI as a new **Version consistency** job (gates the test job) and
  a `make version-check` target
- `tests/unit/test_version_check.py` (10 tests) covering all four sources,
  mismatch detection, exit codes, and missing-source handling

#### Dashboard Live Version
- `dashboard/app.py` now fetches the version from `GET /health` (single
  source of truth) instead of a hardcoded string; falls back to
  `DEFAULT_VERSION` when the API is unreachable so the dashboard still renders

### Changed

#### Version Sync (root pyproject.toml + 1.10.0)
- Root `pyproject.toml` `version` bumped from `1.0.0` (stale since the very
  first release) to `1.10.0`; now enforced by the consistency gate
- Both packages bumped to `1.10.0`; `.env`/`.env.example`
  `APP_VERSION=1.10.0`; canaries updated in `tests/unit/test_main.py` and
  `src/cybershield/tests/test_version.py`
- `README.md` badge refreshed to 776 tests
- `CONTRIBUTING.md` Releasing checklist: step 5 notes the dashboard now reads
  from `/health` (the `DEFAULT_VERSION` fallback still needs syncing) and adds
  `make version-check` as the final verification step

## [1.9.0] - 2026-08-01

### Changed

#### Version Sync (both packages)
- `interntrack.__version__` bumped to `1.9.0` (was lagging the CHANGELOG at
  1.7.0) — `app_version` already reads from the package (single source of truth)
- `cybershield.__version__` bumped from `1.0.0` to `1.9.0` and `config.py`
  `app_version` now reads the package version instead of a hardcoded string
- `.env` + `.env.example` `APP_VERSION=1.9.0`; version canaries updated in
  `tests/unit/test_main.py` and new `src/cybershield/tests/test_version.py`
  (2 tests) so CI validates both packages report the current release

#### Documentation
- `docs/05-api-design.md`: new **System Endpoints** section documenting
  `GET /health` (200 healthy / 503 degraded readiness probe) and `GET /metrics`
  (counts, error rate, latency, status histogram); `/metrics` added to the
  rate-limit exempt paths
- `README.md`: badges refreshed to 764 tests + bandit/safety/trivy clean;
  **System** endpoint table (`/health`, `/metrics`) added
- `CONTRIBUTING.md`: new **Releasing** section — step-by-step version-bump
  checklist (CHANGELOG, `__version__` in both packages, `.env`/`.env.example`,
  version canaries) so future releases can't drift

## [1.8.0] - 2026-08-01

### Added

#### Live Smoke Test ✅
- Booted the real API (uvicorn) on a temp port/DB and verified over HTTP: `GET /`
  (200 app info), `GET /health` (200 healthy, database ok), `GET /docs` (404 in
  prod mode), CORS preflight (200 with allow-origin), 404 routes, and a
  rate-limit burst (`req1:200 req2:200 req3:429 req4:429 req5:429` at 3/min)
  with the `RATE_LIMITED` error contract

#### Request Metrics Endpoint (InternTrack)
- New `src/interntrack/metrics.py`: in-memory `MetricsStore` (total requests,
  errors, latency, per-path counts, status histogram, `snapshot()`, `reset()`)
  + `MetricsMiddleware` recording every request except `/metrics` itself
- `GET /metrics` exposes the snapshot for monitoring (TODO-CHECKLIST §14)
- Middleware registered after the rate limiter so 429s are recorded, before CORS
- `/metrics` added to the rate-limiter exempt paths so scrapers stay reliable
- `tests/unit/test_metrics.py` (10 tests): store counters/reset + endpoint
  integration via the client fixture

#### Version Single Source of Truth
- `config.py` `app_version` now reads `__version__` from the package (was a
  hardcoded `1.0.0` that had drifted from the CHANGELOG)
- Bumped `interntrack.__version__` to `1.7.0`; updated `.env` and `.env.example`
  `APP_VERSION` to match
- `TestVersionConsistency` (2 tests) pins `app_version == __version__` and the
  CHANGELOG release so the drift can never silently recur

#### Deployment & CI
- `.github/workflows/cd.yml` created (was only documented): tag-based Docker
  build/push + SSH deploy, matching the target pipeline in 17-cicd.md
- CI `security` job now runs a Trivy filesystem scan (HIGH/CRITICAL, exit-code
  1) scoped to `src/` (skips tests/dashboard/data/migrations)
- CI `security` job renamed to "Security (bandit + safety + trivy)"

#### Test Coverage Push
- `tests/unit/test_worker.py` rewritten: 4 meaningful tests (scheduler setup,
  signal-handler registration, shutdown handler exit, entrypoint guard)
  replacing a no-op test — `worker.py` coverage 0% → **100%**
- `utils/helpers.py` already at 100%; combined InternTrack count 429 → **443**

## [1.7.0] - 2026-08-01

### Changed

#### Readiness Probe Fix (InternTrack)
- `GET /health` no longer depends on `get_db` — it creates its own session via
  `async_session_factory` inside the handler with a try/except
- A fully unreachable database engine now returns **503 `degraded`** instead of
  a 500 from the dependency layer (the previous readiness gap)
- Unit tests rewritten to monkeypatch `interntrack.database.session.async_session_factory`
  and cover three paths: healthy, session-creation failure (engine down), and
  probe failure (`SELECT 1` raises)
- `tests/conftest.py` `client` fixture points `async_session_factory` at the
  in-memory test engine (restored after each test) so the integration health
  probe succeeds
- README badges refreshed: 749 tests → 750, added bandit + safety security badge

## [1.6.0] - 2026-08-01

### Added

#### Dependency Security Scan (safety)
- `safety check -r requirements.txt -r requirements-dev.txt --full-report` wired
  into the CI `security` job (installed as `safety>=2.3.0,<3` to avoid the v3
  `check`→`scan` migration drift, matching `requirements-dev.txt`)
- Local scan result: **22 packages scanned, 0 vulnerabilities**
  (`requirements.txt`) and 9 scanned, 0 vulnerabilities (`requirements-dev.txt`)
- Makefile: new `deps-check` target for the dependency scan

#### Report Service Hardening (InternTrack)
- `report_service.py`: template directory is now resolved module-relative
  (`Path(__file__).resolve().parent.parent / "reports" / "templates"`) instead of
  CWD-relative, so rendering works from any working directory
- New `tests/unit/test_report_service.py` (10 tests): template dir resolution,
  Jinja env loading of all 3 templates, async `render_report` HTML assertions
  for daily/weekly/monthly (incl. the `{:,.0f}` salary formatting), unknown-type
  raises `jinja2.TemplateNotFound`, autoescape blocks `<script>` injection, and
  `generate_daily/weekly/monthly` shape tests with mocked repositories

## [1.5.0] - 2026-08-01

### Added

#### Security Scanning (bandit)
- First security scan: `bandit -r src/` — 3 high (B324 weak MD5) + 5 medium
  (B104 bind-all) findings found and resolved
- MD5 calls in `cybershield/cache.py` and `cybershield/scrapers/base.py` now use
  `usedforsecurity=False` (cache/dedup fingerprinting, not security)
- Intentional dev `0.0.0.0` binds marked `# nosec B104` (env-overridable defaults)
- CI: new `security` job (`bandit -r src/ -ll -q`) gates the test job
- Makefile: `security` (bandit gate) and `security-report` (HTML) targets

#### Pre-commit & Environment
- Added `.pre-commit-config.yaml` (ruff --fix + ruff-format, mypy with
  `PYTHONPATH=src`, commitizen) matching the hooks documented in 17-cicd.md
- `.env.example` rewritten: added `RATE_LIMIT_*` and CORS variables

#### Health Check Enhancement (InternTrack)
- `GET /health` now runs a DB connectivity probe (`SELECT 1` via `get_db`)
- Returns 200 `healthy` with `version` + `database: ok`, or 503 `degraded`
  when the probe fails
- Tests: integration health test asserts `database: ok` + `version`; new
  `TestHealthEndpoint` unit tests (healthy + degraded 503)

## [1.4.0] - 2026-08-01

### Added

#### API Rate Limiting (InternTrack)
- New `src/interntrack/middleware/rate_limit.py`: in-memory sliding-window
  `RateLimitStore` + `RateLimitMiddleware` (per-IP and per-API-key limits)
- 429 responses follow the standard `{error: {code, message, details}}` contract
  with `X-RateLimit-*` headers and `Retry-After`
- Exempt paths: `/`, `/health`, `/docs`, `/redoc`, `/openapi.json`
- Settings: `rate_limit_enabled`, `rate_limit_per_minute` (100), and
  `rate_limit_api_key_per_minute` (1000); middleware wired in `main.py` when enabled
- `tests/unit/test_rate_limit.py`: store behavior (windows, independence, cleanup,
  clear) + HTTP middleware tests (429 contract, exempt paths, per-API-key limits)
- `TestRateLimitConfig` in `tests/unit/test_main.py`; conftest disables rate
  limiting for deterministic integration tests

#### Dashboard Component Tests
- `tests/unit/test_dashboard_components.py` (46 tests): cards, forms, and charts
  logic tested with lightweight fakes injected into `sys.modules` (streamlit and
  plotly are not required for the backend suite)
- `tests/unit/test_rate_limit.py`: 10 tests including CORS-on-429 coverage
  (RateLimitMiddleware registered before CORS so browser clients see
  `access-control-allow-origin` on rate-limited responses)
- Covers metric/job/application cards, skill badges, section headers, info/
  warning cards, search/filter/notification/skill forms, and all chart
  data-shaping helpers

#### CI & Docs
- `.github/workflows/ci.yml`: test job now collects coverage
  (`--cov=interntrack --cov=cybershield`) and uploads `coverage.xml` artifact
- `docs/05-api-design.md`: API rate limiting section (limits, headers, 429 contract)
- `docs/cscip/17-cicd.md`: aligned with the actual coverage step
- README badges updated: 737 tests, 67% coverage, CI workflow badge

## [1.3.0] - 2026-08-01

### Added

#### CI/CD
- Added `.github/workflows/ci.yml` — ruff lint + format check, mypy on both
  modules, and the combined InternTrack + CyberGuide test suite (679 tests)

#### Documentation
- `docs/01-software-architecture.md` — exception `to_dict()` contract, exception
  handler ordering, CORS settings & configuration
- `docs/05-api-design.md` — error contract table (HTTP status → error code) and
  CORS configuration + preflight example
- `docs/cscip/15-deployment.md` — `is_trusted` migration note for existing
  deployments (ALTER TABLE) since editing the initial migration only covers
  fresh schemas

#### Test Coverage (CyberGuide engines + Elasticsearch)
- Scam detection: email/domain edge cases, risk-level boundaries (low/medium/
  high/critical), score breakdown, batch analysis
- Deduplication: URL fragment/empty normalization, hash case-insensitivity,
  empty similarity, canonical selection, non-duplicate find
- Verification: naive datetime deadlines, weighted score calculation
- Classification: explicit years extraction, batch aggregation
- Elasticsearch: close error handling, missing-ID bulk skip, bulk error via
  injected fake module, match_all search, delete success, index stats

## [1.2.0] - 2026-08-01

### Added

#### Error Handling Architecture (InternTrack)
- Registered a dedicated `AppException` handler in `main.py` (`exc.status` + `exc.to_dict()`) so domain errors (404/409/422/503) surface correctly instead of being masked as 500
- Global fallback handler returns a consistent `{error: {code, message, details}}` payload with debug detail gated by `settings.debug`
- CORS middleware is now settings-driven with comma-separated env parsing (`CORS_ORIGINS`)
- `Settings.is_production` property and `validate_security()` startup warnings (secret key + CORS hardening)
- New tests: `tests/unit/test_main.py` (9 tests) covering the exception handlers, CORS parsing, and security validation; `TestCorsMiddleware` integration tests
- Smoke-tested live API: /health, /, docs (404 in prod), CORS preflight, 404 routes

#### CyberGuide (cybershield) Quality Hardening
- Fixed 107 mypy errors across 37 files; mypy now clean on all 177 source files
- Fixed real runtime bugs:
  - httpx 0.28 `allow_redirects` removed → client now uses `follow_redirects=True`
  - `NotificationPriority.NORMAL` doesn't exist → `MEDIUM`
  - `SkillTrend.recorded_at` → `period_start` (non-existent column)
  - `Company.is_trusted` column added to models + migration; `Company.jobs` relationship added
  - `Job.company` relationship renamed to `company_ref` (was shadowing the string column and breaking `Job.company.ilike` search)
  - `NotFoundError(resource, identifier)` two-arg calls fixed in repositories
  - Scheduler `not Job.is_verified` (evaluated a Python bool) → proper SQL filter
  - `NotificationPriority` typing, scam score float init, dedup sha256 hashing
- Alembic `001_initial_schema.py` updated to include `is_trusted` column
- ruff: 1,294 errors fixed; all checks pass; 212 files formatted

## [1.1.0] - 2026-07-30

### Added

#### Test Coverage Improvements
- Added 290+ unit tests across all modules
- Test coverage improved from 42% to 82%
- Added test_notification_service.py (20 tests)
- Added test_ai_service.py (12 tests)
- Added test_classification_engine.py (15 tests)
- Added test_hackernews_scraper.py (20 tests)
- Added test_linkedin_scraper.py (14 tests)
- Added test_remoteok_scraper.py (15 tests)
- Added test_rss_feeds_scraper.py (18 tests)
- Added test_indeed_scraper.py (12 tests)
- Added test_glassdoor_scraper.py (12 tests)
- Added test_learning_service.py (16 tests)
- Added test_scheduler_jobs.py (10 tests)
- Added test_scheduler_setup.py (3 tests)
- Added test_cache.py (11 tests)
- Added test_logger.py (3 tests)
- Added test_dependencies.py (12 tests)
- Added test_worker.py (2 tests)
- Added test_encryption.py (10 tests)
- Added test_helpers.py (15 tests)

#### Documentation Updates
- Updated README.md with coverage badge (82%)
- Updated PROJECT-PROGRESS.md with 347 tests
- Updated PROJECT-STATUS.md to 100% complete
- Added CHANGELOG.md (this file)
- Added CONTRIBUTING.md with guidelines
- Added SECURITY.md with vulnerability reporting

#### Security Updates
- Contact email updated to parthasarathi442004@gmail.com
- Creator name added: PARTHASARATHI B
- Fixed datetime.utcnow() deprecation warnings (5 files)

### Fixed
- NotificationService import error (renamed to NotificationManager)
- HttpUrl serialization issue (changed to str in schema)
- Test isolation with unique URLs
- Job statistics tuple-to-dict conversion
- datetime.utcnow() deprecation warnings in models, services, repositories
- Removed redundant str() conversion in jobs.py endpoint
- Fixed docker-compose.yml version deprecation

## [1.0.0] - 2026-07-30

### Added

#### Core Application
- FastAPI application with async support
- Pydantic settings management
- Dependency injection system
- Background worker for scheduled tasks

#### Domain Layer
- SQLAlchemy models (Job, Application, Skill, Company, etc.)
- Enumerations (JobType, ApplicationStatus, NotificationChannel)
- Custom exceptions (AppException, NotFoundError, DuplicateJobError)

#### Database Layer
- Async SQLite database support
- Alembic migrations
- Session management

#### Repository Layer
- Base repository with CRUD operations
- Job repository with advanced queries
- Application repository with status tracking
- Skill repository
- User repository

#### Service Layer
- Job service with discovery orchestration
- Application service with pipeline tracking
- Notification service (Telegram, Email, Discord, Slack)
- Report service (Daily, Weekly, Monthly)
- AI service (Ollama, Gemini)
- Learning service with skill recommendations

#### Scrapers
- HackerNews scraper
- RemoteOK scraper
- RSS feed scraper
- LinkedIn scraper
- Indeed scraper
- Glassdoor scraper
- Scraper registry

#### Engines
- Deduplication engine
- Verification engine
- AI classification engine

#### API Endpoints
- Jobs CRUD endpoints
- Application tracking endpoints
- Report generation endpoints
- Notification endpoints
- Skills endpoints
- Dashboard data endpoints

#### Dashboard
- Streamlit dashboard
- Job overview page
- Application tracking page
- Analytics charts
- Learning resources page

#### Testing
- pytest configuration
- Test fixtures
- Unit tests for services
- Unit tests for engines
- Unit tests for utilities
- Unit tests for scrapers
- Integration tests for API

#### CI/CD
- GitHub Actions CI workflow
- GitHub Actions CD workflow

#### Docker
- Dockerfile for API
- Dockerfile for Dashboard
- docker-compose.yml

#### Documentation
- README.md
- LICENSE (MIT)
- SETUP.md
- Architecture documentation
- Security guide
- TODO checklist
- Project progress tracking

## [0.1.0] - 2026-07-29

### Added
- Initial project structure
- Domain layer implementation
- Database layer implementation
- Basic API endpoints
- Initial test setup
