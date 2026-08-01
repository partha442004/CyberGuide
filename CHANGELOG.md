# Changelog

All notable changes to the InternTrack project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
