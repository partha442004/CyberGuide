# InternTrack - Master TODO Checklist

> Complete checklist for development, testing, deployment, and maintenance.

---

## 📋 TABLE OF CONTENTS

1. [Initial Setup](#1-initial-setup)
2. [Development Phase](#2-development-phase)
3. [Database Operations](#3-database-operations)
4. [API Development](#4-api-development)
5. [Scraper Development](#5-scraper-development)
6. [Notification System](#6-notification-system)
7. [AI Integration](#7-ai-integration)
8. [Dashboard Development](#8-dashboard-development)
9. [Testing](#9-testing)
10. [Pre-Deployment](#10-pre-deployment)
11. [Deployment](#11-deployment)
12. [Post-Deployment](#12-post-deployment)
13. [Maintenance & Updates](#13-maintenance--updates)
14. [Monitoring](#14-monitoring)
15. [Security](#15-security)

---

## 1. INITIAL SETUP

### Environment Setup
- [ ] Install Python 3.11+
- [ ] Install pip and virtualenv
- [ ] Clone repository
- [ ] Run `python -m venv venv`
- [ ] Activate virtual environment
- [ ] Run `make dev` or `pip install -e ".[all]"`
- [ ] Copy `.env.example` to `.env`
- [ ] Configure environment variables in `.env`
- [ ] Run `make setup` for initial setup

### Database Setup
- [ ] Create data directory: `mkdir -p data`
- [ ] Run `alembic upgrade head` to create tables
- [ ] Run `make seed` to populate sample data (optional)
- [ ] Verify database file exists: `data/interntrack.db`

### External Services Setup
- [ ] Install and start Ollama (optional)
- [ ] Pull LLM model: `ollama pull llama3`
- [ ] Get Gemini API key (optional)
- [ ] Configure Telegram bot token (optional)
- [ ] Configure Discord webhook (optional)
- [ ] Configure Slack webhook (optional)
- [ ] Configure SMTP credentials (optional)

---

## 2. DEVELOPMENT PHASE

### Starting Services
- [ ] Start API server: `make run`
- [ ] Start worker: `make worker`
- [ ] Start dashboard: `make dashboard`
- [ ] Verify API health: `curl http://localhost:8000/health`
- [ ] Open dashboard: `http://localhost:8501`
- [ ] Open API docs: `http://localhost:8000/docs` (debug mode)

### Code Quality Checks
- [ ] Run linter: `make lint`
- [ ] Run formatter: `make format`
- [ ] Run type checker: `make typecheck`
- [ ] Fix all linting errors
- [ ] Fix all type errors
- [ ] Ensure no security warnings

### Git Workflow
- [ ] Create feature branch: `git checkout -b feature/xxx`
- [ ] Make changes
- [ ] Run tests: `make test`
- [ ] Stage changes: `git add .`
- [ ] Commit with message: `git commit -m "feat: description"`
- [ ] Push branch: `git push origin feature/xxx`
- [ ] Create pull request
- [ ] Get code review approval
- [ ] Merge to main

---

## 3. DATABASE OPERATIONS

### Schema Changes
- [ ] Modify models in `src/interntrack/domain/models.py`
- [ ] Generate migration: `alembic revision --autogenerate -m "description"`
- [ ] Review generated migration in `migrations/versions/`
- [ ] Test migration: `alembic upgrade head`
- [ ] Test downgrade: `alembic downgrade -1`
- [ ] Re-run upgrade: `alembic upgrade head`
- [ ] Commit migration file

### Data Management
- [ ] Backup database before changes: `cp data/interntrack.db data/backup_$(date).db`
- [ ] Run seed script: `python -m interntrack.scripts.seed`
- [ ] Export data: `make export-jobs`
- [ ] Verify data integrity

### Migration Checklist
- [ ] Migration is reversible
- [ ] Migration handles existing data
- [ ] Migration doesn't break running application
- [ ] Migration tested on clean database
- [ ] Migration tested with existing data

---

## 4. API DEVELOPMENT

### Creating New Endpoint
- [ ] Define Pydantic schema in `api/schemas/`
- [ ] Create router file in `api/v1/` (if new resource)
- [ ] Add endpoint function
- [ ] Add request validation
- [ ] Add response model
- [ ] Add error handling
- [ ] Add to `api/router.py`
- [ ] Test endpoint manually
- [ ] Add to API documentation
- [ ] Write integration test

### Endpoint Checklist
- [ ] Request body validated with Pydantic
- [ ] Response model defined
- [ ] HTTP status codes correct
- [ ] Error responses follow standard format
- [ ] Authentication added (if required)
- [ ] Rate limiting configured
- [ ] Input sanitization implemented

### API Testing
- [ ] Test with curl/httpx
- [ ] Test with Swagger UI
- [ ] Test error cases
- [ ] Test pagination
- [ ] Test filtering
- [ ] Test authentication

---

## 5. SCRAPER DEVELOPMENT

### Creating New Scraper
- [ ] Create scraper class in `scrapers/`
- [ ] Inherit from `BaseScraper`
- [ ] Implement `source_name` property
- [ ] Implement `fetch()` method
- [ ] Parse job data into `RawJob`
- [ ] Handle errors gracefully
- [ ] Add rate limiting
- [ ] Register in `registry.py`
- [ ] Test scraper
- [ ] Add to default registry

### Scraper Testing
- [ ] Test with sample queries
- [ ] Verify deduplication works
- [ ] Test error handling
- [ ] Test rate limiting
- [ ] Test with different locations
- [ ] Verify data quality

### Scraper Maintenance
- [ ] Monitor for website changes
- [ ] Update selectors when needed
- [ ] Check robots.txt compliance
- [ ] Verify rate limits
- [ ] Update user agent if blocked

---

## 6. NOTIFICATION SYSTEM

### Adding Notification Channel
- [ ] Create channel class in `notifications/`
- [ ] Inherit from `NotificationChannel`
- [ ] Implement `send()` method
- [ ] Add to `NotificationManager._setup_channels()`
- [ ] Add configuration to `.env`
- [ ] Add to `Settings` class
- [ ] Test channel
- [ ] Update documentation

### Notification Testing
- [ ] Configure channel in `.env`
- [ ] Test with `POST /api/v1/notifications/test`
- [ ] Verify message format
- [ ] Test error handling
- [ ] Test multiple channels
- [ ] Verify rate limits

### Notification Templates
- [ ] Create/update HTML templates
- [ ] Test template rendering
- [ ] Verify variable substitution
- [ ] Test with sample data
- [ ] Check responsive design

---

## 7. AI INTEGRATION

### Ollama Setup
- [ ] Install Ollama
- [ ] Pull model: `ollama pull llama3`
- [ ] Configure `OLLAMA_BASE_URL` in `.env`
- [ ] Test connection: `curl http://localhost:11434/api/tags`
- [ ] Test classification

### Gemini Setup
- [ ] Get API key from Google AI Studio
- [ ] Configure `GEMINI_API_KEY` in `.env`
- [ ] Test connection
- [ ] Test classification

### AI Features Testing
- [ ] Test job classification
- [ ] Test skill extraction
- [ ] Test skill matching
- [ ] Test learning path generation
- [ ] Verify fallback to rule-based

---

## 8. DASHBOARD DEVELOPMENT

### Adding Dashboard Page
- [ ] Create page file in `dashboard/pages/`
- [ ] Add page title and icon
- [ ] Add navigation entry
- [ ] Add data fetching
- [ ] Add visualizations
- [ ] Add interactivity
- [ ] Test responsiveness
- [ ] Test with different data

### Dashboard Testing
- [ ] Start dashboard: `streamlit run dashboard/app.py`
- [ ] Test all pages
- [ ] Test all charts
- [ ] Test filters
- [ ] Test search
- [ ] Test dark/light mode
- [ ] Test mobile view

### Dashboard Deployment
- [ ] Verify API connection
- [ ] Test with production data
- [ ] Verify all charts render
- [ ] Check loading times
- [ ] Test error states

---

## 9. TESTING

### Unit Tests
- [ ] Write tests for new functions
- [ ] Test happy path
- [ ] Test edge cases
- [ ] Test error cases
- [ ] Mock external services
- [ ] Achieve >80% coverage

### Integration Tests
- [ ] Test API endpoints
- [ ] Test database operations
- [ ] Test service interactions
- [ ] Test notification delivery
- [ ] Test report generation

### Running Tests
```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Generate coverage report
make test-cov
```

### Test Checklist
- [ ] All tests pass
- [ ] Coverage >80%
- [ ] No flaky tests
- [ ] No slow tests (>5s)
- [ ] All mocking is correct

---

## 10. PRE-DEPLOYMENT

### Code Review
- [ ] Self-review complete
- [ ] Linting passes
- [ ] Type checking passes
- [ ] All tests pass
- [ ] Documentation updated
- [ ] No console.log/print statements
- [ ] No hardcoded secrets
- [ ] No debug code

### Configuration
- [ ] Environment variables documented
- [ ] `.env.example` updated
- [ ] Default values are safe
- [ ] Feature flags configured
- [ ] Logging configured

### Documentation
- [ ] README updated
- [ ] API docs generated
- [ ] Changelog updated
- [ ] Deployment guide updated

### Security Review
- [ ] No secrets in code
- [ ] Input validation complete
- [ ] SQL injection prevention
- [ ] XSS prevention
- [ ] CSRF protection
- [ ] Rate limiting configured
- [ ] CORS configured correctly

---

## 11. DEPLOYMENT

### Docker Deployment
```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Docker Checklist
- [ ] Dockerfile builds successfully
- [ ] docker-compose.yml configured
- [ ] Environment variables set
- [ ] Volumes configured
- [ ] Health checks working
- [ ] Logs accessible
- [ ] Restart policy set

### Production Deployment
- [ ] Pull latest changes
- [ ] Build Docker images
- [ ] Run database migrations
- [ ] Start services
- [ ] Verify health checks
- [ ] Test critical paths
- [ ] Monitor logs

### Deployment Verification
- [ ] API responds to health check
- [ ] Dashboard loads
- [ ] Database connection works
- [ ] Notifications working
- [ ] Scrapers running
- [ ] No errors in logs

---

## 12. POST-DEPLOYMENT

### Immediate Checks
- [ ] All services healthy
- [ ] No error logs
- [ ] API response times normal
- [ ] Dashboard accessible
- [ ] Database responding

### Monitoring Setup
- [ ] Check application logs
- [ ] Monitor API metrics
- [ ] Monitor database size
- [ ] Check disk usage
- [ ] Monitor memory usage

### User Verification
- [ ] Test user flows
- [ ] Verify notifications
- [ ] Check report generation
- [ ] Test job discovery

---

## 13. MAINTENANCE & UPDATES

### Regular Maintenance
- [ ] Review error logs daily
- [ ] Check database backups weekly
- [ ] Update dependencies monthly
- [ ] Review security advisories
- [ ] Clean old logs
- [ ] Optimize database

### Dependency Updates
```bash
# Check outdated packages
pip list --outdated

# Update all packages
pip install --upgrade -r requirements.txt

# Test after updates
make test
```

### Database Maintenance
```bash
# Backup database
cp data/interntrack.db data/backup_$(date +%Y%m%d).db

# Vacuum database (SQLite)
sqlite3 data/interntrack.db "VACUUM;"

# Check integrity
sqlite3 data/interntrack.db "PRAGMA integrity_check;"
```

### Update Checklist
- [ ] Create backup
- [ ] Review changelog
- [ ] Test in development
- [ ] Run migration tests
- [ ] Deploy to staging
- [ ] Run smoke tests
- [ ] Deploy to production
- [ ] Monitor for issues

---

## 14. MONITORING

### Application Metrics
- [x] API response times — `interntrack_http_request_duration_ms` via `/metrics/prometheus`
- [x] Request counts — `interntrack_http_requests_total` (total + per-path + per-status)
- [x] Error rates — `interntrack_http_errors_total` + `interntrack_http_error_rate`
- [ ] Database query times
- [ ] Scraper success rates
- [ ] Notification delivery rates

### System Metrics
- [ ] CPU usage
- [ ] Memory usage
- [ ] Disk usage
- [ ] Network traffic
- [ ] Process count

### Log Monitoring
- [ ] Application logs
- [ ] Access logs
- [ ] Error logs
- [ ] Database logs

### Alerting
- [ ] High error rate alert
- [ ] High response time alert
- [ ] Disk space alert
- [ ] Memory alert
- [ ] Service down alert

---

## 15. SECURITY

### Security Checklist
- [ ] Environment variables secure
- [ ] API keys rotated regularly
- [ ] Database encrypted at rest
- [ ] HTTPS configured
- [ ] Rate limiting enabled
- [ ] Input validation complete
- [ ] SQL injection prevention
- [ ] XSS prevention
- [ ] CSRF protection
- [ ] Authentication working
- [ ] Authorization working
- [ ] Audit logging enabled

### Security Updates
- [ ] Monitor CVE databases
- [ ] Update vulnerable packages
- [ ] Review access logs
- [ ] Rotate secrets quarterly
- [ ] Review user permissions
- [ ] Update security documentation

---

## ✅ HARDENING PASS (2026-08-01) — COMPLETED

### Static Analysis
- [x] mypy clean across all 177 source files (fixed 107 cybershield errors)
- [x] ruff lint: all checks passed (fixed 1,294 errors)
- [x] ruff format: 212 files formatted

### Error Handling & API Contract
- [x] Dedicated `AppException` handler registered (status + `to_dict()` payload)
- [x] Consistent `{error: {code, message, details}}` shape on all error paths
- [x] Global fallback handler with debug-detail gating
- [x] CORS settings-driven with comma-separated env parsing
- [x] `validate_security()` startup warnings (secret key + CORS)

### Real Bug Fixes
- [x] httpx 0.28 `allow_redirects` → `follow_redirects` (verification engine)
- [x] `NotificationPriority.NORMAL` → `MEDIUM` (orchestrator)
- [x] `SkillTrend.recorded_at` → `period_start` (skill repository)
- [x] `Company.is_trusted` added to model + migration
- [x] `Job.company` relationship → `company_ref` (was shadowing string column, broke search)
- [x] `NotFoundError(resource, identifier)` 2-arg calls
- [x] Scheduler `not Job.is_verified` → proper SQL filter

### Tests
- [x] `tests/unit/test_main.py` (9 tests): handlers, CORS parsing, security validation
- [x] `TestCorsMiddleware` integration tests
- [x] Smoke test of live API (health, CORS preflight, 404, docs-off in prod)
- [x] 653 tests passing (358 InternTrack + 295 CyberGuide)

---

## ✅ HARDENING PASS 2 (2026-08-01) — COMPLETED

### API Rate Limiting (InternTrack)
- [x] `RateLimitMiddleware` + `RateLimitStore` (in-memory sliding window)
- [x] Per-IP (100/min) and per-API-key (1000/min) limits with `RATE_LIMIT_*` env overrides
- [x] 429 responses use the standard `{error: {code, message, details}}` contract
- [x] `X-RateLimit-*` headers + `Retry-After` on responses
- [x] Exempt paths: `/`, `/health`, `/docs`, `/redoc`, `/openapi.json`
- [x] Middleware wired in `main.py`, gated by `rate_limit_enabled`
- [x] Tests: `tests/unit/test_rate_limit.py` (10, incl. CORS-on-429) + `TestRateLimitConfig` in test_main.py
- [x] conftest disables rate limiting for deterministic integration tests

### Dashboard Component Tests
- [x] `tests/unit/test_dashboard_components.py` (46 tests)
- [x] cards.py: metric/job/application cards, skill badges, section headers, info/warning cards
- [x] forms.py: search/filter/job-search/application/notification/skill forms
- [x] charts.py: pie/bar/line/salary/skill-demand chart data shaping
- [x] streamlit + plotly mocked via sys.modules (not required for backend suite)

### CI & Documentation
- [x] CI test job collects coverage (`--cov=interntrack --cov=cybershield`) and uploads `coverage.xml`
- [x] README badges updated: 737 tests, 67% coverage, CI workflow badge
- [x] `docs/05-api-design.md` rate limiting section (API + scraper limits)
- [x] `docs/cscip/17-cicd.md` aligned with the actual coverage step
- [x] CHANGELOG 1.4.0 entry; PROJECT-PROGRESS/STATUS updated to 736 tests

---

## ✅ HARDENING PASS 3 (2026-08-01) — COMPLETED

### Security Scanning (bandit)
- [x] First `bandit -r src/` scan: 3 high (B324 weak MD5) + 5 medium (B104 bind-all) fixed
- [x] MD5 in cache/scrapers now uses `usedforsecurity=False` (fingerprinting, not security)
- [x] Dev `0.0.0.0` binds marked `# nosec B104` (env-overridable defaults)
- [x] CI `security` job (`bandit -r src/ -ll -q`) gates the test job
- [x] Makefile `security` + `security-report` targets

### Pre-commit & Environment
- [x] `.pre-commit-config.yaml` (ruff --fix + ruff-format, mypy with PYTHONPATH=src, commitizen)
- [x] `.env.example` rewritten with `RATE_LIMIT_*` and CORS variables

### Health Check
- [x] `GET /health` runs DB connectivity probe (`SELECT 1`)
- [x] 200 healthy with `version` + `database: ok`; 503 degraded on probe failure
- [x] Integration test asserts `database: ok`; `TestHealthEndpoint` unit tests (healthy + degraded)

---

## ✅ HARDENING PASS 4 (2026-08-01) — COMPLETED

### Dependency Security Scan (safety)
- [x] `safety check -r requirements.txt -r requirements-dev.txt --full-report` wired into CI `security` job
- [x] safety pinned `>=2.3.0,<3` in CI (matches requirements-dev.txt; v3 replaced `check` with `scan`)
- [x] Local result: 22 packages scanned, 0 vulnerabilities (requirements.txt); 9 scanned, 0 (dev)
- [x] Makefile `deps-check` target

### Report Service (InternTrack)
- [x] `report_service.py` template dir resolved module-relative (`Path(__file__)...`), not CWD-relative
- [x] `tests/unit/test_report_service.py` (10 tests): template dir, Jinja env, daily/weekly/monthly render assertions (incl. `{:,.0f}` salary formatting), unknown-type raises `TemplateNotFound`, autoescape XSS, generate_* shape tests with mocked repos

---

## ✅ HARDENING PASS 5 (2026-08-01) — COMPLETED

### Readiness Probe Fix (InternTrack)
- [x] `GET /health` creates its own session via `async_session_factory` inside the handler (was `Depends(get_db)`)
- [x] Fully unreachable engine now returns **503 `degraded`** (was 500 from the dependency layer)
- [x] Unit tests monkeypatch `interntrack.database.session.async_session_factory`: healthy, session-creation failure, probe failure
- [x] conftest `client` fixture points `async_session_factory` at the in-memory test engine (restored after)
- [x] README badges: 750 tests + bandit/safety security badge

---

## ✅ HARDENING PASS 6 (2026-08-01) — COMPLETED

### Live Smoke Test
- [x] Booted real uvicorn server on a temp port/DB; verified over HTTP: `GET /` (200), `GET /health` (200 healthy), `GET /docs` (404 prod), CORS preflight (allow-origin), 404 route, rate-limit burst 200/200/429/429/429, `RATE_LIMITED` 429 contract

### Request Metrics (InternTrack)
- [x] `src/interntrack/metrics.py`: `MetricsStore` (counts/errors/latency/path histogram/status codes, snapshot, reset) + `MetricsMiddleware`
- [x] `GET /metrics` endpoint; middleware registered after rate limiter (records 429s) before CORS; /metrics exempt from recording + rate limiting
- [x] `tests/unit/test_metrics.py` (10 tests)

### Version Single Source of Truth
- [x] `app_version` reads package `__version__` (= 1.7.0), synced with `.env` + `.env.example`
- [x] `TestVersionConsistency` (2 tests) prevents silent drift

### Deployment & CI
- [x] `.github/workflows/cd.yml` (tag-based Docker build/push + SSH deploy)
- [x] Trivy fs scan (HIGH/CRITICAL, exit 1) scoped to `src/` in CI security job; job renamed "Security (bandit + safety + trivy)"

### Coverage Push
- [x] `tests/unit/test_worker.py` rewritten (4 tests): worker.py coverage 0% → **100%**
- [x] helpers.py already 100%; InternTrack 429 → 443; total **764**

---

## ✅ HARDENING PASS 7 (2026-08-01) — COMPLETED

### Version Sync (both packages → 1.9.0)
- [x] `interntrack.__version__` 1.7.0 → **1.9.0** (was lagging the CHANGELOG)
- [x] `cybershield.__version__` 1.0.0 → **1.9.0**; `config.py` `app_version` now reads the package version (single source of truth)
- [x] `.env` + `.env.example` `APP_VERSION=1.9.0`
- [x] Canaries updated in `tests/unit/test_main.py`; new `src/cybershield/tests/test_version.py` (2 tests)

### Documentation
- [x] `docs/05-api-design.md`: System Endpoints section (`/health`, `/metrics`) + `/metrics` in rate-limit exempt paths
- [x] `README.md`: 766 tests badge, bandit/safety/trivy badge, System endpoint table
- [x] `CONTRIBUTING.md`: **Releasing** section — version-bump checklist (CHANGELOG, both `__version__`s, .env, canaries)

---

## 🔄 QUICK REFERENCE

### Common Commands

```bash
# Development
make dev              # Install all dependencies
make run              # Start API server
make worker           # Start background worker
make dashboard        # Start Streamlit dashboard

# Code Quality
make lint             # Run linter
make format           # Format code
make typecheck        # Run type checker

# Testing
make test             # Run all tests
make test-unit        # Run unit tests
make test-integration # Run integration tests
make test-cov         # Generate coverage report

# Database
make db-migrate       # Run migrations
make db-revision      # Create migration
make db-reset         # Reset database

# Docker
make docker-build     # Build images
make docker-up        # Start services
make docker-down      # Stop services
make docker-logs      # View logs

# Cleanup
make clean            # Clean temporary files
```

### Environment Variables

```bash
# Required
DATABASE_URL=sqlite+aiosqlite:///./data/interntrack.db
SECRET_KEY=your-secret-key

# Optional - AI
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
GEMINI_API_KEY=your-key

# Optional - Notifications
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
SLACK_WEBHOOK_URL=
SMTP_USER=
SMTP_PASSWORD=

# Optional - Scraper
SCRAPE_INTERVAL_MINUTES=30
MAX_CONCURRENT_SCRAPERS=5
```

---

## 📝 NOTES

### Before Going Live
1. All items in "Pre-Deployment" must be checked
2. All tests must pass
3. Security review must be complete
4. Documentation must be updated
5. Backup must be created

### When Updating Live
1. Create backup first
2. Test in staging environment
3. Run migrations
4. Deploy with zero downtime
5. Monitor for errors
6. Have rollback plan ready

### Emergency Rollback
```bash
# Stop services
docker-compose down

# Restore database
cp data/backup_YYYYMMDD.db data/interntrack.db

# Start previous version
git checkout <previous-tag>
docker-compose up -d
```

## ✅ HARDENING PASS 8 (2026-08-01) — COMPLETED

### Version Consistency Gate (both packages → 1.10.0)
- [x] New `scripts/check_versions.py` — verifies `interntrack.__version__` ==
      `cybershield.__version__` == `.env.example APP_VERSION` ==
      `pyproject.toml version`; exits non-zero on any drift
- [x] New CI **Version consistency** job (gates the test job) + `make version-check`
- [x] New `tests/unit/test_version_check.py` (10 tests)
- [x] Dashboard `About` now fetches the live version from `GET /health`
      (`DEFAULT_VERSION` fallback = 1.10.0) instead of a hardcoded string
- [x] Root `pyproject.toml` `version` 1.0.0 → **1.10.0** (was stale since the
      first release); both packages + `.env`/`.env.example` synced to 1.10.0

## ✅ HARDENING PASS 9 (2026-08-01) — COMPLETED

### Dashboard Lint Cleanup + v1.11.0
- [x] Fixed all 24 pre-existing `dashboard/` ruff errors (unused imports/locals,
      S110 → `contextlib.suppress`, C408 dict literals, PIE810, ARG001, E501,
      COM812); `job_card()` now renders a View Job link from `url`
- [x] `dashboard/` added to CI ruff scope (`ruff check src/ tests/ dashboard/`)
      and `make lint/format/format-check`
- [x] Rate-limit exempt-paths test now covers `GET /metrics`
- [x] Both packages + `.env`/`.env.example` + `pyproject.toml` + deployment
      artifacts synced to **1.11.0**; `make version-check` exit 0
- [x] Live smoke test: `/health` version 1.11.0, `/metrics` snapshot, CORS
      preflight 200, rate-limit burst `200 200 200 429 429` (limit=3)

## ✅ HARDENING PASS 10 (2026-08-01) — COMPLETED

### Live Smoke Test + v1.12.0
- [x] New `scripts/smoke_test.py` — boots real uvicorn on an ephemeral port
      with a temp DB (rate limit 3/min) and verifies `/health` version ==
      `__version__`, `/metrics` shape, CORS, 404, rate burst `200 200 429 429
      429` (404 consumes one of 3 credits) + `RATE_LIMITED` contract
- [x] New CI **smoke** job + `make smoke` target
- [x] `bandit` scope extended to `dashboard/` + `scripts/` (CI + Makefile)
- [x] `make test*` targets now run the full suite (`tests/` +
      `src/cybershield/tests`) with `PYTHONPATH=src` matching CI
- [x] Both packages + `.env`/`.env.example` + `pyproject.toml` + deployment
      artifacts synced to **1.12.0**; `make version-check` exit 0

---

## ✅ HARDENING PASS 11 (2026-08-01) — COMPLETED

### Prometheus Integration + v1.13.0
- [x] `MetricsStore.render_prometheus()` — dependency-free Prometheus text
      exposition format (`# HELP`/`# TYPE` + labeled samples, label escaping)
- [x] New `GET /metrics/prometheus` endpoint (same in-memory counters as
      `/metrics`); exempt from metrics recording + rate limiting
- [x] `deploy/prometheus/prometheus.yml` scrape config + `prometheus` compose
      service (`prom/prometheus:v2.53.0`, `monitoring` profile, volume)
- [x] `prometheus.io/scrape|path|port` annotations on `k8s/raw/06-api.yaml`
      Service for k8s scraping
- [x] Tests: `TestRenderPrometheus` (format + escaping) + endpoint/exempt
      coverage in `test_metrics.py` and `test_rate_limit.py`
- [x] Both packages + `.env`/`.env.example` + `pyproject.toml` + deployment
      artifacts synced to **1.13.0**; `make version-check` exit 0

---

## ✅ HARDENING PASS 12 (2026-08-01) — COMPLETED

### Redis-Backed Rate Limiting + v1.14.0
- [x] `RedisRateLimitStore` — atomic Lua sliding window over a Redis ZSET
      (`rl:{key}` + `:seq` counter, both `EXPIRE`-bounded); multi-instance
      shared limits via `REDIS_URL`
- [x] Graceful in-memory fallback on a Redis outage (once-only warning, never
      fails closed)
- [x] `get_rate_limit_store()` factory wired into `main.py`;
      `RateLimitStore.is_allowed_async` alias for one shared middleware path
- [x] `X-RateLimit-Reset` semantics aligned across in-memory and Redis stores
- [x] 12 new tests (fakeredis): store behavior, fallback, factory selection,
      async alias parity, middleware-over-Redis; `fakeredis[lua]` dev dep;
      smoke test pins `REDIS_URL=''`
- [x] Both packages + `.env`/`.env.example` + `pyproject.toml` + deployment
      artifacts synced to **1.14.0**; `make version-check` exit 0

---

**Last Updated:** 2026-08-01
**Version:** 1.14.0
