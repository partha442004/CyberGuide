# CyberShield Career Intelligence Platform (CSCIP) - Testing

## Overview

CSCIP uses pytest for unit and integration testing with comprehensive coverage tracking.

> 📌 **Actual layout (2026-08-01):** CyberGuide tests live in
> `src/cybershield/tests/` (e.g. `test_engines.py`, `test_elasticsearch_service.py`,
> `test_scrapers.py`, `test_api.py`, `test_middleware.py`) and are run together with
> the InternTrack suite via:
> `pytest tests src/cybershield/tests -q -p no:cacheprovider -o addopts=''`.
> The `tests/unit/...` tree below is the InternTrack layout; it is illustrative.

---

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                    # Pytest fixtures
├── unit/
│   ├── __init__.py
│   ├── test_job_service.py
│   ├── test_application_service.py
│   ├── test_deduplication.py
│   ├── test_verification.py
│   ├── test_scam_detection.py
│   ├── test_classification.py
│   ├── test_resume_engine.py
│   ├── test_salary_engine.py
│   ├── test_notification_service.py
│   ├── test_watchlist_service.py
│   ├── test_analytics_service.py
│   └── test_learning_service.py
├── integration/
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_scrapers.py
│   └── test_database.py
└── fixtures/
    ├── jobs.json
    ├── applications.json
    └── resumes/
        └── sample_resume.pdf
```

---

## Test Configuration

```python
# tests/conftest.py

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from cybershield.main import app
from cybershield.domain.models import Base

# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    app.dependency_overrides = {}
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.fixture
def mock_job_data() -> dict:
    """Sample job data for testing."""
    return {
        "title": "SOC Analyst Intern",
        "company": "CrowdStrike",
        "url": "https://example.com/job/123",
        "description": "We are looking for a SOC analyst intern...",
        "location": "Bangalore, India",
        "country": "India",
        "job_type": "internship",
        "experience_level": "entry",
        "salary_min": 25000,
        "salary_max": 40000,
        "is_remote": False,
        "required_skills": ["SOC", "SIEM", "Linux"],
    }


@pytest.fixture
def mock_scam_job_data() -> dict:
    """Sample scam job data for testing."""
    return {
        "title": "Earn Money Fast!!!",
        "company": "Unknown Corp",
        "url": "https://suspicious-site.com/job/456",
        "description": "Training fee required. Guaranteed income. Apply now!",
        "location": "Remote",
        "job_type": "full_time",
    }


@pytest.fixture
def mock_resume_data() -> dict:
    """Sample parsed resume data."""
    return {
        "skills": ["python", "soc", "siem", "linux", "splunk"],
        "education": [
            {"degree": "Bachelor", "field": "Computer Science"}
        ],
        "experience": [
            {"title": "Security Intern", "company": "TechCorp"}
        ],
        "projects": ["Built SIEM dashboard", "CTF competition winner"],
        "certifications": ["CompTIA Security+"],
    }
```

---

## Unit Tests

### Job Service Tests

```python
# tests/unit/test_job_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock

from cybershield.services.job_service import JobService
from cybershield.domain.models import Job
from cybershield.domain.enums import JobSource, JobType
from cybershield.domain.exceptions import DuplicateJobError


class TestJobService:
    """Tests for JobService."""
    
    @pytest.fixture
    def mock_session(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_job_repo(self):
        repo = AsyncMock()
        repo.get_by_url.return_value = None
        repo.create.return_value = Job(
            id="test-id",
            title="Test Job",
            company="Test Corp",
            url="https://example.com/job/1",
        )
        return repo
    
    @pytest.fixture
    def service(self, mock_session, mock_job_repo):
        service = JobService(mock_session)
        service.job_repo = mock_job_repo
        return service
    
    @pytest.mark.asyncio
    async def test_create_job_success(self, service, mock_job_repo):
        """Test successful job creation."""
        job_data = {
            "title": "SOC Analyst",
            "company": "CrowdStrike",
            "url": "https://example.com/job/1",
        }
        
        result = await service.create_job(job_data)
        
        assert result is not None
        mock_job_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_job_duplicate(self, service, mock_job_repo):
        """Test duplicate job raises error."""
        mock_job_repo.get_by_url.return_value = Job(id="existing")
        
        job_data = {
            "title": "Duplicate Job",
            "company": "Corp",
            "url": "https://example.com/existing",
        }
        
        with pytest.raises(DuplicateJobError):
            await service.create_job(job_data)
    
    @pytest.mark.asyncio
    async def test_get_job(self, service, mock_job_repo):
        """Test getting a job by ID."""
        mock_job_repo.get_by_id.return_value = Job(
            id="test-id",
            title="Test Job",
        )
        
        result = await service.get_job("test-id")
        
        assert result is not None
        assert result.id == "test-id"
```

### Scam Detection Tests

```python
# tests/unit/test_scam_detection.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.engines.scam_detection import ScamDetectionEngine


class TestScamDetection:
    """Tests for ScamDetectionEngine."""
    
    @pytest.fixture
    def engine(self, db_session):
        return ScamDetectionEngine(db_session)
    
    @pytest.mark.asyncio
    async def test_detect_training_fee(self, engine):
        """Test detection of training fee scam."""
        job_data = {
            "title": "Security Analyst",
            "company": "Unknown Corp",
            "description": "Training fee required for this position",
            "url": "https://example.com/job/1",
        }
        
        result = await engine.analyze_job(job_data)
        
        assert result["scam_score"] > 70
        assert result["is_scam"] == True
        assert any("training_fee" in f["name"] for f in result["flags"])
    
    @pytest.mark.asyncio
    async def test_detect_disposable_email(self, engine):
        """Test detection of disposable email."""
        job_data = {
            "title": "Developer",
            "company": "Tech Corp",
            "description": "Apply now",
            "url": "https://example.com/job/2",
            "hr_email": "hr@temp-mail.org",
        }
        
        result = await engine.analyze_job(job_data)
        
        assert any("disposable_email" in f["name"] for f in result["flags"])
    
    @pytest.mark.asyncio
    async def test_legitimate_job(self, engine):
        """Test legitimate job gets low score."""
        job_data = {
            "title": "SOC Analyst Intern",
            "company": "CrowdStrike",
            "description": "Join our security team. No training fee required.",
            "url": "https://crowdstrike.com/careers/job/123",
        }
        
        result = await engine.analyze_job(job_data)
        
        assert result["scam_score"] < 30
        assert result["is_scam"] == False
```

### Deduplication Tests

```python
# tests/unit/test_deduplication.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from cybershield.engines.deduplication import DeduplicationEngine


class TestDeduplication:
    """Tests for DeduplicationEngine."""
    
    @pytest.fixture
    def engine(self, db_session):
        return DeduplicationEngine(db_session)
    
    def test_normalize_url(self, engine):
        """Test URL normalization."""
        url1 = "https://example.com/job/123?utm_source=linkedin"
        url2 = "https://example.com/job/123"
        
        normalized1 = engine._normalize_url(url1)
        normalized2 = engine._normalize_url(url2)
        
        assert normalized1 == normalized2
    
    def test_normalize_company(self, engine):
        """Test company name normalization."""
        assert engine._normalize_company("Microsoft Inc.") == "microsoft"
        assert engine._normalize_company("Google LLC") == "google"
    
    def test_calculate_similarity(self, engine):
        """Test job similarity calculation."""
        job1 = {
            "title": "SOC Analyst",
            "company": "CrowdStrike",
            "location": "Bangalore",
        }
        job2 = {
            "title": "SOC Analyst Intern",
            "company": "CrowdStrike",
            "location": "Bangalore",
        }
        
        similarity = engine._calculate_similarity(job1, job2)
        
        assert similarity > 0.8
    
    @pytest.mark.asyncio
    async def test_filter_unique(self, engine):
        """Test filtering unique jobs."""
        jobs = [
            {"title": "Job 1", "company": "Corp", "url": "https://example.com/1"},
            {"title": "Job 1", "company": "Corp", "url": "https://example.com/1"},  # Duplicate
            {"title": "Job 2", "company": "Corp", "url": "https://example.com/2"},
        ]
        
        unique = await engine.filter_unique(jobs)
        
        assert len(unique) == 2
```

---

## Integration Tests

### API Tests

```python
# tests/integration/test_api.py

import pytest
from httpx import AsyncClient


class TestJobsAPI:
    """Tests for Jobs API endpoints."""
    
    @pytest.mark.asyncio
    async def test_list_jobs(self, client: AsyncClient):
        """Test listing jobs."""
        response = await client.get("/api/v1/jobs/")
        
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
    
    @pytest.mark.asyncio
    async def test_create_job(self, client: AsyncClient, mock_job_data):
        """Test creating a job."""
        response = await client.post("/api/v1/jobs/", json=mock_job_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == mock_job_data["title"]
    
    @pytest.mark.asyncio
    async def test_get_job_not_found(self, client: AsyncClient):
        """Test getting non-existent job."""
        response = await client.get("/api/v1/jobs/non-existent")
        
        assert response.status_code == 404


class TestApplicationsAPI:
    """Tests for Applications API endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_application(self, client: AsyncClient, mock_job_data):
        """Test creating an application."""
        # First create a job
        job_response = await client.post("/api/v1/jobs/", json=mock_job_data)
        job_id = job_response.json()["id"]
        
        # Then create application
        app_response = await client.post(
            "/api/v1/applications/",
            json={"job_id": job_id}
        )
        
        assert app_response.status_code == 201
    
    @pytest.mark.asyncio
    async def test_update_application_status(self, client: AsyncClient, mock_job_data):
        """Test updating application status."""
        # Create job and application
        job_response = await client.post("/api/v1/jobs/", json=mock_job_data)
        job_id = job_response.json()["id"]
        
        app_response = await client.post(
            "/api/v1/applications/",
            json={"job_id": job_id}
        )
        app_id = app_response.json()["id"]
        
        # Update status
        update_response = await client.patch(
            f"/api/v1/applications/{app_id}/status",
            json={"status": "applied"}
        )
        
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "applied"
```

---

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cybershield --cov-report=html

# Run unit tests only
pytest tests/unit -v

# Run integration tests only
pytest tests/integration -v

# Run specific test
pytest tests/unit/test_scam_detection.py::TestScamDetection::test_detect_training_fee

# Run with verbose output
pytest -v --tb=short
```

---

## Coverage Targets

| Module | Target Coverage |
|--------|-----------------|
| services/ | ≥90% |
| engines/ | ≥85% |
| scrapers/ | ≥80% |
| api/ | ≥85% |
| **Overall** | **≥80%** |

---

## Test Fixtures

### Job Fixtures

```python
@pytest.fixture
def sample_jobs():
    """Multiple sample jobs for batch testing."""
    return [
        {
            "title": "SOC Analyst",
            "company": "CrowdStrike",
            "url": "https://example.com/job/1",
            "required_skills": ["SOC", "SIEM"],
        },
        {
            "title": "Security Engineer",
            "company": "Palo Alto",
            "url": "https://example.com/job/2",
            "required_skills": ["Python", "Cloud Security"],
        },
    ]
```

### Mock AI Fixtures

```python
@pytest.fixture
def mock_ai_service():
    """Mock AI service for testing."""
    mock = AsyncMock()
    mock.classify_job.return_value = {
        "job_type": "internship",
        "experience_level": "entry",
        "security_domain": "soc",
        "skills": ["soc", "siem"],
        "confidence": 0.85,
    }
    return mock
```

---

## Metrics

| Metric | Description |
|--------|-------------|
| `test_total` | Total tests |
| `test_passed` | Tests passed |
| `test_failed` | Tests failed |
| `test_coverage` | Code coverage percentage |
| `test_duration_seconds` | Total test duration |

---

**Module Status**: ✅ Complete

**All 18 Modules Complete!** 🎉
