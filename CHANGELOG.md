# Changelog

All notable changes to the InternTrack project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
- Contact email updated to maxxermogging@gmail.com
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
