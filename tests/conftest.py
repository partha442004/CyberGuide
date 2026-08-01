"""
Pytest configuration and test fixtures.
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime

# Disable rate limiting so the shared integration client stays deterministic.
# Rate limiting is exercised explicitly in tests/unit/test_rate_limit.py.
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from interntrack.domain.enums import ExperienceLevel, JobSource, JobType
from interntrack.domain.models import Base, Job
from interntrack.main import app


def make_job(**overrides) -> Job:
    """Create a Job instance with sensible defaults. Use for export/CSV/JSON tests."""
    defaults = {
        "id": "job-1",
        "title": "Python Developer",
        "company": "TechCorp",
        "url": "https://example.com/job/1",
        "source": JobSource.LINKEDIN,
        "job_type": JobType.FULL_TIME,
        "experience_level": ExperienceLevel.MID,
        "location": "Remote",
        "description": "Build APIs",
        "salary_min": 80000,
        "salary_max": 120000,
        "salary_currency": "USD",
        "is_remote": True,
        "is_active": True,
        "posted_at": datetime(2026, 1, 15, tzinfo=UTC),
        "expires_at": None,
        "created_at": datetime(2026, 1, 10, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 10, tzinfo=UTC),
        "tags": ["python", "fastapi"],
    }
    defaults.update(overrides)
    return Job(**defaults)


def make_job_mock(**overrides) -> dict:
    """Create a Job-like dict that passes Pydantic validation. Use for API tests."""
    defaults = {
        "id": "job-1",
        "title": "Python Developer",
        "company": "TechCorp",
        "url": "https://example.com/job/1",
        "source": "manual",
        "location": "Remote",
        "description": "Build APIs",
        "job_type": "full_time",
        "experience_level": "mid",
        "salary_min": 80000,
        "salary_max": 120000,
        "salary_currency": "USD",
        "is_remote": True,
        "is_active": True,
        "tags": ["python"],
        "posted_at": None,
        "expires_at": None,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    defaults.update(overrides)
    return defaults


def make_app_mock(**overrides) -> dict:
    """Create an Application-like dict that passes Pydantic validation.

    Use for API tests.
    """
    defaults = {
        "id": "app-1",
        "job_id": "job-1",
        "status": "saved",
        "applied_at": None,
        "interview_at": None,
        "notes": None,
        "resume_version": None,
        "priority": 0,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    defaults.update(overrides)
    return defaults


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
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
async def client(db_engine, db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client wired to the in-memory test database."""
    import interntrack.database.session as session_module
    from interntrack.database.session import get_db

    app.dependency_overrides.clear()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # The /health endpoint creates its own session via async_session_factory
    # (so engine-down returns 503, not 500); point it at the in-memory test
    # engine so the connectivity probe succeeds during tests.
    test_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    original_factory = session_module.async_session_factory
    session_module.async_session_factory = test_factory

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    session_module.async_session_factory = original_factory
    app.dependency_overrides.clear()


@pytest.fixture
def mock_job_data() -> dict:
    """Sample job data for testing."""
    import uuid

    return {
        "title": "Python Developer",
        "company": "TechCorp",
        "url": f"https://example.com/job/{uuid.uuid4()}",
        "description": "We are looking for a Python developer...",
        "location": "Remote",
        "job_type": "full_time",
        "is_remote": True,
        "salary_min": 80000,
        "salary_max": 120000,
        "tags": ["python", "fastapi", "sqlalchemy"],
    }


@pytest.fixture
def mock_application_data() -> dict:
    """Sample application data for testing."""
    return {
        "job_id": "test-job-id-123",
        "status": "saved",
        "notes": "Interesting position",
        "priority": 1,
    }


@pytest.fixture
def mock_raw_jobs() -> list:
    """Sample raw job data from scrapers."""
    return [
        {
            "title": "Backend Developer",
            "company": "StartupXYZ",
            "url": "https://example.com/job/100",
            "description": "Build scalable APIs",
            "location": "San Francisco, CA",
            "job_type": "full_time",
            "is_remote": False,
            "source": "hackernews",
            "tags": ["python", "golang"],
        },
        {
            "title": "Frontend Engineer",
            "company": "WebCo",
            "url": "https://example.com/job/101",
            "description": "Build beautiful UIs",
            "location": "Remote",
            "job_type": "remote",
            "is_remote": True,
            "source": "remoteok",
            "tags": ["react", "typescript"],
        },
    ]
