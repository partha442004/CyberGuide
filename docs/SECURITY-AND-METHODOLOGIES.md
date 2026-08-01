# InternTrack - Security & Maintenance Methodologies

> Complete guide for secure development, error prevention, and production maintenance.

---

## 📑 TABLE OF CONTENTS

1. [Development Methodologies](#1-development-methodologies)
2. [Error Prevention](#2-error-prevention)
3. [Security Framework](#3-security-framework)
4. [Code Quality Standards](#4-code-quality-standards)
5. [Testing Methodologies](#5-testing-methodologies)
6. [Deployment Security](#6-deployment-security)
7. [Monitoring & Observability](#7-monitoring--observability)
8. [Backup & Recovery](#8-backup--recovery)
9. [Compliance & Auditing](#9-compliance--auditing)
10. [Incident Response](#10-incident-response)
11. [Maintenance Schedules](#11-maintenance-schedules)
12. [Checklists](#12-checklists)

---

## 1. DEVELOPMENT METHODOLOGIES

### 1.1 Git Workflow (Git Flow)

```
main (production)
  ↑
  ├── develop (integration)
  │     ↑
  │     ├── feature/xxx
  │     ├── feature/yyy
  │     └── feature/zzz
  │
  ├── release/x.x.x
  │
  └── hotfix/xxx
```

#### Branch Naming Convention
```
feature/TICKET-123-add-job-search
bugfix/TICKET-456-fix-deduplication
hotfix/TICKET-789-fix-security-vulnerability
release/1.2.0
```

#### Commit Message Convention
```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance
- `security`: Security fix

**Examples:**
```
feat(jobs): add LinkedIn scraper integration

fix(dedup): prevent duplicate job entries

security(api): add rate limiting to prevent abuse

docs(readme): update installation instructions
```

### 1.2 Code Review Process

#### Pre-Review Checklist
- [ ] Code compiles without errors
- [ ] All tests pass locally
- [ ] Linter shows no errors
- [ ] Type checker shows no errors
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No hardcoded secrets

#### Review Checklist
- [ ] Code follows style guidelines
- [ ] No security vulnerabilities
- [ ] Error handling is proper
- [ ] Tests cover new code
- [ ] Performance is acceptable
- [ ] Documentation is clear

#### Review Best Practices
1. **Be constructive** - Suggest improvements, not just problems
2. **Focus on security** - Always check for vulnerabilities
3. **Check edge cases** - What happens with bad input?
4. **Verify error handling** - Are errors properly caught and logged?
5. **Review tests** - Do tests actually test the right things?

### 1.3 Feature Development Workflow

```
1. Create ticket/issue
2. Create feature branch
3. Write tests first (TDD)
4. Implement feature
5. Run all checks
6. Create pull request
7. Code review
8. Merge to develop
9. Integration testing
10. Merge to main (release)
11. Deploy to production
12. Monitor
```

---

## 2. ERROR PREVENTION

### 2.1 Defensive Programming

#### Input Validation
```python
from pydantic import BaseModel, Field, validator

class JobCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    company: str = Field(..., min_length=1, max_length=200)
    url: HttpUrl

    @validator('title')
    def validate_title(cls, v):
        if '<script>' in v.lower():
            raise ValueError('Invalid characters in title')
        return v.strip()

    @validator('company')
    def validate_company(cls, v):
        return v.strip().title()
```

#### Null Safety
```python
# Bad
async def get_job(job_id: str):
    job = await repo.get_by_id(job_id)
    return job.title  # Could raise AttributeError

# Good
async def get_job(job_id: str):
    job = await repo.get_by_id(job_id)
    if not job:
        raise NotFoundError("Job", job_id)
    return job.title
```

#### Type Safety
```python
# Bad
def calculate_salary(min_salary, max_salary):
    return (min_salary + max_salary) / 2  # Could fail with None

# Good
from typing import Optional

def calculate_salary(
    min_salary: Optional[int],
    max_salary: Optional[int]
) -> Optional[float]:
    if min_salary is None or max_salary is None:
        return None
    return (min_salary + max_salary) / 2
```

### 2.2 Error Handling Patterns

#### Custom Exception Hierarchy
```python
class AppException(Exception):
    """Base application exception."""
    def __init__(self, message: str, code: str, status: int):
        self.message = message
        self.code = code
        self.status = status
        super().__init__(message)

class NotFoundError(AppException):
    def __init__(self, resource: str, id: str):
        super().__init__(
            f"{resource} '{id}' not found",
            "NOT_FOUND",
            404
        )

class ValidationError(AppException):
    def __init__(self, field: str, reason: str):
        super().__init__(
            f"Validation failed for {field}: {reason}",
            "VALIDATION_ERROR",
            422
        )

class ScrapingError(AppException):
    def __init__(self, source: str, reason: str):
        super().__init__(
            f"Scraping failed for {source}: {reason}",
            "SCRAPING_ERROR",
            422
        )
```

#### Global Exception Handler
```python
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )
```

#### Retry Pattern
```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(ScrapingError)
)
async def scrape_with_retry(url: str):
    """Fetch URL with automatic retry on failure."""
    try:
        response = await client.get(url, timeout=30)
        response.raise_for_status()
        return response
    except httpx.TimeoutException:
        raise ScrapingError("source", "Request timed out")
    except httpx.HTTPStatusError as e:
        raise ScrapingError("source", f"HTTP {e.response.status_code}")
```

### 2.3 Data Validation

#### Pydantic Validation
```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List

class JobInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    company: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., max_length=2000)
    salary_min: Optional[int] = Field(None, ge=0, le=10_000_000)
    salary_max: Optional[int] = Field(None, ge=0, le=10_000_000)
    tags: List[str] = Field(default_factory=list)

    @validator('title')
    def sanitize_title(cls, v):
        return v.strip()

    @validator('salary_max')
    def validate_salary_range(cls, v, values):
        if v and values.get('salary_min'):
            if v < values['salary_min']:
                raise ValueError('salary_max must be >= salary_min')
        return v
```

#### Database Validation
```python
from sqlalchemy import event

@event.listens_for(Job, 'before_insert')
def validate_job_before_insert(mapper, connection, job):
    """Validate job data before database insert."""
    if not job.title or len(job.title) < 5:
        raise ValueError("Job title must be at least 5 characters")
    if not job.company:
        raise ValueError("Company name is required")
```

### 2.4 Logging Best Practices

#### Structured Logging
```python
import structlog

logger = structlog.get_logger()

# Good - structured logging
logger.info(
    "job.scraped",
    source="linkedin",
    job_count=15,
    duration_ms=1234,
    success=True
)

logger.error(
    "scrape.failed",
    source="indeed",
    error=str(e),
    retry_count=3,
    exc_info=True
)

# Bad - unstructured logging
print(f"Found {count} jobs")  # Don't do this
```

#### Log Levels
```python
logger.debug("Processing job: %s", job_id)  # Detailed debug info
logger.info("Job saved: %s", job.id)  # Normal operation
logger.warning("Rate limit approaching: %d requests", count)  # Potential issue
logger.error("Scraping failed: %s", error)  # Error occurred
logger.critical("Database connection lost")  # System failure
```

---

## 3. SECURITY FRAMEWORK

### 3.1 Authentication & Authorization

#### API Key Authentication
```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key from header."""
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    return api_key
```

#### JWT Token Authentication
```python
from datetime import datetime, timedelta
from jose import JWTError, jwt

SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def verify_token(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials"
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception
```

### 3.2 Input Sanitization

#### XSS Prevention
```python
import html
import re

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS."""
    # HTML escape
    text = html.escape(text)
    # Remove script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    # Remove event handlers
    text = re.sub(r'\s*on\w+\s*=\s*["\'][^"\']*["\']', '', text)
    return text

def sanitize_html(html_content: str) -> str:
    """Sanitize HTML content while preserving safe tags."""
    from bleach import clean
    allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li']
    return clean(html_content, tags=allowed_tags)
```

#### SQL Injection Prevention
```python
# Always use parameterized queries
# BAD
query = f"SELECT * FROM jobs WHERE title = '{title}'"

# GOOD - SQLAlchemy ORM
jobs = session.query(Job).filter(Job.title == title).all()

# GOOD - Raw query with parameters
result = await session.execute(
    text("SELECT * FROM jobs WHERE title = :title"),
    {"title": title}
)
```

### 3.3 Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/jobs")
@limiter.limit("100/minute")
async def get_jobs(request: Request):
    """Rate limited endpoint."""
    return await job_service.get_jobs()
```

### 3.4 CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

# Production configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourdomain.com",
        "https://www.yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Request-Id"],
    max_age=600
)
```

### 3.5 Secrets Management

#### Environment Variables
```python
# NEVER commit secrets to git
# Use .env file (excluded from git)

# .env.example (committed)
DATABASE_URL=sqlite:///./data.db
SECRET_KEY=change-me
API_KEY=your-api-key

# .env (NOT committed)
DATABASE_URL=postgresql://user:pass@localhost/db
SECRET_KEY=super-secret-key-12345
API_KEY=abc123xyz
```

#### Encryption at Rest
```python
from cryptography.fernet import Fernet

class SecretManager:
    def __init__(self, key: str):
        self.cipher = Fernet(key.encode())

    def encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        return self.cipher.decrypt(encrypted.encode()).decode()

# Usage
manager = SecretManager(settings.encryption_key)
encrypted_api_key = manager.encrypt("sensitive-api-key")
```

### 3.6 HTTPS & TLS

```nginx
# nginx.conf for production
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self'" always;
}
```

### 3.7 Security Headers

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

    return response
```

---

## 4. CODE QUALITY STANDARDS

### 4.1 Python Style Guide (PEP 8 + Extensions)

#### Naming Conventions
```python
# Classes - PascalCase
class JobService:
class ApplicationRepository:

# Functions/Methods - snake_case
def get_job_by_id():
async def create_application():

# Variables - snake_case
job_count = 10
is_valid = True

# Constants - UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 30

# Private methods - leading underscore
def _validate_input():
def _parse_salary():
```

#### Type Hints
```python
from typing import Optional, List, Dict, Any
from uuid import UUID

# Always use type hints
async def get_jobs(
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None
) -> List[Job]:
    """Get jobs with optional filters."""
    pass

# Use proper return types
def calculate_match_score(
    job_skills: List[str],
    user_skills: List[str]
) -> float:
    """Calculate skill match percentage."""
    pass
```

### 4.2 Docstring Standards

#### Google Style Docstrings
```python
async def create_job(self, job_data: dict) -> Job:
    """Create a new job posting.

    Creates a new job listing after checking for duplicates
    and validating the input data.

    Args:
        job_data: Dictionary containing job information with keys:
            - title: Job title (required)
            - company: Company name (required)
            - url: Job posting URL (required)
            - description: Job description (optional)

    Returns:
        The created Job object with assigned ID.

    Raises:
        DuplicateJobError: If a job with same URL already exists.
        ValidationError: If required fields are missing.

    Example:
        >>> job = await service.create_job({
        ...     "title": "Python Developer",
        ...     "company": "TechCorp",
        ...     "url": "https://example.com/job/123"
        ... })
    """
    pass
```

### 4.3 Code Organization

#### File Structure
```
module/
├── __init__.py          # Public API exports
├── models.py            # Data models
├── schemas.py           # Pydantic schemas
├── service.py           # Business logic
├── repository.py        # Data access
├── exceptions.py        # Custom exceptions
├── utils.py             # Helper functions
└── tests/
    ├── __init__.py
    ├── test_service.py
    └── test_repository.py
```

#### Import Order
```python
# 1. Standard library
import os
import sys
from datetime import datetime
from typing import Optional

# 2. Third-party packages
import httpx
import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

# 3. Local application
from interntrack.domain.models import Job
from interntrack.repositories import JobRepository
from interntrack.services import JobService
```

---

## 5. TESTING METHODOLOGIES

### 5.1 Test Pyramid

```
         /\
        /  \        E2E Tests (10%)
       /    \       - Full user flows
      /------\      
     /        \     Integration Tests (20%)
    /          \    - API endpoints
   /            \   - Database operations
  /--------------\  
 /                \ Unit Tests (70%)
/                  \- Functions
/--------------------\- Classes
```

### 5.2 Unit Testing

#### Test Structure
```python
import pytest
from unittest.mock import AsyncMock, patch

class TestJobService:
    """Tests for JobService."""

    @pytest.fixture
    def mock_repo(self):
        """Mock job repository."""
        repo = AsyncMock()
        repo.get_by_id.return_value = None
        repo.get_by_url.return_value = None
        repo.create.return_value = Job(id="123", title="Test Job")
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        """Create service with mocked dependencies."""
        return JobService(session=AsyncMock(), job_repo=mock_repo)

    @pytest.mark.asyncio
    async def test_create_job_success(self, service, mock_repo):
        """Test successful job creation."""
        job_data = {
            "title": "Python Developer",
            "company": "TechCorp",
            "url": "https://example.com/job/1"
        }

        job = await service.create_job(job_data)

        assert job.title == "Python Developer"
        assert job.company == "TechCorp"
        mock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_job_duplicate(self, service, mock_repo):
        """Test duplicate job raises exception."""
        mock_repo.get_by_url.return_value = Job(id="existing")

        with pytest.raises(DuplicateJobError):
            await service.create_job({
                "title": "Test",
                "company": "Test",
                "url": "https://existing.com"
            })
```

### 5.3 Integration Testing

#### API Testing
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_job_api(client: AsyncClient):
    """Test job creation API endpoint."""
    response = await client.post(
        "/api/v1/jobs/",
        json={
            "title": "Test Job",
            "company": "Test Company",
            "url": "https://example.com/job/1"
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Job"
    assert "id" in data

@pytest.mark.asyncio
async def test_get_jobs_api(client: AsyncClient):
    """Test job listing API endpoint."""
    # Create test jobs first
    await client.post("/api/v1/jobs/", json={...})

    response = await client.get("/api/v1/jobs/")

    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "total" in data
```

### 5.4 Test Coverage

```bash
# Run with coverage
pytest --cov=interntrack --cov-report=html

# Coverage requirements
# - Overall: >80%
# - Critical paths: >90%
# - New code: 100%
```

---

## 6. DEPLOYMENT SECURITY

### 6.1 Docker Security

#### Secure Dockerfile
```dockerfile
# Use specific version, not latest
FROM python:3.11-slim

# Don't run as root
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Don't store secrets in image
ENV PYTHONUNBUFFERED=1
# Use build args for secrets, never hardcode
ARG DATABASE_URL
ENV DATABASE_URL=$DATABASE_URL

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use multi-stage builds
FROM python:3.11-slim AS builder
# ... build dependencies

FROM python:3.11-slim
# ... copy only necessary files
```

#### Docker Compose Security
```yaml
services:
  api:
    # Don't use :latest
    image: interntrack:1.15.0
    
    # Use secrets
    secrets:
      - db_password
      - api_key
    
    # Read-only filesystem where possible
    read_only: true
    
    # Drop capabilities
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    
    # Security options
    security_opt:
      - no-new-privileges:true
    
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
        reservations:
          memory: 512M

secrets:
  db_password:
    file: ./secrets/db_password.txt
  api_key:
    file: ./secrets/api_key.txt
```

### 6.2 Environment Security

```bash
# Use different secrets per environment

# Development
DATABASE_URL=sqlite:///./dev.db
SECRET_KEY=dev-secret-key-not-for-production

# Staging
DATABASE_URL=postgresql://staging:pass@db/staging
SECRET_KEY=staging-secret-key

# Production
DATABASE_URL=postgresql://prod:pass@db/prod
SECRET_KEY=production-secret-key-very-secure
```

### 6.3 Network Security

```yaml
# Docker network isolation
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access

services:
  nginx:
    networks:
      - frontend
  
  api:
    networks:
      - frontend
      - backend
  
  db:
    networks:
      - backend  # Only accessible internally
```

---

## 7. MONITORING & OBSERVABILITY

### 7.1 Logging Strategy

```python
import structlog
from typing import Any

def setup_logging():
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

# Application logging
logger = structlog.get_logger()

# Request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    
    logger.info("request.started",
        method=request.method,
        path=request.url.path
    )
    
    response = await call_next(request)
    
    logger.info("request.completed",
        status_code=response.status_code
    )
    
    return response
```

### 7.2 Metrics Collection

```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

ACTIVE_JOBS = Gauge(
    'active_jobs_total',
    'Total active job listings'
)

SCRAPER_SUCCESS = Counter(
    'scraper_success_total',
    'Successful scraper runs',
    ['source']
)

# Usage
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(time.time() - start_time)
    
    return response
```

### 7.3 Alerting Rules

```yaml
# alerts.yml
groups:
  - name: application
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: High error rate detected
      
      - alert: HighLatency
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High latency detected
      
      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) < 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: Disk space is low
```

---

## 8. BACKUP & RECOVERY

### 8.1 Backup Strategy

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_FILE="data/interntrack.db"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
cp $DB_FILE "$BACKUP_DIR/interntrack_$DATE.db"

# Backup configuration
cp .env "$BACKUP_DIR/env_$DATE"

# Compress
tar -czf "$BACKUP_DIR/interntrack_$DATE.tar.gz" \
    "$BACKUP_DIR/interntrack_$DATE.db" \
    "$BACKUP_DIR/env_$DATE"

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: interntrack_$DATE.tar.gz"
```

### 8.2 Recovery Procedures

```bash
# Database recovery
cp /backups/interntrack_YYYYMMDD.tar.gz /tmp/
cd /tmp
tar -xzf interntrack_YYYYMMDD.tar.gz
cp interntrack_YYYYMMDD.db /app/data/interntrack.db

# Verify integrity
sqlite3 /app/data/interntrack.db "PRAGMA integrity_check;"

# Restart services
docker-compose restart api worker
```

### 8.3 Disaster Recovery Plan

| Scenario | RTO | RPO | Procedure |
|----------|-----|-----|-----------|
| Database corruption | 1 hour | 24 hours | Restore from daily backup |
| Server failure | 4 hours | 1 hour | Restore to new server |
| Security breach | 2 hours | 0 | Isolate, investigate, restore |
| Data loss | 1 hour | 24 hours | Restore from backup |

---

## 9. COMPLIANCE & AUDITING

### 9.1 Audit Logging

```python
from sqlalchemy import event
from datetime import datetime

class AuditLog:
    def __init__(self):
        self.logs = []

    def log(self, action: str, user_id: str, details: dict):
        self.logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id,
            "details": details
        })

# Database audit
@event.listens_for(Job, 'after_insert')
def audit_job_insert(mapper, connection, job):
    audit_log.log(
        action="job.created",
        user_id="system",
        details={"job_id": job.id, "title": job.title}
    )
```

### 9.2 Data Privacy

```python
# Data retention policy
RETENTION_POLICIES = {
    "activity_logs": 90,  # days
    "notifications": 30,
    "temp_files": 7,
    "backups": 365,
}

async def cleanup_old_data():
    """Remove data older than retention policy."""
    for table, days in RETENTION_POLICIES.items():
        cutoff = datetime.utcnow() - timedelta(days=days)
        await session.execute(
            delete(table).where(table.created_at < cutoff)
        )
```

---

## 10. INCIDENT RESPONSE

### 10.1 Incident Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| P1 | Critical | 1 hour | Data breach, service down |
| P2 | High | 4 hours | Major feature broken |
| P3 | Medium | 24 hours | Minor bug, performance issue |
| P4 | Low | 72 hours | Cosmetic issue |

### 10.2 Incident Response Checklist

```
1. DETECT
   [ ] Alert received
   [ ] Initial assessment
   [ ] Severity determined

2. RESPOND
   [ ] Incident commander assigned
   [ ] Team notified
   [ ] Status page updated

3. CONTAIN
   [ ] Isolate affected systems
   [ ] Preserve evidence
   [ ] Implement workaround

4. ERADICATE
   [ ] Root cause identified
   [ ] Fix implemented
   [ ] Fix tested

5. RECOVER
   [ ] Systems restored
   [ ] Monitoring enhanced
   [ ] Users notified

6. LEARN
   [ ] Post-mortem scheduled
   [ ] Documentation updated
   [ ] Preventive measures implemented
```

---

## 11. MAINTENANCE SCHEDULES

### 11.1 Daily Tasks

```bash
# 6:00 AM - Daily Report
0 6 * * * python -m interntrack.reports.daily

# Every hour - Cleanup
0 * * * * python -m interntrack.utils.cleanup

# Every 30 minutes - Job Discovery
*/30 * * * * python -m interntrack.scrapers.run
```

### 11.2 Weekly Tasks

```bash
# Monday 2:00 AM - Backup
0 2 * * 1 /app/scripts/backup.sh

# Monday 3:00 AM - Database optimization
0 3 * * 1 sqlite3 /app/data/interntrack.db "VACUUM;"

# Friday 4:00 PM - Dependency check
0 16 * * 5 pip-audit
```

### 11.3 Monthly Tasks

```bash
# 1st of month - Security scan
0 0 1 * * safety check

# 1st of month - Full backup
0 0 1 * * /app/scripts/backup-full.sh

# 15th of month - SSL certificate check
0 0 15 * * certbot renew --dry-run
```

---

## 12. CHECKLISTS

### 12.1 Pre-Commit Checklist

- [ ] Code compiles without errors
- [ ] All tests pass
- [ ] Linter shows no errors
- [ ] Type checker shows no errors
- [ ] No hardcoded secrets
- [ ] Documentation updated
- [ ] Changelog updated (if needed)

### 12.2 Pre-Deployment Checklist

- [ ] All tests pass in CI
- [ ] Security scan passed
- [ ] Performance tests passed
- [ ] Database migrations tested
- [ ] Rollback plan documented
- [ ] Monitoring configured
- [ ] Alerts configured
- [ ] Backup verified

### 12.3 Post-Deployment Checklist

- [ ] Health checks passing
- [ ] No error spikes in logs
- [ ] Response times normal
- [ ] Critical user flows tested
- [ ] Monitoring dashboards reviewed
- [ ] Team notified

### 12.4 Security Audit Checklist

- [ ] No secrets in code
- [ ] All inputs validated
- [ ] SQL injection prevented
- [ ] XSS prevented
- [ ] CSRF protection enabled
- [ ] Rate limiting configured
- [ ] HTTPS enforced
- [ ] Security headers present
- [ ] Dependencies up to date
- [ ] Access logs reviewed

---

**Last Updated:** {{DATE}}
**Version:** 1.15.0
**Owner:** Security Team
