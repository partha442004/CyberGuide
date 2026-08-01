# InternTrack - API Design

## Overview

InternTrack provides a RESTful API built with FastAPI. The API follows REST conventions with proper HTTP methods and status codes.

---

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently, the API is open for development. In production, API key authentication is recommended:

```
X-API-Key: your-api-key
```

---

## Response Format

### Success Response
```json
{
    "data": { ... },
    "meta": {
        "total": 100,
        "skip": 0,
        "limit": 20
    }
}
```

### Error Response
```json
{
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

### Error Contract

All errors follow one shape: `{ "error": { "code", "message", "details" } }`.

| HTTP Status | `code` | Meaning |
|-------------|--------|---------|
| 400 | `VALIDATION_ERROR` | Bad request / invalid input |
| 404 | `NOT_FOUND` | Resource does not exist |
| 409 | `DUPLICATE` | Conflict (e.g. duplicate job) |
| 422 | `SCRAPING_ERROR` | Upstream scraping/processing failure |
| 502 | `NOTIFICATION_ERROR` | Notification channel failure |
| 500 | `INTERNAL_ERROR` | Unexpected error (debug detail gated) |

> FastAPI's `HTTPException` 4xx responses are preserved by the middleware stack;
> domain `AppException`s surface via a dedicated handler using `exc.status`;
> unexpected exceptions become 500 with a consistent payload.

---

## CORS

CORS is configured via environment variables (see `Settings` in `config.py`):

```env
CORS_ORIGINS=https://app.example.com,https://admin.example.com
CORS_ALLOW_ALL=false
```

- `CORS_ORIGINS` — comma-separated list; each entry is trimmed when parsed
- `CORS_ALLOW_ALL=true` (default) → `allow_origins=["*"]`, `allow_credentials=false`
  (the spec-correct combination for the wildcard)
- Restricted origins → `allow_credentials=true`

Example preflight:
```
OPTIONS /api/v1/jobs/ HTTP/1.1
Origin: https://app.example.com
Access-Control-Request-Method: GET

HTTP/1.1 200 OK
access-control-allow-origin: *
```

---

## Endpoints

### Jobs

#### List Jobs
```
GET /api/v1/jobs/
```

**Query Parameters:**
- `skip` (int, default: 0) - Pagination offset
- `limit` (int, default: 100, max: 200) - Items per page
- `job_type` (string) - Filter by job type
- `is_remote` (boolean) - Filter remote jobs
- `company` (string) - Filter by company

**Response:**
```json
{
    "jobs": [...],
    "total": 100,
    "skip": 0,
    "limit": 100
}
```

---

#### Get Job
```
GET /api/v1/jobs/{job_id}
```

**Response:** Single job object

---

#### Create Job
```
POST /api/v1/jobs/
```

**Request Body:**
```json
{
    "title": "Python Developer",
    "company": "TechCorp",
    "url": "https://example.com/job/123",
    "location": "Remote",
    "description": "Job description...",
    "job_type": "full_time",
    "salary_min": 100000,
    "salary_max": 150000,
    "is_remote": true,
    "tags": ["python", "fastapi"]
}
```

**Response:** 201 Created with job object

---

#### Update Job
```
PUT /api/v1/jobs/{job_id}
```

**Request Body:** Partial job object with fields to update

**Response:** Updated job object

---

#### Delete Job
```
DELETE /api/v1/jobs/{job_id}
```

**Response:** 204 No Content

---

#### Search Jobs
```
POST /api/v1/jobs/search
```

**Request Body:**
```json
{
    "query": "python developer",
    "location": "San Francisco",
    "job_type": "full_time",
    "limit": 50
}
```

**Response:** List of matching jobs

---

#### Job Statistics
```
GET /api/v1/jobs/stats/overview
```

**Response:**
```json
{
    "total_jobs": 150,
    "salary_stats": {
        "min_salary": 50000,
        "max_salary": 250000,
        "avg_min": 95000,
        "avg_max": 145000
    },
    "top_companies": [
        {"company": "TechCorp", "jobs": 15}
    ],
    "job_types": [
        {"type": "full_time", "count": 100}
    ]
}
```

---

#### Jobs Closing Soon
```
GET /api/v1/jobs/closing/soon
```

**Query Parameters:**
- `days` (int, default: 2) - Days until closing

**Response:** List of jobs closing soon

---

#### Run Job Discovery
```
POST /api/v1/jobs/discovery/run
```

**Query Parameters:**
- `source` (string, optional) - Specific source to scrape
- `query` (string, default: "python developer") - Search query

**Response:**
```json
{
    "discovered": 50,
    "saved": 45
}
```

---

### Applications

#### List Applications
```
GET /api/v1/applications/
```

**Query Parameters:**
- `status` (string) - Filter by status
- `skip` (int) - Pagination offset
- `limit` (int) - Items per page

**Response:**
```json
{
    "applications": [...],
    "total": 25
}
```

---

#### Get Application
```
GET /api/v1/applications/{application_id}
```

---

#### Create Application
```
POST /api/v1/applications/
```

**Request Body:**
```json
{
    "job_id": "job-uuid-123"
}
```

**Response:** 201 Created with application object

---

#### Update Application Status
```
PATCH /api/v1/applications/{application_id}/status
```

**Request Body:**
```json
{
    "status": "interview",
    "notes": "Phone screen scheduled"
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
    "total_applications": 25,
    "status_counts": {
        "saved": 5,
        "applied": 10,
        "interview": 5,
        "rejected": 3,
        "offer": 2
    },
    "rejection_rate": 12.5,
    "response_rate": 50.0,
    "recent_applications": 8
}
```

---

#### Application Timeline
```
GET /api/v1/applications/timeline/recent
```

**Query Parameters:**
- `days` (int, default: 30) - Number of days

---

### Reports

#### Daily Report
```
GET /api/v1/reports/daily
```

---

#### Weekly Report
```
GET /api/v1/reports/weekly
```

---

#### Monthly Report
```
GET /api/v1/reports/monthly
```

---

#### Report as HTML
```
GET /api/v1/reports/{report_type}/html
```

**Path Parameters:**
- `report_type` - daily, weekly, or monthly

**Response:** HTML content

---

### Notifications

#### Get Configured Channels
```
GET /api/v1/notifications/channels
```

**Response:**
```json
{
    "channels": ["telegram", "email", "discord"]
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
    "message": "Test notification"
}
```

**Response:**
```json
{
    "results": {
        "telegram": true,
        "email": true
    },
    "configured_channels": ["telegram", "email", "discord"]
}
```

---

### Skills

#### List Skills
```
GET /api/v1/skills/
```

**Query Parameters:**
- `category` (string) - Filter by category
- `search` (string) - Search skills

---

#### Skill Demand
```
GET /api/v1/skills/demand
```

**Response:** Top skills by job demand

---

#### Match Skills
```
POST /api/v1/skills/match
```

**Query Parameters:**
- `job_skills` (list) - Required skills
- `user_skills` (list) - User's skills

---

#### Learning Path
```
GET /api/v1/skills/learning-path
```

**Query Parameters:**
- `current_skills` (list) - User's current skills
- `target_role` (string) - Target role

---

### Dashboard

#### Overview
```
GET /api/v1/dashboard/overview
```

**Response:**
```json
{
    "jobs": { ... },
    "applications": { ... }
}
```

---

#### Charts

```
GET /api/v1/dashboard/charts/job-types
GET /api/v1/dashboard/charts/application-timeline
GET /api/v1/dashboard/charts/top-companies
GET /api/v1/dashboard/charts/salary
```

---

#### Recent Activity
```
GET /api/v1/dashboard/recent-activity
```

---

## Rate Limiting

Rate limits are applied per source for scrapers:

| Source | Rate Limit |
|--------|------------|
| HackerNews | 30 req/min |
| RemoteOK | 30 req/min |
| LinkedIn | 10 req/min |
| Indeed | 15 req/min |
| Glassdoor | 10 req/min |
| RSS Feeds | 60 req/min |

---

## Versioning

The API is versioned under `/api/v1/`. Future versions will be added as `/api/v2/`, etc.

---

**Module Status**: ✅ Complete
