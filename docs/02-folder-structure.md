# InternTrack - Folder Structure

## Complete Directory Layout

```
internship-tracker/
├── 📁 src/
│   └── 📁 interntrack/
│       ├── 📄 __init__.py
│       ├── 📄 main.py                    # FastAPI application entry
│       ├── 📄 config.py                  # Settings management
│       ├── 📄 dependencies.py            # Dependency injection
│       │
│       ├── 📁 domain/                    # Domain Layer (Entities)
│       │   ├── 📄 __init__.py
│       │   ├── 📄 models.py             # SQLAlchemy models
│       │   ├── 📄 enums.py              # Enumerations
│       │   └── 📄 exceptions.py         # Domain exceptions
│       │
│       ├── 📁 repositories/              # Repository Layer
│       │   ├── 📄 __init__.py
│       │   ├── 📄 base.py               # Base repository
│       │   ├── 📄 job_repository.py     # Job CRUD operations
│       │   ├── 📄 application_repository.py
│       │   ├── 📄 user_repository.py
│       │   └── 📄 skill_repository.py
│       │
│       ├── 📁 services/                  # Application Layer (Use Cases)
│       │   ├── 📄 __init__.py
│       │   ├── 📄 job_service.py        # Job management
│       │   ├── 📄 application_service.py # Application tracking
│       │   ├── 📄 notification_service.py
│       │   ├── 📄 report_service.py
│       │   ├── 📄 learning_service.py
│       │   └── 📄 ai_service.py         # AI classification
│       │
│       ├── 📁 scrapers/                  # Scraping Infrastructure
│       │   ├── 📄 __init__.py
│       │   ├── 📄 base.py               # Base scraper class
│       │   ├── 📄 registry.py           # Scraper registry
│       │   ├── 📄 linkedin.py
│       │   ├── 📄 indeed.py
│       │   ├── 📄 glassdoor.py
│       │   ├── 📄 remoteok.py
│       │   ├── 📄 hackernews.py
│       │   └── 📄 rss_feeds.py
│       │
│       ├── 📁 engines/                   # Core Engines
│       │   ├── 📄 __init__.py
│       │   ├── 📄 deduplication.py      # Deduplication engine
│       │   ├── 📄 verification.py       # Job verification
│       │   ├── 📄 classification.py     # AI classification
│       │   └── 📄 matching.py           # Skill matching
│       │
│       ├── 📁 reports/                   # Report Generation
│       │   ├── 📄 __init__.py
│       │   └── 📁 templates/            # Jinja2 templates
│       │       ├── 📄 daily_report.html
│       │       ├── 📄 weekly_report.html
│       │       └── 📄 monthly_report.html
│       │
│       ├── 📁 scripts/                   # Utility Scripts
│       │   ├── 📄 __init__.py
│       │   ├── 📄 export_jobs.py        # Export utilities
│       │   └── 📄 seed_data.py          # Database seeding
│       │
│       ├── 📁 api/                       # API Layer
│       │   ├── 📄 __init__.py
│       │   ├── 📄 router.py             # Main router
│       │   ├── 📁 v1/                   # API Version 1
│       │   │   ├── 📄 __init__.py
│       │   │   ├── 📄 jobs.py
│       │   │   ├── 📄 applications.py
│       │   │   ├── 📄 reports.py
│       │   │   ├── 📄 notifications.py
│       │   │   ├── 📄 skills.py
│       │   │   └── 📄 dashboard.py
│       │   └── 📁 schemas/              # Pydantic schemas
│       │       ├── 📄 __init__.py
│       │       ├── 📄 job.py
│       │       ├── 📄 application.py
│       │       ├── 📄 user.py
│       │       ├── 📄 report.py
│       │       └── 📄 notification.py
│       │
│       ├── 📁 database/                  # Database Infrastructure
│       │   ├── 📄 __init__.py
│       │   ├── 📄 session.py            # DB session management
│       │   └── 📄 base.py               # Base model
│       │
│       ├── 📁 scheduler/                 # Task Scheduling
│       │   ├── 📄 __init__.py
│       │   ├── 📄 jobs.py               # Scheduled jobs
│       │   └── 📄 setup.py              # Scheduler setup
│       │
│       ├── 📁 utils/                     # Utilities
│           ├── 📄 __init__.py
│           ├── 📄 logger.py             # Structured logging
│           ├── 📄 cache.py              # Cache utilities
│           ├── 📄 encryption.py         # Secret management
│           └── 📄 helpers.py            # General helpers
│
├── 📁 dashboard/                         # Streamlit Dashboard
│   ├── 📄 app.py                         # Dashboard entry
│   ├── 📄 pages/                         # Dashboard pages
│   │   ├── 📄 1_📊_overview.py
│   │   ├── 📄 2_💼_jobs.py
│   │   ├── 📄 3_📋_applications.py
│   │   ├── 📄 4_📈_analytics.py
│   │   ├── 📄 5_📚_learning.py
│   │   └── 📄 6_⚙️_settings.py
│   ├── 📁 components/                    # Reusable components
│   │   ├── 📄 __init__.py
│   │   ├── 📄 charts.py
│   │   ├── 📄 cards.py
│   │   └── 📄 forms.py
│   └── 📁 styles/                        # CSS styles
│       ├── 📄 main.css
│       ├── 📄 dark.css
│       └── 📄 light.css
│
├── 📁 migrations/                        # Alembic Migrations
│   ├── 📄 env.py
│   ├── 📄 script.py.mako
│   └── 📁 versions/
│       └── 📄 001_initial.py
│
├── 📁 tests/                             # Test Suite
│   ├── 📄 __init__.py
│   ├── 📄 conftest.py                    # Pytest fixtures
│   ├── 📁 unit/
│   │   ├── 📄 __init__.py
│   │   ├── 📄 test_job_service.py
│   │   ├── 📄 test_application_service.py
│   │   ├── 📄 test_deduplication.py
│   │   ├── 📄 test_verification.py
│   │   ├── 📄 test_classification_engine.py
│   │   ├── 📄 test_matching_engine.py
│   │   ├── 📄 test_engines_extended.py
│   │   ├── 📄 test_scrapers_unified.py
│   │   ├── 📄 test_edge_cases.py
│   │   ├── 📄 test_api_v1_extended.py
│   │   ├── 📄 test_api_v1_full.py
│   │   ├── 📄 test_services_extended.py
│   │   ├── 📄 test_coverage_boost.py
│   │   ├── 📄 test_final_coverage_push.py
│   │   ├── 📄 test_export_jobs.py
│   │   ├── 📄 test_seed_data.py
│   │   ├── 📄 test_ai_service.py
│   │   ├── 📄 test_ai_service_extended.py
│   │   ├── 📄 test_notification_service.py
│   │   ├── 📄 test_notification_service_v2.py
│   │   ├── 📄 test_report_service.py
│   │   ├── 📄 test_learning_service.py
│   │   ├── 📄 test_cache.py
│   │   ├── 📄 test_cache_utils.py
│   │   ├── 📄 test_encryption.py
│   │   ├── 📄 test_encryption_utils.py
│   │   ├── 📄 test_helpers.py
│   │   ├── 📄 test_helpers_utils.py
│   │   ├── 📄 test_utils.py
│   │   ├── 📄 test_utils_extended.py
│   │   ├── 📄 test_logger.py
│   │   ├── 📄 test_dependencies.py
│   │   ├── 📄 test_worker.py
│   │   ├── 📄 test_scheduler_jobs.py
│   │   ├── 📄 test_scheduler_jobs_v2.py
│   │   ├── 📄 test_scheduler_setup.py
│   │   ├── 📄 test_scraper_base.py
│   │   └── [40+ more test files]
│   ├── 📁 integration/
│   │   ├── 📄 __init__.py
│   │   └── 📄 test_api.py
│   └── 📁 fixtures/
│       └── 📄 __init__.py
│
├── 📁 docs/                              # Documentation
│   ├── 📄 01-software-architecture.md
│   ├── 📄 02-folder-structure.md
│   ├── 📄 03-database-schema.md
│   ├── 📄 SECURITY-AND-METHODOLOGIES.md
│   └── 📁 cscip/                          # Detailed architecture docs
│
├── 📁 .github/                           # GitHub Configuration
│   └── 📁 workflows/
│       ├── 📄 ci.yml                     # CI pipeline
│       └── 📄 cd.yml                     # CD pipeline
│
├── 📄 .env.example                       # Environment template
├── 📄 .gitignore                         # Git ignore rules
├── 📄 .dockerignore                      # Docker ignore rules
├── 📄 Dockerfile                         # API container
├── 📄 Dockerfile.dashboard               # Dashboard container
├── 📄 docker-compose.yml                 # Docker Compose
├── 📄 vercel.json                        # Vercel serverless deployment (api/index.py)
├── 📄 .vercelignore                      # Vercel upload exclusions
├── 📄 render.yaml                        # Render.com deployment
├── 📄 Procfile                           # Render build system
├── 📄 pyproject.toml                     # Project configuration
├── 📄 requirements.txt                   # Dependencies
├── 📄 requirements-dev.txt               # Dev dependencies
├── 📄 Makefile                           # Common commands
├── 📄 README.md                          # Project documentation
├── 📄 CHANGELOG.md                       # Version history
├── 📄 CONTRIBUTING.md                    # Contribution guidelines
├── 📄 SECURITY.md                        # Security policy
├── 📄 SETUP.md                           # Setup guide
├── 📄 PROJECT-STATUS.md                  # Project status
├── 📄 PROJECT-PROGRESS.md                # Progress tracking
├── 📄 TODO-CHECKLIST.md                  # Development checklist
└── 📄 LICENSE                            # MIT License
```

---

## File Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Python modules | snake_case | `job_service.py` |
| Python packages | snake_case | `engines/` |
| Test files | `test_` prefix | `test_job_service.py` |
| Config files | lowercase | `pyproject.toml` |
| Documentation | `XX-name.md` | `01-architecture.md` |
| Templates | snake_case | `daily_report.html` |

---

## Key Files Description

### Core Application Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app initialization, middleware, lifespan |
| `config.py` | Pydantic settings, environment loading |
| `dependencies.py` | Dependency injection setup |

### Domain Layer

| File | Purpose |
|------|---------|
| `models.py` | SQLAlchemy ORM models |
| `enums.py` | JobStatus, ApplicationStatus, etc. |
| `exceptions.py` | Custom exception classes |

### Service Layer

| File | Purpose |
|------|---------|
| `job_service.py` | Job CRUD, discovery orchestration |
| `application_service.py` | Application state management |
| `notification_service.py` | Multi-channel notifications |
| `report_service.py` | Report generation |

### Infrastructure

| File | Purpose |
|------|---------|
| `session.py` | Async database session |
| `base.py` | Base scraper, base repository |
| `registry.py` | Scraper plugin registry |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 3: Database Schema](./03-database-schema.md)
