"""
Test Configuration and Fixtures

Shared fixtures for all tests.
"""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from cybershield.dependencies import get_session
from cybershield.domain.models import Base
from cybershield.main import app

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a test database session with automatic rollback."""
    # Create tables once
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    # Drop tables after all tests
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client with database dependency override."""

    async def override_get_session():
        yield db_session

    # Override the database dependency
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Clear dependency overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
def sample_job():
    """Sample job data for testing."""
    return {
        "title": "Security Analyst",
        "company_name": "Tech Corp",
        "location": "Remote",
        "country": "USA",
        "description": "We are looking for a security analyst with Python and SIEM experience.",
        "url": "https://example.com/job/123",
        "source": "linkedin",
        "source_id": "linkedin_123",
        "salary_min": 80000,
        "salary_max": 120000,
        "salary_currency": "USD",
        "is_remote": True,
        "job_type": "full_time",
        "experience_level": "mid",
    }


@pytest.fixture
def sample_scam_job():
    """Sample scam job data for testing."""
    return {
        "title": "Easy Money Work From Home",
        "company_name": "",
        "location": "Remote",
        "description": "Training fee required. Guaranteed income. WhatsApp only contact.",
        "url": "https://suspicious-site.xyz/job/456",
        "source": "unknown",
    }
