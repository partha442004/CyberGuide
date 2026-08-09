# InternTrack - Database Schema

## Overview

InternTrack uses SQLAlchemy 2.0+ with async support. The database can be SQLite (development) or PostgreSQL (production).

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATABASE SCHEMA                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│      jobs        │       │   applications   │       │ application_     │
├──────────────────┤       ├──────────────────┤       │ status_history   │
│ id (PK)          │◄──┐   │ id (PK)          │◄──┐   ├──────────────────┤
│ title            │   │   │ job_id (FK)      │───┘   │ id (PK)          │
│ company          │   │   │ status           │       │ application_id   │
│ location         │   │   │ applied_at       │       │ old_status       │
│ description      │   │   │ interview_at     │       │ new_status       │
│ url              │   │   │ notes            │       │ changed_at       │
│ source           │   │   │ resume_version   │       │ notes            │
│ job_type         │   │   │ cover_letter     │       └──────────────────┘
│ experience_level │   │   │ priority         │
│ salary_min       │   │   │ reminded         │
│ salary_max       │   │   │ created_at       │
│ salary_currency  │   │   │ updated_at       │
│ is_remote        │   │   └──────────────────┘
│ posted_at        │   │
│ expires_at       │   │   ┌──────────────────┐       ┌──────────────────┐
│ is_active        │   │   │    job_skills    │       │     skills       │
│ tags             │   │   ├──────────────────┤       ├──────────────────┤
│ raw_data         │   │   │ job_id (FK)      │──┐    │ id (PK)          │
│ created_at       │   └───│ skill_id (FK)    │──┼───►│ name             │
│ updated_at       │       │ importance       │  │    │ category         │
└──────────────────┘       └──────────────────┘  │    │ description      │
                                                  │    │ difficulty_level │
                                                  │    │ learning_resources│
                                                  │    │ is_active        │
                                                  │    │ created_at       │
                                                  │    │ updated_at       │
                                                  │    └──────────────────┘
                                                  │
                                                  │    ┌──────────────────┐
                                                  │    │   user_skills    │
                                                  │    ├──────────────────┤
                                                  └───►│ user_id          │
                                                       │ skill_id (FK)    │
                                                       │ proficiency_level│
                                                       │ last_used        │
                                                       │ is_learning      │
                                                       │ created_at       │
                                                       │ updated_at       │
                                                       └──────────────────┘

┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  learning_paths  │       │ notification_    │       │ scheduled_       │
├──────────────────┤       │ config           │       │ reports          │
│ id (PK)          │       ├──────────────────┤       ├──────────────────┤
│ name             │       │ id (PK)          │       │ id (PK)          │
│ description      │       │ channel          │       │ report_type      │
│ skill_id (FK)    │       │ is_enabled       │       │ frequency        │
│ resources        │       │ config           │       │ is_enabled       │
│ estimated_hours  │       │ last_notified    │       │ last_generated   │
│ difficulty_level │       │ created_at       │       │ next_generation  │
│ platform         │       │ updated_at       │       │ recipients       │
│ created_at       │       └──────────────────┘       │ created_at       │
│ updated_at       │                                  │ updated_at       │
└──────────────────┘                                  └──────────────────┘

┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│    companies     │       │    bookmarks     │       │    watchlists    │
├──────────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (PK)          │       │ id (PK)          │       │ id (PK)          │
│ name             │       │ item_type        │       │ watch_type       │
│ website          │       │ item_id          │       │ value            │
│ industry         │       │ notes            │       │ is_active        │
│ size             │       │ tags             │       │ notification_    │
│ rating           │       │ created_at       │       │ channels         │
│ reviews_count    │       │ updated_at       │       │ created_at       │
│ is_watched       │       └──────────────────┘       │ updated_at       │
│ tags             │                                  └──────────────────┘
│ created_at       │
│ updated_at       │       ┌──────────────────┐
└──────────────────┘       │   activity_log   │
                           ├──────────────────┤
                           │ id (PK)          │
                           │ action           │
                           │ entity_type      │
                           │ entity_id        │
                           │ details          │
                           │ created_at       │
                           │ updated_at       │
                           └──────────────────┘
```

---

## Table Definitions

### jobs

The main job listings table.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| title | VARCHAR(500) | NOT NULL | Job title |
| company | VARCHAR(200) | NOT NULL, INDEX | Company name |
| location | VARCHAR(200) | NULLABLE | Job location |
| description | TEXT | NULLABLE | Job description |
| url | VARCHAR(2000) | NOT NULL, UNIQUE | Job URL |
| source | ENUM | NOT NULL | Job source (linkedin, indeed, etc.) |
| job_type | ENUM | NOT NULL | Job type (full_time, internship, etc.) |
| experience_level | ENUM | NULLABLE | Required experience |
| salary_min | INTEGER | NULLABLE | Minimum salary |
| salary_max | INTEGER | NULLABLE | Maximum salary |
| salary_currency | VARCHAR(10) | NULLABLE | Currency code |
| is_remote | BOOLEAN | DEFAULT false | Remote work flag |
| posted_at | DATETIME | NULLABLE | When job was posted |
| expires_at | DATETIME | NULLABLE | When job expires |
| is_active | BOOLEAN | DEFAULT true | Active status |
| tags | JSON | NULLABLE | Skill tags |
| raw_data | JSON | NULLABLE | Raw scraper data |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

**Indexes:**
- `idx_job_company` on company
- `idx_job_source` on source
- `idx_job_active` on is_active

---

### applications

Job application tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| job_id | VARCHAR(36) | FK → jobs.id | Related job |
| status | ENUM | NOT NULL | Application status |
| applied_at | DATETIME | NULLABLE | When application was sent |
| interview_at | DATETIME | NULLABLE | Scheduled interview time |
| notes | TEXT | NULLABLE | User notes |
| resume_version | VARCHAR(100) | NULLABLE | Resume version used |
| cover_letter | TEXT | NULLABLE | Cover letter content |
| priority | INTEGER | DEFAULT 0 | Priority level (0-5) |
| reminded | BOOLEAN | DEFAULT false | Reminder sent flag |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

**Status Values:**
- `saved` - Job saved for later
- `applied` - Application submitted
- `interview` - Interview scheduled
- `assessment` - Assessment/test in progress
- `rejected` - Application rejected
- `offer` - Offer received
- `joined` - Position accepted

**Indexes:**
- `idx_application_status` on status
- `idx_application_job` on job_id

---

### skills

Skills for learning recommendations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| name | VARCHAR(100) | NOT NULL, UNIQUE | Skill name |
| category | ENUM | NOT NULL | Skill category |
| description | TEXT | NULLABLE | Skill description |
| difficulty_level | INTEGER | DEFAULT 1 | Difficulty (1-5) |
| learning_resources | JSON | NULLABLE | Learning resources |
| is_active | BOOLEAN | DEFAULT true | Active status |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

**Categories:**
- `programming` - Programming languages
- `framework` - Frameworks and libraries
- `tool` - Development tools
- `soft_skill` - Soft skills
- `certification` - Certifications
- `language` - Human languages

---

### learning_paths

Learning paths for skill development.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| name | VARCHAR(200) | NOT NULL | Path name |
| description | TEXT | NULLABLE | Path description |
| skill_id | VARCHAR(36) | FK → skills.id | Target skill |
| resources | JSON | NOT NULL | Learning resources |
| estimated_hours | INTEGER | NULLABLE | Estimated completion time |
| difficulty_level | INTEGER | DEFAULT 1 | Difficulty (1-5) |
| platform | VARCHAR(50) | NULLABLE | Learning platform |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

---

## Enums

### JobSource
```python
LINKEDIN = "linkedin"
INDEED = "indeed"
GLASSDOOR = "glassdoor"
REMOTE_OK = "remote_ok"
WE_WORK_REMOTELY = "we_work_remotely"
HACKER_NEWS = "hackernews"
RSS_FEED = "rss_feed"
INTERNSHALA = "internshala"
UNSTOP = "unstop"
NAUKRI = "naukri"
FRESHERWORLD = "freshersworld"
APNA = "apna"
COMPANY = "company"
MANUAL = "manual"
UNKNOWN = "unknown"
```

### JobType
```python
INTERNSHIP = "internship"
FULL_TIME = "full_time"
PART_TIME = "part_time"
CONTRACT = "contract"
FREELANCE = "freelance"
REMOTE = "remote"
UNKNOWN = "unknown"
```

### ApplicationStatus
```python
SAVED = "saved"
APPLIED = "applied"
INTERVIEW = "interview"
ASSESSMENT = "assessment"
REJECTED = "rejected"
OFFER = "offer"
JOINED = "joined"
```

### SkillCategory
```python
PROGRAMMING = "programming"
FRAMEWORK = "framework"
TOOL = "tool"
SOFT_SKILL = "soft_skill"
CERTIFICATION = "certification"
LANGUAGE = "language"
```

---

## Migration

Database migrations are managed with Alembic:

```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Rollback one step
alembic downgrade -1
```

---

**Module Status**: ✅ Complete
