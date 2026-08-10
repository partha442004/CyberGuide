"""
Unit tests for the salary insights / benchmarks API.
"""

from dataclasses import dataclass

import pytest


@dataclass
class _FakeJob:
    """Minimal Job stand-in with the attributes the endpoint reads."""

    title: str
    description: str
    location: str
    salary_min: int | None
    salary_max: int | None
    is_active: bool = True


class _FakeResult:
    """Result proxy exposing .scalars().all() like SQLAlchemy."""

    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    """AsyncSession stand-in: ignores the query, returns canned jobs."""

    def __init__(self, jobs):
        self._jobs = jobs

    async def execute(self, _query):
        return _FakeResult(self._jobs)


def _security_jobs():
    return [
        _FakeJob(
            title="SOC Analyst",
            description="Monitor SIEM alerts and triage incidents.",
            location="Bangalore, Karnataka",
            salary_min=500_000,
            salary_max=700_000,
        ),
        _FakeJob(
            title="SOC Analyst L2",
            description="Handle escalations in the SOC.",
            location="Bangalore",
            salary_min=600_000,
            salary_max=800_000,
        ),
        _FakeJob(
            title="React Developer",
            description="Build frontend UI components.",
            location="Chennai",
            salary_min=300_000,
            salary_max=400_000,
        ),
    ]


def test_classify_domain():
    from interntrack.api.v1.salary_insights import _classify_domain

    assert _classify_domain("SOC Analyst", "monitor SIEM") == "security"
    assert _classify_domain("VAPT Engineer", "penetration testing") == "security"
    assert _classify_domain("ML Engineer", "machine learning models") == "data"
    assert _classify_domain("DevOps", "cloud infrastructure") == "devops"
    assert _classify_domain("React Developer", "frontend") == "development"


@pytest.mark.asyncio
async def test_salary_benchmarks_groups_by_domain_and_city():
    from interntrack.api.v1.salary_insights import salary_benchmarks

    data = await salary_benchmarks(db=_FakeDB(_security_jobs()))

    assert data["total_buckets"] == 2
    security_row = next(
        r
        for r in data["rows"]
        if r["domain"] == "security" and r["city"] == "Bangalore"
    )
    assert security_row["count"] == 2
    # Midpoints 600_000 and 700_000 -> median 650_000.
    assert security_row["median"] == 650_000
    assert security_row["min"] == 600_000
    assert security_row["max"] == 700_000
    assert security_row["currency"] == "INR"


@pytest.mark.asyncio
async def test_salary_benchmarks_skips_jobs_without_salary():
    from interntrack.api.v1.salary_insights import salary_benchmarks

    jobs = [
        _FakeJob(
            title="SOC Analyst",
            description="security",
            location="Bangalore",
            salary_min=None,
            salary_max=None,
        ),
        _FakeJob(
            title="Security Engineer",
            description="security",
            location="Bangalore",
            salary_min=1_000_000,
            salary_max=1_500_000,
        ),
    ]
    data = await salary_benchmarks(db=_FakeDB(jobs))
    assert data["total_buckets"] == 1
    assert data["rows"][0]["count"] == 1
    assert data["rows"][0]["median"] == 1_250_000
