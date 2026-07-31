# CyberShield Career Intelligence Platform (CSCIP) - ER Diagram

## Complete Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        CSCIP ENTITY RELATIONSHIP DIAGRAM                                             │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                      │
│                                            ┌─────────────────────┐                                                    │
│                                            │       users         │                                                    │
│                                            ├─────────────────────┤                                                    │
│                                            │ PK id               │                                                    │
│                                            │    email            │                                                    │
│                                            │    username         │                                                    │
│                                            │    hashed_password  │                                                    │
│                                            │    full_name        │                                                    │
│                                            │    country          │                                                    │
│                                            │    target_role      │                                                    │
│                                            │    experience_level │                                                    │
│                                            │    is_active        │                                                    │
│                                            │    is_verified      │                                                    │
│                                            │    created_at       │                                                    │
│                                            │    updated_at       │                                                    │
│                                            └─────────┬───────────┘                                                    │
│                                                      │                                                                │
│          ┌───────────────────┬───────────────────┬────┴────┬───────────────────┬───────────────────┬──────────────┐  │
│          │                   │                   │         │                   │                   │              │  │
│          ▼                   ▼                   ▼         ▼                   ▼                   ▼              │  │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────┐  │  │
│ │  applications   │ │   watchlists    │ │ resume_data │ │  user_skills    │ │ notification_   │ │ bookmarks   │  │  │
│ ├─────────────────┤ ├─────────────────┤ ├─────────────┤ ├─────────────────┤ │ config          │ ├─────────────┤  │  │
│ │ PK id           │ │ PK id           │ │ PK id       │ │ PK user_id      │ ├─────────────────┤ │ PK id       │  │  │
│ │ FK user_id ─────│─│ FK user_id      │ │ FK user_id  │ │ PK skill_id ────│─│ PK id           │ │ FK user_id  │  │  │
│ │ FK job_id ──────│─│    watch_type   │ │    file_path│ │    proficiency  │ │ FK user_id      │ │    item_type│  │  │
│ │    status       │ │    value        │ │    file_hash│ │    last_used    │ │    channel      │ │    item_id  │  │  │
│ │    applied_at   │ │    is_active    │ │    skills   │ │    is_learning  │ │    is_enabled   │ │    notes    │  │  │
│ │    interview_at │ │    notification │ │    education│ │    created_at   │ │    config       │ │    tags     │  │  │
│ │    notes        │ │    match_count  │ │    experience│ │    updated_at   │ │    last_notified│ │    created  │  │  │
│ │    resume_ver   │ │    last_matched │ │    projects │ └─────────────────┘ │    created_at   │ └─────────────┘  │  │
│ │    cover_letter │ │    created_at   │ │    certs    │                     │    updated_at   │                   │  │
│ │    priority     │ │    updated_at   │ │    github   │                     └─────────────────┘                   │  │
│ │    reminded     │ └─────────────────┘ │    linkedin │                                                         │  │
│ │    match_score  │                     │    parsed_at│                                                         │  │
│ │    ats_score    │                     │    created  │                                                         │  │
│ │    created_at   │                     │    updated  │                                                         │  │
│ │    updated_at   │                     └──────┬──────┘                                                         │  │
│ └────────┬────────┘                            │                                                                  │  │
│          │                                     │                                                                  │  │
│          │                                     │                                                                  │  │
│          ▼                                     │                                                                  │  │
│ ┌─────────────────┐                           │                                                                  │  │
│ │     jobs        │◄──────────────────────────┘                                                                  │  │
│ ├─────────────────┤                                                                                              │  │
│ │ PK id           │                                                                                              │  │
│ │ FK company_id ──│──┐                                                                                           │  │
│ │    title        │  │                                                                                           │  │
│ │    company      │  │                                                                                           │  │
│ │    department   │  │                                                                                           │  │
│ │    job_id_ext   │  │                                                                                           │  │
│ │    description  │  │                                                                                           │  │
│ │    url          │  │                                                                                           │  │
│ │    apply_url    │  │                                                                                           │  │
│ │    source       │  │                                                                                           │  │
│ │    source_url   │  │                                                                                           │  │
│ │    job_type     │  │                                                                                           │  │
│ │    exp_level    │  │                                                                                           │  │
│ │    salary_min   │  │                                                                                           │  │
│ │    salary_max   │  │                                                                                           │  │
│ │    currency     │  │                                                                                           │  │
│ │    location     │  │                                                                                           │  │
│ │    country      │  │                                                                                           │  │
│ │    city         │  │                                                                                           │  │
│ │    is_remote    │  │                                                                                           │  │
│ │    work_mode    │  │                                                                                           │  │
│ │    duration     │  │                                                                                           │  │
│ │    deadline     │  │                                                                                           │  │
│ │    openings     │  │                                                                                           │  │
│ │    eligibility  │  │                                                                                           │  │
│ │    degree       │  │                                                                                           │  │
│ │    branch       │  │                                                                                           │  │
│ │    cgpa_min     │  │                                                                                           │  │
│ │    batch        │  │                                                                                           │  │
│ │    req_skills   │  │                                                                                           │  │
│ │    pref_skills  │  │                                                                                           │  │
│ │    benefits     │  │                                                                                           │  │
│ │    selection    │  │                                                                                           │  │
│ │    interview    │  │                                                                                           │  │
│ │    hr_email     │  │                                                                                           │  │
│ │    recruiter    │  │                                                                                           │  │
│ │    recruiter_in │  │                                                                                           │  │
│ │    hire_mgr     │  │                                                                                           │  │
│ │    company_size │  │                                                                                           │  │
│ │    industry     │  │                                                                                           │  │
│ │    is_active    │  │                                                                                           │  │
│ │    is_verified  │  │                                                                                           │  │
│ │    posted_at    │  │                                                                                           │  │
│ │    expires_at   │  │                                                                                           │  │
│ │    scraped_at   │  │                                                                                           │  │
│ │    raw_data     │  │                                                                                           │  │
│ │    created_at   │  │                                                                                           │  │
│ │    updated_at   │  │                                                                                           │  │
│ └───┬─────┬───────┘  │                                                                                           │  │
│     │     │          │                                                                                           │  │
│     │     │          │                                                                                           │  │
│     │     │          └──────────────────────────────────────────────────────────────────────────────────────────┘  │
│     │     │                                                                                                        │
│     │     │                                                                                                        │
│     │     │    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                                 │
│     │     │    │   companies     │    │ scam_scores     │    │ salary_estimates│                                 │
│     │     │    ├─────────────────┤    ├─────────────────┤    ├─────────────────┤                                 │
│     │     │    │ PK id           │    │ PK id           │    │ PK id           │                                 │
│     │     │    │    name         │    │ FK job_id       │    │ FK job_id       │                                 │
│     │     │    │    website      │    │    scam_score   │    │    est_min      │                                 │
│     │     │    │    career_page  │    │    confidence   │    │    est_max      │                                 │
│     │     │    │    industry     │    │    flags        │    │    currency     │                                 │
│     │     │    │    size         │    │    reasons      │    │    confidence   │                                 │
│     │     │    │    founded_year │    │    is_scam      │    │    city_compare │                                 │
│     │     │    │    headquarters │    │    analyzed_at  │    │    created_at   │                                 │
│     │     │    │    rating       │    │    created_at   │    └─────────────────┘                                 │
│     │     │    │    reviews_cnt  │    └─────────────────┘                                                         │
│     │     │    │    is_watched   │                                                                                │
│     │     │    │    tags         │    ┌─────────────────┐    ┌─────────────────┐                                 │
│     │     │    │    social_links │    │   predictions   │    │  skill_trends   │                                 │
│     │     │    │    created_at   │    ├─────────────────┤    ├─────────────────┤                                 │
│     │     │    │    updated_at   │    │ PK id           │    │ PK id           │                                 │
│     │     │    └────────┬────────┘    │ FK user_id      │    │ FK skill_id     │                                 │
│     │     │             │             │    pred_type     │    │    period       │                                 │
│     │     │             │             │    target_entity │    │    period_start │                                 │
│     │     │             │             │    prediction    │    │    demand_count │                                 │
│     │     │             │             │    confidence    │    │    growth_rate  │                                 │
│     │     │             │             │    valid_until   │    │    avg_salary   │                                 │
│     │     │             │             │    created_at    │    │    top_companies│                                 │
│     │     │             │             └─────────────────┘    │    created_at    │                                 │
│     │     │             │                                     └─────────────────┘                                 │
│     │     │             │                                                                                          │
│     │     │             │    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                   │
│     │     │             │    │ hiring_calendar │    │ news_analyses   │    │ certifications  │                   │
│     │     │             │    ├─────────────────┤    ├─────────────────┤    ├─────────────────┤                   │
│     │     │             │    │ PK id           │    │ PK id           │    │ PK id           │                   │
│     │     │             │    │ FK company_id   │    │    title        │    │    name         │                   │
│     │     │             │    │    month        │    │    source       │    │    provider     │                   │
│     │     │             │    │    year         │    │    url          │    │    url          │                   │
│     │     │             │    │    expected_int │    │    published_at │    │    exam_fee     │                   │
│     │     │             │    │    confidence   │    │    category     │    │    voucher_avail│                   │
│     │     │             │    │    hist_pattern │    │    companies    │    │    voucher_dead │                   │
│     │     │             │    │    created_at   │    │    hire_impact  │    │    student_disc │                   │
│     │     │             │    └─────────────────┘    │    analysis     │    │    validity_yrs │                   │
│     │     │             │                           │    created_at   │    │    difficulty   │                   │
│     │     │             │                           └─────────────────┘    │    prereqs      │                   │
│     │     │             │                                                  │    created_at   │                   │
│     │     │             │                                                  │    updated_at   │                   │
│     │     │             │                                                  └─────────────────┘                   │
│     │     │             │                                                                                          │
│     │     │             │    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                   │
│     │     │             │    │   ctf_events    │    │bug_bounty_progs │    │     events      │                   │
│     │     │             │    ├─────────────────┤    ├─────────────────┤    ├─────────────────┤                   │
│     │     │             │    │ PK id           │    │ PK id           │    │ PK id           │                   │
│     │     │             │    │    name         │    │    company      │    │    name         │                   │
│     │     │             │    │    platform     │    │    platform     │    │    event_type   │                   │
│     │     │             │    │    url          │    │    url          │    │    organizer    │                   │
│     │     │             │    │    start_date   │    │    scope        │    │    url          │                   │
│     │     │             │    │    end_date     │    │    rewards      │    │    location     │                   │
│     │     │             │    │    register_url │    │    min_bounty   │    │    is_virtual   │                   │
│     │     │             │    │    prize        │    │    max_bounty   │    │    start_date   │                   │
│     │     │             │    │    difficulty   │    │    status       │    │    end_date     │                   │
│     │     │             │    │    format       │    │    is_new       │    │    register_url │                   │
│     │     │             │    │    is_registered│    │    last_updated │    │    price        │                   │
│     │     │             │    │    created_at   │    │    created_at   │    │    is_free      │                   │
│     │     │             │    │    updated_at   │    │    updated_at   │    │    topics       │                   │
│     │     │             │    └─────────────────┘    └─────────────────┘    │    created_at   │                   │
│     │     │             │                                                   │    updated_at   │                   │
│     │     │             │                                                   └─────────────────┘                   │
│     │     │             │                                                                                          │
│     │     │             │    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                   │
│     │     │             │    │ learning_paths  │    │ interview_prep  │    │ duplicate_groups│                   │
│     │     │             │    ├─────────────────┤    ├─────────────────┤    ├─────────────────┤                   │
│     │     │             │    │ PK id           │    │ PK id           │    │ PK id           │                   │
│     │     │             │    │    name         │    │ FK user_id      │    │ FK canonical_id │                   │
│     │     │             │    │    description  │    │ FK company_id   │    │ FK duplicate_id │                   │
│     │     │             │    │ FK skill_id     │    │    role         │    │    similarity   │                   │
│     │     │             │    │    resources    │    │    tech_questions│    │    match_type   │                   │
│     │     │             │    │    est_hours    │    │    hr_questions │    │    created_at   │                   │
│     │     │             │    │    difficulty   │    │    scenarios    │    └─────────────────┘                   │
│     │     │             │    │    platform     │    │    company_spec │                                           │
│     │     │             │    │    is_free      │    │    created_at   │                                           │
│     │     │             │    │    url          │    │    updated_at   │                                           │
│     │     │             │    │    created_at   │    └─────────────────┘                                           │
│     │     │             │    └─────────────────┘                                                                   │
│     │     │             │                                                                                          │
│     ▼     ▼             ▼                                                                                          │
│ ┌─────────────────┐                                                                                               │
│ │   job_skills    │                                                                                               │
│ ├─────────────────┤                                                                                               │
│ │ PK FK job_id    │                                                                                               │
│ │ PK FK skill_id  │                                                                                               │
│ │    importance   │                                                                                               │
│ │    is_required  │                                                                                               │
│ └─────────────────┘                                                                                               │
│                                                                                                                      │
│          ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐                                        │
│          │ application_    │    │ analytics_      │    │ activity_log    │                                        │
│          │ status_history  │    │ snapshots       │    │                 │                                        │
│          ├─────────────────┤    ├─────────────────┤    ├─────────────────┤                                        │
│          │ PK id           │    │ PK id           │    │ PK id           │                                        │
│          │ FK application_id│   │    snapshot_type│    │ FK user_id      │                                        │
│          │    old_status   │    │    period       │    │    action       │                                        │
│          │    new_status   │    │    data         │    │    entity_type  │                                        │
│          │    changed_at   │    │    created_at   │    │    entity_id    │                                        │
│          │    notes        │    └─────────────────┘    │    details      │                                        │
│          └─────────────────┘                            │    ip_address   │                                        │
│                                                         │    created_at   │                                        │
│          ┌─────────────────┐    ┌─────────────────┐    └─────────────────┘                                        │
│          │ scheduled_      │    │ generated_      │                                                               │
│          │ reports         │    │ reports         │                                                               │
│          ├─────────────────┤    ├─────────────────┤                                                               │
│          │ PK id           │    │ PK id           │                                                               │
│          │ FK user_id      │    │ FK user_id      │                                                               │
│          │    report_type  │    │    report_type  │                                                               │
│          │    frequency    │    │    period_start │                                                               │
│          │    is_enabled   │    │    period_end   │                                                               │
│          │    last_gen     │    │    data         │                                                               │
│          │    next_gen     │    │    file_path    │                                                               │
│          │    recipients   │    │    sent_via     │                                                               │
│          │    created_at   │    │    created_at   │                                                               │
│          └─────────────────┘    └─────────────────┘                                                               │
│                                                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Relationship Types

### One-to-Many Relationships

| Parent | Child | Relationship |
|--------|-------|--------------|
| users | applications | A user has many applications |
| users | watchlists | A user has many watchlist entries |
| users | bookmarks | A user has many bookmarks |
| users | resume_data | A user has many resumes |
| users | notification_config | A user has many notification configs |
| users | scheduled_reports | A user has many scheduled reports |
| users | activity_log | A user has many activities |
| users | predictions | A user has many predictions |
| users | interview_prep | A user has many interview prep sessions |
| jobs | applications | A job has many applications |
| jobs | scam_scores | A job has one scam score |
| jobs | salary_estimates | A job has one salary estimate |
| jobs | duplicate_groups | A job can be in many duplicate groups |
| companies | jobs | A company has many jobs |
| companies | hiring_calendar | A company has many hiring predictions |
| companies | interview_prep | A company has many interview prep sessions |
| skills | job_skills | A skill is in many job-skill mappings |
| skills | user_skills | A skill is in many user-skill mappings |
| skills | skill_trends | A skill has many trend records |
| skills | learning_paths | A skill has many learning paths |

### Many-to-Many Relationships

| Table 1 | Junction Table | Table 2 |
|---------|----------------|---------|
| jobs | job_skills | skills |
| users | user_skills | skills |

### One-to-One Relationships

| Table 1 | Table 2 | Relationship |
|---------|---------|--------------|
| jobs | scam_scores | Each job has one scam score |
| jobs | salary_estimates | Each job has one salary estimate |

---

## Cascade Rules

| Relationship | On Delete | On Update |
|--------------|-----------|-----------|
| applications → users | CASCADE | CASCADE |
| applications → jobs | CASCADE | CASCADE |
| watchlists → users | CASCADE | CASCADE |
| bookmarks → users | CASCADE | CASCADE |
| job_skills → jobs | CASCADE | CASCADE |
| job_skills → skills | CASCADE | CASCADE |
| user_skills → users | CASCADE | CASCADE |
| user_skills → skills | CASCADE | CASCADE |
| scam_scores → jobs | CASCADE | CASCADE |
| salary_estimates → jobs | CASCADE | CASCADE |
| predictions → users | CASCADE | CASCADE |

---

## Index Strategy

### Primary Indexes (Automatic)
- All primary keys are indexed automatically

### Secondary Indexes
```sql
-- Performance indexes
CREATE INDEX idx_job_company ON jobs(company);
CREATE INDEX idx_job_source ON jobs(source);
CREATE INDEX idx_job_country ON jobs(country);
CREATE INDEX idx_job_type ON jobs(job_type);
CREATE INDEX idx_job_active ON jobs(is_active);
CREATE INDEX idx_job_deadline ON jobs(deadline);
CREATE INDEX idx_job_posted ON jobs(posted_at);

CREATE INDEX idx_application_user ON applications(user_id);
CREATE INDEX idx_application_status ON applications(status);
CREATE INDEX idx_application_job ON applications(job_id);

CREATE INDEX idx_watchlist_user ON watchlists(user_id);
CREATE INDEX idx_watchlist_type_value ON watchlists(watch_type, value);

CREATE INDEX idx_skill_name ON skills(name);
CREATE INDEX idx_company_name ON companies(name);

CREATE INDEX idx_scam_job ON scam_scores(job_id);
CREATE INDEX idx_prediction_user ON predictions(user_id);
```

---

## Data Types Summary

| Type | Usage |
|------|-------|
| VARCHAR(36) | UUID primary keys |
| VARCHAR(255) | Emails, usernames |
| VARCHAR(500) | URLs, names |
| VARCHAR(2000) | Long URLs, descriptions |
| TEXT | Large text fields |
| INTEGER | Counts, scores |
| FLOAT | Percentages, ratings |
| BOOLEAN | Flags |
| DATETIME | Timestamps |
| DATE | Date-only fields |
| JSON | Flexible structured data |
| ENUM | Constrained values |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 5: API Design](./05-api-design.md)
