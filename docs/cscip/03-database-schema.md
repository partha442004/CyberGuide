# CyberShield Career Intelligence Platform (CSCIP) - Database Schema

## Overview

CSCIP uses SQLAlchemy 2.0+ with async support. The database supports SQLite (development) and PostgreSQL (production).

---

## Complete Schema (30+ Tables)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CSCIP DATABASE SCHEMA                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     CORE TABLES                                      │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │  │   users      │  │   jobs       │  │ applications │             │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │  │   skills     │  │  companies   │  │  user_skills │             │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     TRACKING TABLES                                  │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │  │  watchlists  │  │  bookmarks   │  │ resume_data  │             │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │  │ applications │  │ notification │  │  user_prefs  │             │   │
│  │  │ _status_hist │  │ _config      │  │              │             │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     AI ENGINE TABLES                                 │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │  │ scam_scores  │  │ predictions  │  │ salary_est   │             │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │  │ skill_trends │  │ hiring_cal   │  │ news_analyses│             │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     EVENT TABLES                                     │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │  │   ctf_events │  │bug_bounty_   │  │  events      │             │   │
│  │  │              │  │programs      │  │  (meetups)   │             │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │  │certifications│  │ learning_    │  │  activity_   │             │   │
│  │  │              │  │ paths        │  │  log         │             │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     REPORTING TABLES                                 │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │  │ scheduled_   │  │ generated_   │  │ analytics_   │             │   │
│  │  │ reports      │  │ reports      │  │ snapshots    │             │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Table Definitions

### 1. users

User accounts and profiles.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| email | VARCHAR(255) | UNIQUE, NOT NULL | User email |
| username | VARCHAR(100) | UNIQUE, NOT NULL | Username |
| hashed_password | VARCHAR(255) | NOT NULL | Bcrypt hash |
| full_name | VARCHAR(200) | NULLABLE | Full name |
| country | VARCHAR(50) | DEFAULT 'India' | Target country |
| target_role | VARCHAR(100) | NULLABLE | Target job role |
| experience_level | ENUM | NULLABLE | entry, junior, mid, senior |
| is_active | BOOLEAN | DEFAULT true | Account status |
| is_verified | BOOLEAN | DEFAULT false | Email verified |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

---

### 2. jobs

Core job listings table (50+ fields).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| title | VARCHAR(500) | NOT NULL | Job title |
| company | VARCHAR(200) | NOT NULL, INDEX | Company name |
| company_id | VARCHAR(36) | FK → companies.id | Company reference |
| department | VARCHAR(100) | NULLABLE | Department |
| job_id_external | VARCHAR(100) | NULLABLE | External job ID |
| description | TEXT | NULLABLE | Full description |
| url | VARCHAR(2000) | NOT NULL, UNIQUE | Job URL |
| apply_url | VARCHAR(2000) | NULLABLE | Official apply URL |
| source | ENUM | NOT NULL | Job source |
| source_url | VARCHAR(2000) | NULLABLE | Source website URL |
| job_type | ENUM | NOT NULL | Job type |
| experience_level | ENUM | NULLABLE | Required experience |
| salary_min | INTEGER | NULLABLE | Minimum salary/stipend |
| salary_max | INTEGER | NULLABLE | Maximum salary/stipend |
| salary_currency | VARCHAR(10) | DEFAULT 'INR' | Currency code |
| location | VARCHAR(200) | NULLABLE | Job location |
| country | VARCHAR(50) | INDEX | Country |
| city | VARCHAR(100) | NULLABLE | City |
| is_remote | BOOLEAN | DEFAULT false | Remote work flag |
| work_mode | ENUM | NULLABLE | remote, hybrid, onsite |
| duration | VARCHAR(50) | NULLABLE | Internship duration |
| deadline | DATETIME | NULLABLE | Application deadline |
| openings | INTEGER | NULLABLE | Number of openings |
| eligibility | JSON | NULLABLE | Eligibility criteria |
| degree | VARCHAR(100) | NULLABLE | Required degree |
| branch | VARCHAR(100) | NULLABLE | Required branch |
| cgpa_min | FLOAT | NULLABLE | Minimum CGPA |
| batch | VARCHAR(50) | NULLABLE | Target batch |
| required_skills | JSON | DEFAULT [] | Required skills |
| preferred_skills | JSON | DEFAULT [] | Preferred skills |
| benefits | JSON | NULLABLE | Job benefits |
| selection_process | TEXT | NULLABLE | Selection process |
| interview_process | TEXT | NULLABLE | Interview process |
| hr_email | VARCHAR(255) | NULLABLE | HR contact email |
| recruiter_name | VARCHAR(200) | NULLABLE | Recruiter name |
| recruiter_linkedin | VARCHAR(500) | NULLABLE | Recruiter LinkedIn |
| hiring_manager | VARCHAR(200) | NULLABLE | Hiring manager |
| company_size | VARCHAR(50) | NULLABLE | Company size |
| industry | VARCHAR(100) | NULLABLE | Industry |
| is_active | BOOLEAN | DEFAULT true | Active status |
| is_verified | BOOLEAN | DEFAULT false | Verified by system |
| posted_at | DATETIME | NULLABLE | When job was posted |
| expires_at | DATETIME | NULLABLE | When job expires |
| scraped_at | DATETIME | NOT NULL | When scraped |
| raw_data | JSON | NULLABLE | Raw scraper data |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

**Indexes:**
- `idx_job_company` on company
- `idx_job_source` on source
- `idx_job_country` on country
- `idx_job_type` on job_type
- `idx_job_active` on is_active
- `idx_job_deadline` on deadline
- `idx_job_posted` on posted_at

---

### 3. applications

Application tracking with Kanban pipeline.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| user_id | VARCHAR(36) | FK → users.id | User reference |
| job_id | VARCHAR(36) | FK → jobs.id | Job reference |
| status | ENUM | NOT NULL | Application status |
| applied_at | DATETIME | NULLABLE | When applied |
| interview_at | DATETIME | NULLABLE | Interview date |
| notes | TEXT | NULLABLE | User notes |
| resume_version | VARCHAR(100) | NULLABLE | Resume version used |
| cover_letter | TEXT | NULLABLE | Cover letter |
| priority | INTEGER | DEFAULT 0 | Priority (0-5) |
| reminded | BOOLEAN | DEFAULT false | Reminder sent |
| resume_match_score | FLOAT | NULLABLE | Resume match % |
| ats_score | FLOAT | NULLABLE | ATS compatibility % |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

**Status Values:**
- `saved` - Saved for later
- `applied` - Application submitted
- `interview` - Interview scheduled
- `assessment` - Assessment in progress
- `rejected` - Rejected
- `offer` - Offer received
- `joined` - Position accepted

---

### 4. companies

Company information and tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| name | VARCHAR(200) | UNIQUE, NOT NULL | Company name |
| website | VARCHAR(500) | NULLABLE | Company website |
| career_page | VARCHAR(500) | NULLABLE | Career page URL |
| industry | VARCHAR(100) | NULLABLE | Industry |
| size | VARCHAR(50) | NULLABLE | Company size |
| founded_year | INTEGER | NULLABLE | Founded year |
| headquarters | VARCHAR(200) | NULLABLE | HQ location |
| rating | FLOAT | NULLABLE | Company rating |
| reviews_count | INTEGER | DEFAULT 0 | Number of reviews |
| is_watched | BOOLEAN | DEFAULT false | In watchlist |
| tags | JSON | DEFAULT [] | Company tags |
| social_links | JSON | NULLABLE | Social media links |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

---

### 5. skills

Skills database for matching and recommendations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| name | VARCHAR(100) | UNIQUE, NOT NULL | Skill name |
| category | ENUM | NOT NULL | Skill category |
| subcategory | VARCHAR(50) | NULLABLE | Subcategory |
| description | TEXT | NULLABLE | Skill description |
| difficulty_level | INTEGER | DEFAULT 1 | Difficulty (1-5) |
| demand_score | FLOAT | DEFAULT 0 | Market demand |
| trend_score | FLOAT | DEFAULT 0 | Trend direction |
| learning_resources | JSON | DEFAULT [] | Learning resources |
| is_active | BOOLEAN | DEFAULT true | Active status |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

**Categories:**
- `programming` - Programming languages
- `framework` - Frameworks/libraries
- `tool` - Development tools
- `certification` - Security certifications
- `soft_skill` - Soft skills
- `domain_knowledge` - Domain expertise

---

### 6. watchlists

Company and keyword watchlists.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| user_id | VARCHAR(36) | FK → users.id | User reference |
| watch_type | ENUM | NOT NULL | keyword, company, skill |
| value | VARCHAR(200) | NOT NULL | Watch value |
| is_active | BOOLEAN | DEFAULT true | Active status |
| notification_channels | JSON | DEFAULT ['telegram'] | Alert channels |
| match_count | INTEGER | DEFAULT 0 | Total matches |
| last_matched | DATETIME | NULLABLE | Last match time |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

**Indexes:**
- `idx_watchlist_user` on user_id
- `idx_watchlist_type_value` on (watch_type, value)

---

### 7. scam_scores

AI-generated scam analysis results.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| job_id | VARCHAR(36) | FK → jobs.id, UNIQUE | Job reference |
| scam_score | FLOAT | NOT NULL | Score 0-100 (100 = scam) |
| confidence | FLOAT | NOT NULL | Confidence 0-1 |
| flags | JSON | DEFAULT [] | Detected flags |
| reasons | JSON | DEFAULT [] | Explanation |
| is_scam | BOOLEAN | DEFAULT false | Is scam (>70 score) |
| analyzed_at | DATETIME | NOT NULL | Analysis timestamp |
| created_at | DATETIME | NOT NULL | Creation timestamp |

---

### 8. resume_data

User resume information.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| user_id | VARCHAR(36) | FK → users.id | User reference |
| file_path | VARCHAR(500) | NULLABLE | Stored file path |
| file_hash | VARCHAR(64) | NOT NULL | File hash for dedup |
| skills | JSON | DEFAULT [] | Extracted skills |
| education | JSON | DEFAULT [] | Education details |
| experience | JSON | DEFAULT [] | Work experience |
| projects | JSON | DEFAULT [] | Projects |
| certifications | JSON | DEFAULT [] | Certifications |
| github_url | VARCHAR(500) | NULLABLE | GitHub profile |
| linkedin_url | VARCHAR(500) | NULLABLE | LinkedIn profile |
| parsed_at | DATETIME | NULLABLE | When parsed |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

---

### 9. predictions

AI prediction results.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| user_id | VARCHAR(36) | FK → users.id | User reference |
| prediction_type | VARCHAR(50) | NOT NULL | Type of prediction |
| target_entity | VARCHAR(100) | NULLABLE | Target company/role |
| prediction | JSON | NOT NULL | Prediction data |
| confidence | FLOAT | NOT NULL | Confidence 0-1 |
| valid_until | DATETIME | NULLABLE | Expiration |
| created_at | DATETIME | NOT NULL | Creation timestamp |

**Prediction Types:**
- `hiring_probability` - Likelihood of hiring
- `opening_predicted` - Predicted job opening
- `company_expansion` - Company growth
- `salary_range` - Expected salary

---

### 10. salary_estimates

AI-estimated salary data.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| job_id | VARCHAR(36) | FK → jobs.id | Job reference |
| estimated_min | INTEGER | NOT NULL | Estimated minimum |
| estimated_max | INTEGER | NOT NULL | Estimated maximum |
| currency | VARCHAR(10) | NOT NULL | Currency code |
| confidence | FLOAT | NOT NULL | Confidence 0-1 |
| city_comparison | JSON | NULLABLE | City-wise comparison |
| created_at | DATETIME | NOT NULL | Creation timestamp |

---

### 11. skill_trends

Skill market trend data.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| skill_id | VARCHAR(36) | FK → skills.id | Skill reference |
| period | ENUM | NOT NULL | weekly, monthly, yearly |
| period_start | DATE | NOT NULL | Period start date |
| demand_count | INTEGER | DEFAULT 0 | Job mentions |
| growth_rate | FLOAT | DEFAULT 0 | Growth % |
| avg_salary | FLOAT | NULLABLE | Average salary |
| top_companies | JSON | DEFAULT [] | Top hiring companies |
| created_at | DATETIME | NOT NULL | Creation timestamp |

---

### 12. hiring_calendar

Predicted hiring cycles.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| company_id | VARCHAR(36) | FK → companies.id | Company reference |
| month | INTEGER | NOT NULL | Month (1-12) |
| year | INTEGER | NOT NULL | Year |
| expected_internships | INTEGER | DEFAULT 0 | Predicted count |
| confidence | FLOAT | NOT NULL | Confidence 0-1 |
| historical_pattern | JSON | NULLABLE | Historical data |
| created_at | DATETIME | NOT NULL | Creation timestamp |

---

### 13. ctf_events

CTF competition tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| name | VARCHAR(200) | NOT NULL | CTF name |
| platform | VARCHAR(100) | NULLABLE | Platform name |
| url | VARCHAR(500) | NOT NULL | CTF URL |
| start_date | DATETIME | NOT NULL | Start time |
| end_date | DATETIME | NOT NULL | End time |
| registration_url | VARCHAR(500) | NULLABLE | Registration link |
| prize | TEXT | NULLABLE | Prize info |
| difficulty | ENUM | NULLABLE | easy, medium, hard, expert |
| format | VARCHAR(50) | NULLABLE | Jeopardy, Attack-Defense, etc. |
| is_registered | BOOLEAN | DEFAULT false | User registered |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

---

### 14. bug_bounty_programs

Bug bounty program tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| company | VARCHAR(200) | NOT NULL | Company name |
| platform | VARCHAR(100) | NULLABLE | Platform (HackerOne, etc.) |
| url | VARCHAR(500) | NOT PROGRAM | Program URL |
| scope | TEXT | NULLABLE | Program scope |
| rewards | JSON | NULLABLE | Reward tiers |
| min_bounty | INTEGER | NULLABLE | Minimum bounty |
| max_bounty | INTEGER | NULLABLE | Maximum bounty |
| status | ENUM | NOT NULL | active, paused, ended |
| is_new | BOOLEAN | DEFAULT true | Recently added |
| last_updated | DATETIME | NULLABLE | Last scope update |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

---

### 15. events

Conferences, meetups, workshops.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| name | VARCHAR(200) | NOT NULL | Event name |
| event_type | ENUM | NOT NULL | conference, meetup, workshop, webinar |
| organizer | VARCHAR(200) | NULLABLE | Organizer name |
| url | VARCHAR(500) | NOT NULL | Event URL |
| location | VARCHAR(200) | NULLABLE | Location |
| is_virtual | BOOLEAN | DEFAULT false | Virtual event |
| start_date | DATETIME | NOT NULL | Start time |
| end_date | DATETIME | NULLABLE | End time |
| registration_url | VARCHAR(500) | NULLABLE | Registration link |
| price | FLOAT | NULLABLE | Ticket price |
| is_free | BOOLEAN | DEFAULT false | Free event |
| topics | JSON | DEFAULT [] | Event topics |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

---

### 16. certifications

Certification tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| name | VARCHAR(200) | NOT NULL | Certification name |
| provider | VARCHAR(100) | NOT NULL | Provider (ISC2, CompTIA, etc.) |
| url | VARCHAR(500) | NULLABLE | Certification URL |
| exam_fee | FLOAT | NULLABLE | Exam fee |
| voucher_available | BOOLEAN | DEFAULT false | Free voucher available |
| voucher_deadline | DATETIME | NULLABLE | Voucher expiry |
| student_discount | BOOLEAN | DEFAULT false | Student discount |
| validity_years | INTEGER | NULLABLE | Validity period |
| difficulty | ENUM | NULLABLE | beginner, intermediate, advanced |
| prerequisites | JSON | NULLABLE | Prerequisites |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

---

### 17. news_analyses

Cybersecurity news analysis.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| title | VARCHAR(500) | NOT NULL | Article title |
| source | VARCHAR(100) | NOT NULL | News source |
| url | VARCHAR(500) | NOT NULL | Article URL |
| published_at | DATETIME | NOT NULL | Publish date |
| category | VARCHAR(50) | NULLABLE | breach, zero-day, threat, etc. |
| companies_mentioned | JSON | DEFAULT [] | Companies in article |
| hiring_impact | FLOAT | NULLABLE | Predicted hiring impact |
| analysis | TEXT | NULLABLE | AI analysis |
| created_at | DATETIME | NOT NULL | Creation timestamp |

---

### 18. learning_paths

Learning path recommendations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| name | VARCHAR(200) | NOT NULL | Path name |
| description | TEXT | NULLABLE | Path description |
| skill_id | VARCHAR(36) | FK → skills.id | Target skill |
| resources | JSON | NOT NULL | Learning resources |
| estimated_hours | INTEGER | NULLABLE | Completion time |
| difficulty_level | INTEGER | DEFAULT 1 | Difficulty (1-5) |
| platform | VARCHAR(50) | NULLABLE | Platform name |
| is_free | BOOLEAN | DEFAULT true | Free resource |
| url | VARCHAR(500) | NULLABLE | Resource URL |
| created_at | DATETIME | NOT NULL | Creation timestamp |

---

### 19. activity_log

User activity tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| user_id | VARCHAR(36) | FK → users.id | User reference |
| action | VARCHAR(100) | NOT NULL | Action performed |
| entity_type | VARCHAR(50) | NOT NULL | Entity type |
| entity_id | VARCHAR(36) | NOT NULL | Entity ID |
| details | JSON | NULLABLE | Action details |
| ip_address | VARCHAR(45) | NULLABLE | Client IP |
| created_at | DATETIME | NOT NULL | Creation timestamp |

---

### 20. notification_config

User notification preferences.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| user_id | VARCHAR(36) | FK → users.id | User reference |
| channel | VARCHAR(50) | NOT NULL | Channel name |
| is_enabled | BOOLEAN | DEFAULT true | Enabled status |
| config | JSON | NOT NULL | Channel config |
| last_notified | DATETIME | NULLABLE | Last notification |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

---

### 21. scheduled_reports

Report scheduling configuration.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| user_id | VARCHAR(36) | FK → users.id | User reference |
| report_type | VARCHAR(50) | NOT NULL | daily, weekly, monthly |
| frequency | VARCHAR(50) | NOT NULL | Cron expression |
| is_enabled | BOOLEAN | DEFAULT true | Enabled status |
| last_generated | DATETIME | NULLABLE | Last generation |
| next_generation | DATETIME | NULLABLE | Next scheduled |
| recipients | JSON | NOT NULL | Recipient channels |
| created_at | DATETIME | NOT NULL | Creation timestamp |

---

### 22. generated_reports

Report generation history.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| user_id | VARCHAR(36) | FK → users.id | User reference |
| report_type | VARCHAR(50) | NOT NULL | Report type |
| period_start | DATE | NOT NULL | Period start |
| period_end | DATE | NOT NULL | Period end |
| data | JSON | NOT NULL | Report data |
| file_path | VARCHAR(500) | NULLABLE | Generated file |
| sent_via | JSON | DEFAULT [] | Delivery channels |
| created_at | DATETIME | NOT NULL | Creation timestamp |

---

### 23. analytics_snapshots

Analytics data snapshots.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| snapshot_type | VARCHAR(50) | NOT NULL | Type of snapshot |
| period | DATE | NOT NULL | Snapshot date |
| data | JSON | NOT NULL | Snapshot data |
| created_at | DATETIME | NOT NULL | Creation timestamp |

---

### 24. job_skills

Many-to-many: jobs ↔ skills.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| job_id | VARCHAR(36) | FK → jobs.id | Job reference |
| skill_id | VARCHAR(36) | FK → skills.id | Skill reference |
| importance | INTEGER | DEFAULT 1 | Importance (1-5) |
| is_required | BOOLEAN | DEFAULT true | Required vs preferred |

**Primary Key:** (job_id, skill_id)

---

### 25. application_status_history

Application status change history.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| application_id | VARCHAR(36) | FK → applications.id | Application reference |
| old_status | ENUM | NULLABLE | Previous status |
| new_status | ENUM | NOT NULL | New status |
| changed_at | DATETIME | NOT NULL | Change timestamp |
| notes | TEXT | NULLABLE | Change notes |

---

### 26. bookmarks

User bookmarks for jobs, companies, etc.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| user_id | VARCHAR(36) | FK → users.id | User reference |
| item_type | VARCHAR(50) | NOT NULL | job, company, ctf, etc. |
| item_id | VARCHAR(36) | NOT NULL | Item ID |
| notes | TEXT | NULLABLE | User notes |
| tags | JSON | DEFAULT [] | Bookmark tags |
| created_at | DATETIME | NOT NULL | Creation timestamp |

---

### 27. user_skills

User skill proficiency tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| user_id | VARCHAR(36) | FK → users.id | User reference |
| skill_id | VARCHAR(36) | FK → skills.id | Skill reference |
| proficiency_level | INTEGER | DEFAULT 1 | Level (1-5) |
| last_used | DATETIME | NULLABLE | Last usage |
| is_learning | BOOLEAN | DEFAULT false | Currently learning |
| created_at | DATETIME | NOT NULL | Creation timestamp |

**Primary Key:** (user_id, skill_id)

---

### 28. resume_match_results

Resume-job match analysis results.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| resume_id | VARCHAR(36) | FK → resume_data.id | Resume reference |
| job_id | VARCHAR(36) | FK → jobs.id | Job reference |
| match_score | FLOAT | NOT NULL | Match percentage |
| matched_skills | JSON | DEFAULT [] | Matched skills |
| missing_skills | JSON | DEFAULT [] | Missing skills |
| ats_score | FLOAT | NULLABLE | ATS compatibility |
| suggestions | JSON | DEFAULT [] | Improvement tips |
| created_at | DATETIME | NOT NULL | Generation timestamp |

---

### 29. interview_prep

Interview preparation data.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| user_id | VARCHAR(36) | FK → users.id | User reference |
| company_id | VARCHAR(36) | FK → companies.id | Company reference |
| role | VARCHAR(200) | NOT NULL | Target role |
| technical_questions | JSON | DEFAULT [] | Technical Q&A |
| hr_questions | JSON | DEFAULT [] | HR Q&A |
| scenario_questions | JSON | DEFAULT [] | Scenario Q&A |
| company_specific | JSON | DEFAULT [] | Company-specific Q&A |
| created_at | DATETIME | NOT NULL | Creation timestamp |
| updated_at | DATETIME | NOT NULL | Last update timestamp |

---

### 30. duplicate_groups

Deduplication tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PK | UUID primary key |
| canonical_job_id | VARCHAR(36) | FK → jobs.id | Original job |
| duplicate_job_id | VARCHAR(36) | FK → jobs.id | Duplicate job |
| similarity_score | FLOAT | NOT NULL | Similarity 0-1 |
| match_type | VARCHAR(50) | NOT NULL | hash, semantic, url |
| created_at | DATETIME | NOT NULL | Detection timestamp |

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ER DIAGRAM                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                              ┌──────────┐                                   │
│                              │   users  │                                   │
│                              └────┬─────┘                                   │
│                                   │                                          │
│         ┌─────────────────────────┼─────────────────────────┐               │
│         │                         │                         │               │
│         ▼                         ▼                         ▼               │
│  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐      │
│  │ applications │          │  watchlists  │          │ resume_data  │      │
│  └──────┬───────┘          └──────────────┘          └──────────────┘      │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐      │
│  │     jobs     │◄────────▶│   companies  │          │    skills    │      │
│  └──────┬───────┘          └──────────────┘          └──────┬───────┘      │
│         │                                                    │              │
│         │           ┌──────────────┐                         │              │
│         │           │ scam_scores  │                         │              │
│         │           └──────────────┘                         │              │
│         │                                                    │              │
│         │           ┌──────────────┐          ┌──────────────┴───────┐      │
│         │           │ predictions  │          │     job_skills       │      │
│         │           └──────────────┘          └──────────────────────┘      │
│         │                                                                    │
│         │           ┌──────────────┐          ┌──────────────┐             │
│         └──────────▶│salary_est    │          │ skill_trends │             │
│                     └──────────────┘          └──────────────┘             │
│                                                                              │
│  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐      │
│  │  ctf_events  │          │bug_bounty_   │          │    events    │      │
│  │              │          │programs      │          │  (meetups)   │      │
│  └──────────────┘          └──────────────┘          └──────────────┘      │
│                                                                              │
│  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐      │
│  │certifications│          │ news_analyses│          │ learning_    │      │
│  │              │          │              │          │ paths        │      │
│  └──────────────┘          └──────────────┘          └──────────────┘      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
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

# Reset database (development only)
rm -f data/cybershield.db
alembic upgrade head
```

---

**Module Status**: ✅ Complete

**Next Module**: [Module 4: ER Diagram](./04-er-diagram.md)
