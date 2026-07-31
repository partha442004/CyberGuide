"""
Pytest configuration and test fixtures.
"""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from interntrack.main import app
from interntrack.domain.models import Base


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
