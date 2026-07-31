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
│       │   ├── 📄 we_work_remotely.py
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
│       ├── 📁 notifications/             # Notification Infrastructure
│       │   ├── 📄 __init__.py
│       │   ├── 📄 base.py               # Base channel
│       │   ├── 📄 manager.py            # Notification manager
│       │   ├── 📄 telegram.py
│       │   ├── 📄 email.py
│       │   ├── 📄 discord.py
│       │   ├── 📄 slack.py
│       │   └── 📄 templates/            # Message templates
│       │       ├── 📄 new_job.html
│       │       ├── 📄 daily_report.html
│       │       ├── 📄 weekly_report.html
│       │       └── 📄 monthly_report.html
│       │
│       ├── 📁 reports/                   # Report Generation
│       │   ├── 📄 __init__.py
│       │   ├── 📄 generator.py          # Report generator
│       │   ├── 📄 daily.py
│       │   ├── 📄 weekly.py
│       │   ├── 📄 monthly.py
│       │   └── 📄 templates/            # Jinja2 templates
│       │       ├── 📄 daily_report.html
│       │       ├── 📄 weekly_report.html
│       │       └── 📄 monthly_report.html
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
│       ├── 📁 integrations/              # External Integrations
│       │   ├── 📄 __init__.py
│       │   ├── 📄 ollama.py             # Ollama client
│       │   ├── 📄 gemini.py             # Gemini API
│       │   └── 📄 rss.py                # RSS parser
│       │
│       └── 📁 utils/                     # Utilities
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
│   │   ├── 📄 test_deduplication.py
│   │   └── 📄 test_notification.py
│   ├── 📁 integration/
│   │   ├── 📄 __init__.py
│   │   ├── 📄 test_database.py
│   │   └── 📄 test_api.py
│   └── 📁 fixtures/                      # Test data
│       ├── 📄 jobs.json
│       └── 📄 applications.json
│
├── 📁 docs/                              # Documentation
│   ├── 📄 01-software-architecture.md
│   ├── 📄 02-folder-structure.md
│   ├── 📄 03-database-schema.md
│   ├── 📄 04-er-diagram.md
│   ├── 📄 05-api-design.md
│   ├── 📄 06-scheduler.md
│   ├── 📄 07-discovery-engine.md
│   ├── 📄 08-verification-engine.md
│   ├── 📄 09-deduplication-engine.md
│   ├── 📄 10-ai-classification.md
│   ├── 📄 11-notification-engine.md
│   ├── 📄 12-dashboard.md
│   ├── 📄 13-authentication.md
│   ├── 📄 14-deployment.md
│   ├── 📄 15-docker.md
│   ├── 📄 16-cicd.md
│   ├── 📄 17-testing.md
│   └── 📄 18-documentation.md
│
├── 📁 scripts/                           # Utility Scripts
│   ├── 📄 setup.sh                       # Initial setup
│   ├── 📄 seed_data.py                   # Database seeding
│   └── 📄 export_jobs.py                 # Export utilities
│
├── 📁 .github/                           # GitHub Configuration
│   └── 📁 workflows/
│       ├── 📄 ci.yml                     # CI pipeline
│       └── 📄 cd.yml                     # CD pipeline
│
├── 📄 .env.example                       # Environment template
├── 📄 .gitignore                         # Git ignore rules
├── 📄 .dockerignore                      # Docker ignore rules
├── 📄 Dockerfile                         # Docker image
├── 📄 docker-compose.yml                 # Docker Compose
├── 📄 pyproject.toml                     # Project configuration
├── 📄 requirements.txt                   # Dependencies
├── 📄 requirements-dev.txt               # Dev dependencies
├── 📄 Makefile                           # Common commands
├── 📄 README.md                          # Project documentation
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
