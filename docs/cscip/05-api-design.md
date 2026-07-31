# CyberShield Career Intelligence Platform (CSCIP) - API Design

## Overview

CSCIP provides a RESTful API built with FastAPI. The API follows REST conventions with proper HTTP methods, status codes, and comprehensive error handling.

---

## Base URL

```
Development: http://localhost:8000/api/v1
Production:  https://api.cybershield.dev/api/v1
```

## Authentication

API Key authentication via header:
```
X-API-Key: your-api-key
```

---

## Response Format

### Success Response
```json
{
    "success": true,
    "data": { ... },
    "meta": {
        "total": 100,
        "skip": 0,
        "limit": 20,
        "has_more": true
    }
}
```

### Error Response
```json
{
    "success": false,
    "error": {
        "code": "NOT_FOUND",
        "message": "Resource not found",
        "details": {
            "resource": "job",
            "identifier": "123"
        }
    }
}
```

### Paginated Response
```json
{
    "success": true,
    "data": [...],
    "pagination": {
        "total": 150,
        "page": 1,
        "per_page": 20,
        "total_pages": 8,
        "has_next": true,
        "has_prev": false
    }
}
```

---

## API Endpoints

### 1. Jobs API

#### List Jobs
```
GET /api/v1/jobs/
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| skip | int | 0 | Pagination offset |
| limit | int | 20 | Items per page (max: 100) |
| job_type | string | null | Filter: internship, full_time, etc. |
| experience_level | string | null | Filter: entry, junior, mid, senior |
| country | string | null | Filter: India, USA, etc. |
| city | string | null | Filter by city |
| is_remote | boolean | null | Filter remote jobs |
| work_mode | string | null | Filter: remote, hybrid, onsite |
| company | string | null | Filter by company name |
| source | string | null | Filter by source |
| min_salary | int | null | Minimum salary filter |
| max_salary | int | null | Maximum salary filter |
| skills | string | null | Comma-separated skill filter |
| deadline_before | datetime | null | Deadline filter |
| is_verified | boolean | null | Verified jobs only |
| sort_by | string | created_at | Sort field |
| sort_order | string | desc | Sort direction |

**Response:** `200 OK`
```json
{
    "success": true,
    "data": [
        {
            "id": "uuid",
            "title": "SOC Analyst Intern",
            "company": "CrowdStrike",
            "location": "Bangalore, India",
            "country": "India",
            "job_type": "internship",
            "experience_level": "entry",
            "salary_min": 25000,
            "salary_max": 40000,
            "salary_currency": "INR",
            "is_remote": false,
            "work_mode": "hybrid",
            "deadline": "2026-08-15T00:00:00Z",
            "required_skills": ["SOC", "SIEM", "Linux"],
            "preferred_skills": ["Splunk", "Python"],
            "scam_score": 5,
            "is_verified": true,
            "posted_at": "2026-07-25T10:00:00Z"
        }
    ],
    "pagination": {
        "total": 150,
        "page": 1,
        "per_page": 20,
        "total_pages": 8
    }
}
```

---

#### Get Job Details
```
GET /api/v1/jobs/{job_id}
```

**Response:** `200 OK` - Full job details with company info, scam score, salary estimate

---

#### Create Job (Manual)
```
POST /api/v1/jobs/
```

**Request Body:**
```json
{
    "title": "Security Analyst",
    "company": "TechCorp",
    "url": "https://example.com/job/123",
    "description": "Job description...",
    "job_type": "full_time",
    "country": "USA",
    "is_remote": true
}
```

**Response:** `201 Created`

---

#### Update Job
```
PUT /api/v1/jobs/{job_id}
```

---

#### Delete Job
```
DELETE /api/v1/jobs/{job_id}
```

**Response:** `204 No Content`

---

#### Search Jobs
```
POST /api/v1/jobs/search
```

**Request Body:**
```json
{
    "query": "SOC analyst cybersecurity",
    "filters": {
        "country": "India",
        "job_type": "internship",
        "is_remote": false
    },
    "sort_by": "relevance",
    "limit": 50
}
```

---

#### Run Job Discovery
```
POST /api/v1/jobs/discovery/run
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| source | string | Specific source (optional) |
| query | string | Search query |
| country | string | Target country |

**Response:**
```json
{
    "success": true,
    "data": {
        "discovered": 150,
        "unique": 120,
        "saved": 115,
        "scam_detected": 5
    }
}
```

---

#### Job Statistics
```
GET /api/v1/jobs/stats/overview
```

**Response:**
```json
{
    "success": true,
    "data": {
        "total_jobs": 5000,
        "active_jobs": 4500,
        "internships": 1200,
        "remote_jobs": 800,
        "countries": {
            "India": 3000,
            "USA": 2000
        },
        "salary_stats": {
            "min": 15000,
            "max": 250000,
            "avg_min": 45000,
            "avg_max": 85000
        },
        "top_skills": [
            {"skill": "Python", "count": 1500},
            {"skill": "SOC", "count": 1200}
        ],
        "top_companies": [
            {"company": "CrowdStrike", "jobs": 50},
            {"company": "Palo Alto", "jobs": 45}
        ]
    }
}
```

---

### 2. Applications API

#### List Applications
```
GET /api/v1/applications/
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| status | string | Filter by status |
| skip | int | Pagination offset |
| limit | int | Items per page |

---

#### Create Application
```
POST /api/v1/applications/
```

**Request Body:**
```json
{
    "job_id": "uuid",
    "status": "saved",
    "notes": "Interested in this role",
    "priority": 3
}
```

---

#### Update Application Status
```
PATCH /api/v1/applications/{application_id}/status
```

**Request Body:**
```json
{
    "status": "applied",
    "notes": "Applied via company website"
}
```

---

#### Application Metrics
```
GET /api/v1/applications/metrics/overview
```

**Response:**
```json
{
    "success": true,
    "data": {
        "total_applications": 50,
        "status_counts": {
            "saved": 10,
            "applied": 25,
            "interview": 10,
            "assessment": 3,
            "rejected": 5,
            "offer": 2
        },
        "response_rate": 45.5,
        "interview_rate": 22.2,
        "offer_rate": 4.0
    }
}
```

---

#### Application Timeline
```
GET /api/v1/applications/timeline/recent
```

---

### 3. Watchlist API

#### List Watchlists
```
GET /api/v1/watchlists/
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| watch_type | string | Filter: keyword, company, skill |

---

#### Create Watchlist Entry
```
POST /api/v1/watchlists/
```

**Request Body:**
```json
{
    "watch_type": "keyword",
    "value": "SOC Analyst",
    "notification_channels": ["telegram", "email"]
}
```

---

#### Delete Watchlist Entry
```
DELETE /api/v1/watchlists/{watchlist_id}
```

---

#### Get Watchlist Matches
```
GET /api/v1/watchlists/{watchlist_id}/matches
```

---

### 4. Resume API

#### Upload Resume
```
POST /api/v1/resume/upload
```

**Request:** `multipart/form-data`
- `file`: PDF or DOCX file

**Response:**
```json
{
    "success": true,
    "data": {
        "id": "uuid",
        "skills": ["Python", "SOC", "SIEM"],
        "education": [...],
        "experience": [...],
        "parsed_at": "2026-07-30T10:00:00Z"
    }
}
```

---

#### Get Resume Analysis
```
GET /api/v1/resume/{resume_id}/analysis
```

---

#### Match Resume to Jobs
```
POST /api/v1/resume/{resume_id}/match
```

**Request Body:**
```json
{
    "job_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Response:**
```json
{
    "success": true,
    "data": [
        {
            "job_id": "uuid1",
            "match_score": 85.5,
            "matched_skills": ["Python", "SOC"],
            "missing_skills": ["Splunk"],
            "ats_score": 78.0,
            "suggestions": [
                "Add Splunk experience to your resume",
                "Highlight Python automation projects"
            ]
        }
    ]
}
```

---

### 5. Analytics API

#### Skill Market Trends
```
GET /api/v1/analytics/skills/trends
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| period | string | weekly, monthly, yearly |
| category | string | Filter by skill category |

**Response:**
```json
{
    "success": true,
    "data": {
        "trending_up": [
            {"skill": "Kubernetes", "growth": 45.2, "demand": 1200},
            {"skill": "Cloud Security", "growth": 38.5, "demand": 980}
        ],
        "trending_down": [
            {"skill": "Flash", "growth": -85.0, "demand": 10}
        ],
        "stable": [
            {"skill": "Python", "growth": 2.5, "demand": 2500}
        ]
    }
}
```

---

#### Salary Insights
```
GET /api/v1/analytics/salary/insights
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| role | string | Job role |
| country | string | Country |
| experience | string | Experience level |

---

#### Hiring Predictions
```
GET /api/v1/analytics/predictions/hiring
```

---

#### Company Insights
```
GET /api/v1/analytics/companies/{company_id}/insights
```

---

### 6. CTF API

#### List CTF Events
```
GET /api/v1/ctf/
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| upcoming | boolean | Only upcoming events |
| difficulty | string | Filter by difficulty |

---

#### Get CTF Details
```
GET /api/v1/ctf/{ctf_id}
```

---

### 7. Bug Bounty API

#### List Bug Bounty Programs
```
GET /api/v1/bug-bounty/
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| platform | string | Filter by platform |
| status | string | Filter: active, paused, ended |
| min_bounty | int | Minimum bounty filter |

---

#### Get Program Details
```
GET /api/v1/bug-bounty/{program_id}
```

---

### 8. Events API

#### List Events
```
GET /api/v1/events/
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| event_type | string | conference, meetup, workshop, webinar |
| upcoming | boolean | Only upcoming events |
| is_free | boolean | Free events only |

---

### 9. Certifications API

#### List Certifications
```
GET /api/v1/certifications/
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| provider | string | Filter by provider |
| voucher_available | boolean | Free vouchers only |

---

### 10. Interview Prep API

#### Generate Interview Questions
```
POST /api/v1/interviews/generate
```

**Request Body:**
```json
{
    "company_id": "uuid",
    "role": "SOC Analyst",
    "question_types": ["technical", "hr", "scenario"]
}
```

---

#### Get Interview Prep
```
GET /api/v1/interviews/{prep_id}
```

---

### 11. Learning API

#### Get Learning Recommendations
```
GET /api/v1/learning/recommendations
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| skill | string | Target skill |
| level | string | Difficulty level |

---

#### List Learning Paths
```
GET /api/v1/learning/paths
```

---

### 12. Notifications API

#### Get Notification Config
```
GET /api/v1/notifications/config
```

---

#### Update Notification Config
```
PUT /api/v1/notifications/config
```

**Request Body:**
```json
{
    "telegram": {
        "enabled": true,
        "bot_token": "...",
        "chat_id": "..."
    },
    "email": {
        "enabled": true,
        "smtp_user": "...",
        "smtp_password": "..."
    }
}
```

---

#### Test Notification
```
POST /api/v1/notifications/test
```

**Request Body:**
```json
{
    "channels": ["telegram", "email"],
    "message": "Test notification from CSCIP"
}
```

---

### 13. Reports API

#### Generate Daily Report
```
GET /api/v1/reports/daily
```

---

#### Generate Weekly Report
```
GET /api/v1/reports/weekly
```

---

#### Generate Monthly Report
```
GET /api/v1/reports/monthly
```

---

### 14. Dashboard API

#### Get Dashboard Overview
```
GET /api/v1/dashboard/overview
```

**Response:**
```json
{
    "success": true,
    "data": {
        "jobs": {
            "total": 5000,
            "new_today": 150,
            "closing_soon": 45
        },
        "applications": {
            "total": 50,
            "pending": 30,
            "interviews": 10
        },
        "watchlist_matches": 25,
        "upcoming_events": {
            "ctfs": 5,
            "meetups": 8
        }
    }
}
```

---

#### Get Chart Data
```
GET /api/v1/dashboard/charts/{chart_type}
```

**Chart Types:**
- `job-types` - Job type distribution
- `applications-timeline` - Application timeline
- `top-companies` - Top hiring companies
- `salary-distribution` - Salary distribution
- `skill-demand` - Skill demand chart
- `geographic` - Geographic distribution

---

### 15. User API

#### Get User Profile
```
GET /api/v1/users/me
```

---

#### Update User Profile
```
PUT /api/v1/users/me
```

**Request Body:**
```json
{
    "full_name": "John Doe",
    "country": "India",
    "target_role": "SOC Analyst",
    "experience_level": "junior"
}
```

---

## WebSocket Endpoints

### Real-time Notifications
```
ws://localhost:8000/ws/notifications
```

**Events:**
```json
{
    "type": "new_job_match",
    "data": {
        "job_id": "uuid",
        "title": "SOC Analyst",
        "company": "CrowdStrike",
        "match_score": 92.5
    }
}
```

---

## Rate Limiting

| Endpoint Category | Rate Limit |
|-------------------|------------|
| General API | 100 requests/minute |
| Job Discovery | 10 requests/minute |
| Resume Upload | 5 requests/hour |
| Notification Test | 3 requests/hour |

---

## Error Codes

| Code | Status | Description |
|------|--------|-------------|
| NOT_FOUND | 404 | Resource not found |
| VALIDATION_ERROR | 422 | Input validation failed |
| DUPLICATE_JOB | 409 | Job already exists |
| SCAM_DETECTED | 403 | Job flagged as scam |
| RATE_LIMITED | 429 | Too many requests |
| UNAUTHORIZED | 401 | Invalid API key |
| INTERNAL_ERROR | 500 | Server error |

---

## API Versioning

The API is versioned under `/api/v1/`. Future versions will be `/api/v2/`, etc.

Deprecation notice will be provided 6 months before any endpoint removal.

---

**Module Status**: ✅ Complete

**Next Module**: [Module 6: Scheduler](./06-scheduler.md)
