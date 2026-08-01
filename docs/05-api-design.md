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

## System Endpoints

### Health Check
```
GET /health
```

Runs a database connectivity probe by creating its own session via
`async_session_factory` (so a fully unreachable engine still returns a proper
503, not a 500 from the dependency layer):

- **200 `healthy`** when the DB responds — payload includes `status`,
  `version`, and `database: ok`
- **503 `degraded`** when session creation or the `SELECT 1` probe fails

### Request Metrics
```
GET /metrics
```

Exposes in-memory request metrics collected by `MetricsMiddleware`
(`src/interntrack/metrics.py`) for monitoring and alerting:

```json
{
    "total_requests": 100,
    "total_errors": 2,
    "error_rate": 0.02,
    "avg_latency_ms": 12.345,
    "requests_per_path": {"/api/v1/jobs/": 40},
    "errors_per_path": {"/api/v1/boom": 2},
    "status_codes": {"200": 98, "500": 2}
}
```

- Counts are per-process and reset on restart (lightweight, dependency-free)
- HTTP >= 500 responses count as errors; 4xx are not
- `/metrics` itself is not recorded, and is exempt from rate limiting

### Prometheus Metrics
```
GET /metrics/prometheus
```

Serves the **same** in-memory counters in the Prometheus text exposition
format (`# HELP` / `# TYPE` + labeled samples) so a Prometheus server can
scrape it without requiring the `prometheus_client` library:

```
# HELP interntrack_http_requests_total Total HTTP requests.
# TYPE interntrack_http_requests_total counter
interntrack_http_requests_total 100
# HELP interntrack_http_requests_by_path_total Total HTTP requests per path.
# TYPE interntrack_http_requests_by_path_total counter
interntrack_http_requests_by_path_total{path="/api/v1/jobs/"} 40
# HELP interntrack_http_requests_by_status_total Total HTTP requests per status.
# TYPE interntrack_http_requests_by_status_total counter
interntrack_http_requests_by_status_total{status="200"} 98
# HELP interntrack_http_errors_total Total HTTP 5xx responses.
# TYPE interntrack_http_errors_total counter
interntrack_http_errors_total 2
# HELP interntrack_http_errors_by_path_total Total HTTP 5xx responses per path.
# TYPE interntrack_http_errors_by_path_total counter
interntrack_http_errors_by_path_total{path="/api/v1/boom"} 2
# HELP interntrack_http_error_rate Fraction of requests with 5xx.
# TYPE interntrack_http_error_rate gauge
interntrack_http_error_rate 0.02
# HELP interntrack_http_request_duration_ms Average latency in ms.
# TYPE interntrack_http_request_duration_ms gauge
interntrack_http_request_duration_ms 12.345
```

> Each labeled metric uses its own family name (`*_by_path_total`,
> `*_by_status_total`) so `sum()`/`rate()` never mix label sets and cannot
> double-count across families.

- Label values are escaped per the exposition format (backslash, `"`, newline)
- Response `Content-Type: text/plain; version=0.0.4; charset=utf-8`
- `/metrics/prometheus` is exempt from both metrics recording and rate
  limiting so scrapers stay reliable

#### Local monitoring stack

`docker-compose.yml` ships a Prometheus + Grafana stack (both behind the
`monitoring` profile). Prometheus is pre-configured by
`deploy/prometheus/prometheus.yml` to scrape `api:8000/metrics/prometheus`
every 15s; Grafana is pre-provisioned with a Prometheus datasource (uid
`prometheus`) and an **InternTrack API** dashboard
(`deploy/grafana/dashboards/interntrack.json`) showing request rate, 5xx
error rate, average latency, requests by status code, and top paths:

```bash
docker compose --profile monitoring up -d prometheus grafana
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000 (admin / admin)
```

> **Production:** override the Grafana admin credentials with
> `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` env vars — the default
> `admin`/`admin` is for local dev only. Provisioned dashboards are
> read-only (`allowUiUpdates: false`).

Prometheus also loads **alerting rules** from `deploy/prometheus/alerts.yml`
(`rule_files` in `prometheus.yml`, mounted into the container):

| Alert | Expression (simplified) | Severity | `for` |
|-------|------------------------|----------|-------|
| `HighErrorRate` | 5xx rate / request rate > 0.1 | critical | 5m |
| `HighLatency` | `interntrack_http_request_duration_ms > 1000` | warning | 5m |
| `ServiceDown` | `up{job="interntrack-api"} == 0` | critical | 1m |

View them at `http://localhost:9090/alerts`. Every expression is pinned to
an emitted `interntrack_http_*` metric by `tests/unit/test_prometheus_alerts.py`.

#### Host system monitoring (node-exporter)

The `monitoring` profile also ships a **node-exporter** service
(`prom/node-exporter:v1.8.2`, port 9100, host `/proc`/`/sys`/`/` mounted
read-only) scraped by Prometheus, so host CPU/memory/disk/network metrics are
available:

- `deploy/prometheus/prometheus.yml` adds a `node-exporter` scrape job
- `deploy/prometheus/alerts.yml` adds a `system` alert group:
  `DiskSpaceLow` (critical), `MemoryHigh` (warning), `CpuHigh` (warning)
- `deploy/grafana/dashboards/system.json` — **InternTrack System** dashboard
  (CPU / memory / disk stat panels + network traffic + system load)

```bash
docker compose --profile monitoring up -d prometheus grafana node-exporter
```

> **Linux-host requirement:** node-exporter's `/proc`/`/sys`/`/` host mounts
> behave differently on Docker Desktop for macOS/Windows — the `DiskSpaceLow`,
> `MemoryHigh` and `CpuHigh` alerts and the **InternTrack System** dashboard
> are only representative on Linux hosts (a VM/cloud node or WSL2 backend).

For Kubernetes, the API `Service` (`k8s/raw/06-api.yaml`) carries
`prometheus.io/scrape: "true"` (+ `path`/`port`) annotations for
`kubernetes_sd_configs`-based scraping.

---

## Rate Limiting

### API Request Rate Limiting

InternTrack applies API-level rate limiting via `RateLimitMiddleware`
(`src/interntrack/middleware/rate_limit.py`) using an in-memory sliding window:

| Scope | Limit (default) | Env override |
|-------|-----------------|--------------|
| Per IP | 100 req/min | `RATE_LIMIT_PER_MINUTE` |
| Per API key (`X-API-Key`) | 1000 req/min | `RATE_LIMIT_API_KEY_PER_MINUTE` |

- **Exempt paths:** `/`, `/health`, `/metrics`, `/metrics/prometheus`,
  `/docs`, `/redoc`, `/openapi.json`
- **Disable:** set `RATE_LIMIT_ENABLED=false`

Responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
`X-RateLimit-Reset`; when blocked, `Retry-After` is also sent.

When the limit is exceeded the API returns `429 Too Many Requests` with the
standard error contract:

```json
{
    "error": {
        "code": "RATE_LIMITED",
        "message": "Too many requests. Please try again later.",
        "details": {}
    }
}
```

**Backing store:** when `REDIS_URL` is configured (docker-compose sets
`redis://redis:6379/0`), the middleware uses `RedisRateLimitStore` — an
atomic Lua sliding window over a Redis ZSET (`rl:{key}` + a `:seq` member
counter, both with `EXPIRE`) so limits are **shared across API replicas**.
Without `REDIS_URL`, it uses the in-memory `RateLimitStore` (per-process
limits). On a Redis outage the store falls back to in-memory (once-only
warning, stays degraded until process restart) so the API never fails closed.

### Scraper Rate Limits

Scrapers also apply their own conservative per-source rate limits:

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
