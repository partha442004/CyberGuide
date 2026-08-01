"""
Pytest configuration and test fixtures.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from interntrack.domain.models import Base
from interntrack.main import app

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
    from interntrack.database.session import get_db

    app.dependency_overrides.clear()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

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
