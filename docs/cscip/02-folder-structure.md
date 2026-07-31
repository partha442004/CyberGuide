# CyberShield Career Intelligence Platform (CSCIP) - Folder Structure

## Complete Directory Layout

```
cybershield/
├── 📁 src/
│   └── 📁 cybershield/
│       ├── 📄 __init__.py
│       ├── 📄 main.py                    # FastAPI application entry
│       ├── 📄 config.py                  # Settings management (Pydantic)
│       ├── 📄 dependencies.py            # Dependency injection
│       ├── 📄 worker.py                  # Background worker process
│       ├── 📄 event_bus.py               # Event-driven architecture
│       │
│       ├── 📁 domain/                    # Domain Layer (Core Business Logic)
│       │   ├── 📄 __init__.py
│       │   ├── 📄 models.py             # SQLAlchemy ORM models (30+ tables)
│       │   ├── 📄 enums.py              # All enumerations
│       │   ├── 📄 exceptions.py         # Custom exceptions
│       │   ├── 📄 events.py             # Domain events
│       │   └── 📄 value_objects.py       # Value objects
│       │
│       ├── 📁 repositories/              # Repository Layer (Data Access)
│       │   ├── 📄 __init__.py
│       │   ├── 📄 base.py               # Base repository with CRUD
│       │   ├── 📄 job_repository.py     # Job-specific queries
│       │   ├── 📄 application_repository.py
│       │   ├── 📄 user_repository.py
│       │   ├── 📄 skill_repository.py
│       │   ├── 📄 company_repository.py
│       │   ├── 📄 watchlist_repository.py
│       │   ├── 📄 resume_repository.py
│       │   └── 📄 analytics_repository.py
│       │
│       ├── 📁 services/                  # Application Layer (Use Cases)
│       │   ├── 📄 __init__.py
│       │   ├── 📄 job_service.py        # Job management
│       │   ├── 📄 application_service.py # Application tracking
│       │   ├── 📄 notification_service.py
│       │   ├── 📄 report_service.py
│       │   ├── 📄 learning_service.py
│       │   ├── 📄 resume_service.py
│       │   ├── 📄 portfolio_service.py
│       │   ├── 📄 interview_service.py
│       │   ├── 📄 watchlist_service.py
│       │   ├── 📄 analytics_service.py
│       │   └── 📄 user_service.py
│       │
│       ├── 📁 engines/                   # AI Engines (17 Engines)
│       │   ├── 📄 __init__.py
│       │   ├── 📄 base.py               # Base engine class
│       │   ├── 📄 registry.py           # Engine registry
│       │   ├── 📄 deduplication.py      # Deduplication engine
│       │   ├── 📄 verification.py       # Verification engine
│       │   ├── 📄 scam_detection.py     # Scam detection engine
│       │   ├── 📄 resume_engine.py      # Resume analysis engine
│       │   ├── 📄 portfolio_engine.py   # Portfolio analysis engine
│       │   ├── 📄 interview_engine.py   # Interview prep engine
│       │   ├── 📄 skill_market.py       # Skill market trends engine
│       │   ├── 📄 salary_engine.py      # Salary estimation engine
│       │   ├── 📄 hiring_calendar.py    # Hiring calendar engine
│       │   ├── 📄 prediction.py         # Prediction engine
│       │   ├── 📄 cyber_news.py         # Cyber news engine
│       │   ├── 📄 certification.py      # Certification tracking engine
│       │   ├── 📄 ctf.py                # CTF tracking engine
│       │   ├── 📄 bug_bounty.py         # Bug bounty tracking engine
│       │   ├── 📄 events.py             # Event tracking engine
│       │   ├── 📄 learning.py           # Learning recommendation engine
│       │   └── 📄 classification.py     # Classification engine
│       │
│       ├── 📁 scrapers/                  # Scraping Infrastructure (40+ Sources)
│       │   ├── 📄 __init__.py
│       │   ├── 📄 base.py               # Base scraper class
│       │   ├── 📄 registry.py           # Scraper registry
│       │   │
│       │   ├── 📁 india/                # India-specific scrapers
│       │   │   ├── 📄 __init__.py
│       │   │   ├── 📄 naukri.py
│       │   │   ├── 📄 foundit.py
│       │   │   ├── 📄 internshala.py
│       │   │   ├── 📄 unstop.py
│       │   │   ├── 📄 freshersworld.py
│       │   │   ├── 📄 aicte.py
│       │   │   └── 📄 government.py    # CERT-In, CDAC, NIC, DRDO, ISRO, BEL, BHEL
│       │   │
│       │   ├── 📁 usa/                  # USA-specific scrapers
│       │   │   ├── 📄 __init__.py
│       │   │   ├── 📄 linkedin.py
│       │   │   ├── 📄 indeed.py
│       │   │   └── 📄 glassdoor.py
│       │   │
│       │   ├── 📁 company_careers/      # Company career page scrapers
│       │   │   ├── 📄 __init__.py
│       │   │   ├── 📄 microsoft.py
│       │   │   ├── 📄 google.py
│       │   │   ├── 📄 amazon.py
│       │   │   ├── 📄 cisco.py
│       │   │   ├── 📄 ibm.py
│       │   │   ├── 📄 oracle.py
│       │   │   ├── 📄 crowdstrike.py
│       │   │   ├── 📄 palo_alto.py
│       │   │   ├── 📄 fortinet.py
│       │   │   ├── 📄 checkpoint.py
│       │   │   ├── 📄 rapid7.py
│       │   │   ├── 📄 qualys.py
│       │   │   ├── 📄 tenable.py
│       │   │   ├── 📄 cloudflare.py
│       │   │   ├── 📄 zscaler.py
│       │   │   ├── 📄 datadog.py
│       │   │   ├── 📄 elastic.py
│       │   │   ├── 📄 splunk.py
│       │   │   ├── 📄 openai.py
│       │   │   └── 📄 anthropic.py
│       │   │
│       │   ├── 📁 global/               # Global/multi-source scrapers
│       │   │   ├── 📄 __init__.py
│       │   │   ├── 📄 remoteok.py
│       │   │   ├── 📄 hackernews.py
│       │   │   ├── 📄 we_work_remotely.py
│       │   │   ├── 📄 google_jobs.py
│       │   │   └── 📄 rss_feeds.py
│       │   │
│       │   ├── 📁 security_platforms/   # Security community scrapers
│       │   │   ├── 📄 __init__.py
│       │   │   ├── 📄 owasp.py
│       │   │   ├── 📄 github.py
│       │   │   └── 📄 gitlab.py
│       │   │
│       │   ├── 📁 ctf_platforms/        # CTF competition scrapers
│       │   │   ├── 📄 __init__.py
│       │   │   ├── 📄 ctftime.py
│       │   │   └── 📄 hackthebox.py
│       │   │
│       │   ├── 📁 bug_bounty_platforms/ # Bug bounty platform scrapers
│       │   │   ├── 📄 __init__.py
│       │   │   ├── 📄 hackerone.py
│       │   │   ├── 📄 bugcrowd.py
│       │   │   └── 📄_intigriti.py
│       │   │
│       │   ├── 📁 learning_platforms/   # Learning platform scrapers
│       │   │   ├── 📄 __init__.py
│       │   │   ├── 📄 tryhackme.py
│       │   │   ├── 📄 hackthebox.py
│       │   │   ├── 📄 portswigger.py
│       │   │   ├── 📄 picoctf.py
│       │   │   └── 📄 overthewire.py
│       │   │
│       │   └── 📁 news_sources/         # Cybersecurity news scrapers
│       │       ├── 📄 __init__.py
│       │       ├── 📄 bleeping_computer.py
│       │       ├── 📄 the_hacker_news.py
│       │       └── 📄 security_week.py
│       │
│       ├── 📁 notifications/             # Notification Infrastructure
│       │   ├── 📄 __init__.py
│       │   ├── 📄 base.py               # Base notification channel
│       │   ├── 📄 manager.py            # Notification manager
│       │   ├── 📄 telegram.py
│       │   ├── 📄 email.py
│       │   ├── 📄 discord.py
│       │   ├── 📄 slack.py
│       │   ├── 📄 push.py               # Web push notifications
│       │   └── 📄 templates/            # Message templates
│       │       ├── 📄 instant_alert.html
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
│       ├── 📁 resume/                    # Resume Processing
│       │   ├── 📄 __init__.py
│       │   ├── 📄 parser.py             # Resume parser (PDF/DOCX)
│       │   ├── 📄 extractor.py          # Skill/experience extractor
│       │   ├── 📄 matcher.py            # Resume-job matcher
│       │   └── 📄 scorer.py             # ATS score calculator
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
│       │   │   ├── 📄 dashboard.py
│       │   │   ├── 📄 resume.py
│       │   │   ├── 📄 watchlist.py
│       │   │   ├── 📄 analytics.py
│       │   │   ├── 📄 interviews.py
│       │   │   ├── 📄 ctf.py
│       │   │   ├── 📄 bug_bounty.py
│       │   │   └── 📄 events.py
│       │   └── 📁 schemas/              # Pydantic schemas
│       │       ├── 📄 __init__.py
│       │       ├── 📄 job.py
│       │       ├── 📄 application.py
│       │       ├── 📄 report.py
│       │       ├── 📄 notification.py
│       │       ├── 📄 resume.py
│       │       ├── 📄 watchlist.py
│       │       └── 📄 analytics.py
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
│       └── 📁 utils/                     # Utilities
│           ├── 📄 __init__.py
│           ├── 📄 logger.py             # Structured logging
│           ├── 📄 cache.py              # Cache utilities
│           ├── 📄 encryption.py         # Secret management
│           ├── 📄 helpers.py            # General helpers
│           ├── 📄 text_processing.py    # NLP text processing
│           └── 📄 rate_limiter.py       # Rate limiting
│
├── 📁 dashboard/                         # Streamlit Dashboard
│   ├── 📄 app.py                         # Dashboard entry
│   ├── 📁 pages/                         # Dashboard pages
│   │   ├── 📄 1_📊_overview.py
│   │   ├── 📄 2_💼_jobs.py
│   │   ├── 📄 3_📋_applications.py
│   │   ├── 📄 4_📈_analytics.py
│   │   ├── 📄 5_📚_learning.py
│   │   ├── 📄 6_🎯_interviews.py
│   │   ├── 📄 7_🏆_ctf.py
│   │   ├── 📄 8_💰_bug_bounty.py
│   │   ├── 📄 9_📅_events.py
│   │   ├── 📄 10_📰_cyber_news.py
│   │   ├── 📄 11_🔔_notifications.py
│   │   ├── 📄 12_⚙️_settings.py
│   │   └── 📄 13_📊_salary_insights.py
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
│   │   ├── 📄 test_scam_detection.py
│   │   ├── 📄 test_resume_engine.py
│   │   ├── 📄 test_salary_engine.py
│   │   ├── 📄 test_notification_service.py
│   │   ├── 📄 test_watchlist_service.py
│   │   └── 📄 test_analytics_service.py
│   ├── 📁 integration/
│   │   ├── 📄 __init__.py
│   │   ├── 📄 test_api.py
│   │   └── 📄 test_scrapers.py
│   └── 📁 fixtures/                      # Test data
│       ├── 📄 jobs.json
│       ├── 📄 applications.json
│       └── 📄 resumes/
│
├── 📁 docs/                              # Documentation
│   ├── 📁 cscip/                         # CSCIP-specific docs
│   │   ├── 📄 01-software-architecture.md
│   │   ├── 📄 02-folder-structure.md
│   │   ├── 📄 03-database-schema.md
│   │   ├── 📄 04-er-diagram.md
│   │   ├── 📄 05-api-design.md
│   │   ├── 📄 06-scheduler.md
│   │   ├── 📄 07-discovery-engine.md
│   │   ├── 📄 08-verification-engine.md
│   │   ├── 📄 09-deduplication-engine.md
│   │   ├── 📄 10-scam-detection-engine.md
│   │   ├── 📄 11-ai-classification.md
│   │   ├── 📄 12-notification-engine.md
│   │   ├── 📄 13-dashboard.md
│   │   ├── 📄 14-resume-engine.md
│   │   ├── 📄 15-deployment.md
│   │   ├── 📄 16-docker.md
│   │   ├── 📄 17-cicd.md
│   │   └── 📄 18-testing.md
│   └── 📁 existing/                      # InternTrack docs
│
├── 📁 scripts/                           # Utility Scripts
│   ├── 📄 seed_data.py                   # Database seeding
│   ├── 📄 export_jobs.py                 # Export utilities
│   └── 📄 setup.py                       # Initial setup
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

## File Count Summary

| Directory | Files | Purpose |
|-----------|-------|---------|
| `domain/` | 5 | Core business logic |
| `repositories/` | 8 | Data access layer |
| `services/` | 11 | Business services |
| `engines/` | 18 | 17 AI engines + base |
| `scrapers/` | 35+ | 40+ source scrapers |
| `notifications/` | 7 | Notification channels |
| `reports/` | 4 | Report generation |
| `resume/` | 4 | Resume processing |
| `api/` | 15 | API endpoints |
| `dashboard/` | 15 | Dashboard pages |
| `tests/` | 15+ | Test files |
| `docs/` | 18 | Documentation |
| **Total** | **~160** | **Complete platform** |

---

## Key Design Decisions

### 1. Regional Scrapers Organization
```
scrapers/
├── india/          # India-specific sources
├── usa/            # USA-specific sources
├── company_careers/ # Major company career pages
├── global/         # Multi-country sources
├── security_platforms/ # Security community
├── ctf_platforms/  # CTF competitions
├── bug_bounty_platforms/ # Bug bounty programs
├── learning_platforms/ # Learning resources
└── news_sources/   # Cybersecurity news
```

### 2. AI Engines as Separate Modules
Each engine is independent and can be:
- Tested in isolation
- Scaled independently
- Replaced without affecting others

### 3. Event-Driven Communication
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Scraper   │────▶│  Event Bus  │────▶│   Engine    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Notification│
                    └─────────────┘
```

---

**Module Status**: ✅ Complete

**Next Module**: [Module 3: Database Schema](./03-database-schema.md)
