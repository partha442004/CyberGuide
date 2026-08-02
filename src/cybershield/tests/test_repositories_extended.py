"""
Tests for the specialized repositories: Job, Skill, User, Application.

Uses the shared in-memory-SQLite ``db_session`` fixture so queries run against
a real (throwaway) database.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from cybershield.domain.enums import ApplicationStatus
from cybershield.domain.models import (
    Application,
    DuplicateGroup,
    ScamScore,
    SkillTrend,
    UserSkill,
    Watchlist,
)
from cybershield.repositories.application_repository import ApplicationRepository
from cybershield.repositories.job_repository import JobRepository
from cybershield.repositories.skill_repository import SkillRepository
from cybershield.repositories.user_repository import UserRepository


def _make_job(**overrides) -> dict:
    """Build a valid Job dict with defaults."""
    data = {
        "title": "Security Engineer",
        "company": "Acme",
        "url": f"https://job.example/{id(overrides)}",
        "source": "linkedin",
        "job_type": "full_time",
        "is_active": True,
        "country": "USA",
    }
    data.update(overrides)
    return data


def _make_user(**overrides) -> dict:
    """Build a valid User dict with defaults."""
    data = {
        "email": f"user{id(overrides)}@example.com",
        "username": f"user{id(overrides)}",
        "hashed_password": "hash",
        "is_active": True,
    }
    data.update(overrides)
    return data


class TestJobRepository:
    @pytest.mark.asyncio
    async def test_get_with_skills_missing(self, db_session):
        repo = JobRepository(db_session)
        assert await repo.get_with_skills("nope") is None

    @pytest.mark.asyncio
    async def test_search_jobs_no_filters(self, db_session):
        repo = JobRepository(db_session)
        await repo.create(_make_job(title="Backend Engineer"))
        await repo.create(_make_job(title="DevOps Engineer"))
        results = await repo.search_jobs("")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_jobs_with_query_and_filters(self, db_session):
        repo = JobRepository(db_session)
        await repo.create(_make_job(title="Python Developer", country="USA", job_type="full_time"))
        await repo.create(_make_job(title="Java Developer", country="IN", job_type="internship"))
        results = await repo.search_jobs(
            "python", country="USA", job_type="full_time", skip=0, limit=10
        )
        assert len(results) == 1
        assert results[0].title == "Python Developer"

    @pytest.mark.asyncio
    async def test_get_by_source(self, db_session):
        repo = JobRepository(db_session)
        await repo.create(_make_job(source="hackernews"))
        await repo.create(_make_job(source="remoteok"))
        results = await repo.get_by_source("hackernews")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_expiring_soon(self, db_session):
        repo = JobRepository(db_session)
        future = datetime.now(timezone.utc) + timedelta(days=3)
        past = datetime.now(timezone.utc) - timedelta(days=3)
        await repo.create(_make_job(title="Expiring", expires_at=future))
        await repo.create(_make_job(title="Expired", expires_at=past))
        results = await repo.get_expiring_soon(days=7)
        assert len(results) == 1
        assert results[0].title == "Expiring"

    @pytest.mark.asyncio
    async def test_get_high_scam_risk(self, db_session):
        job_repo = JobRepository(db_session)
        job = await job_repo.create(_make_job(title="Scammy"))
        await job_repo.create(_make_job(title="Clean"))

        scam = ScamScore(job_id=str(job.id), scam_score=90, confidence=0.99)
        db_session.add(scam)
        await db_session.flush()

        results = await job_repo.get_high_scam_risk(threshold=50.0)
        assert len(results) == 1
        assert results[0].title == "Scammy"

    @pytest.mark.asyncio
    async def test_mark_duplicates(self, db_session):
        repo = JobRepository(db_session)
        canonical = await repo.create(_make_job(title="Canonical"))
        dup1 = await repo.create(_make_job(title="Dup 1"))
        dup2 = await repo.create(_make_job(title="Dup 2"))

        await repo.mark_duplicates([str(dup1.id), str(dup2.id)], str(canonical.id))

        # duplicates deactivated and DuplicateGroup rows created
        dup1_fetched = await repo.get(str(dup1.id))
        assert dup1_fetched is not None
        assert dup1_fetched.is_active is False
        dup_groups = (
            (
                await db_session.execute(
                    select(DuplicateGroup).where(
                        DuplicateGroup.canonical_job_id == str(canonical.id)
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(dup_groups) == 2

    @pytest.mark.asyncio
    async def test_update_verification_status(self, db_session):
        repo = JobRepository(db_session)
        job = await repo.create(_make_job())
        updated = await repo.update_verification_status(str(job.id), True)
        assert updated.is_verified is True


class TestSkillRepository:
    @pytest.mark.asyncio
    async def test_get_by_name_case_insensitive(self, db_session):
        repo = SkillRepository(db_session)
        await repo.create({"name": "Python", "category": "programming"})
        skill = await repo.get_by_name("python")
        assert skill is not None
        assert skill.name == "Python"

    @pytest.mark.asyncio
    async def test_get_or_create_by_name(self, db_session):
        repo = SkillRepository(db_session)
        skill = await repo.get_or_create_by_name("SIEM", category="security")
        assert skill.name == "SIEM"
        again = await repo.get_or_create_by_name("SIEM")
        assert again.id == skill.id

    @pytest.mark.asyncio
    async def test_search_skills(self, db_session):
        repo = SkillRepository(db_session)
        await repo.create({"name": "Kubernetes", "category": "devops"})
        await repo.create({"name": "Docker", "category": "devops"})
        results = await repo.search_skills("kuber")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_user_skills_empty_and_add(self, db_session):
        repo = SkillRepository(db_session)
        user_repo = UserRepository(db_session)
        user = await user_repo.create(_make_user())
        assert user is not None
        user_id = str(user.id)

        user_skills = await repo.get_user_skills(user_id)
        assert user_skills == []

        us = await repo.add_user_skill(user_id, "Python", proficiency="advanced")
        assert isinstance(us, UserSkill)
        assert len(await repo.get_user_skills(user_id)) == 1
        assert (await repo.get_user_skills(user_id))[0].skill is not None

    @pytest.mark.asyncio
    async def test_get_skill_trends(self, db_session):
        repo = SkillRepository(db_session)
        skill = await repo.create({"name": "AWS", "category": "cloud"})
        old = datetime.now(timezone.utc) - timedelta(days=400)
        recent = datetime.now(timezone.utc) - timedelta(days=10)
        db_session.add_all(
            [
                SkillTrend(skill_id=str(skill.id), period="M1", period_start=old, demand_count=1),
                SkillTrend(
                    skill_id=str(skill.id), period="M2", period_start=recent, demand_count=5
                ),
            ]
        )
        await db_session.flush()
        trends = await repo.get_skill_trends(str(skill.id), months=12)
        assert len(trends) == 1
        assert trends[0].demand_count == 5


class TestUserRepository:
    @pytest.mark.asyncio
    async def test_get_by_email_and_username(self, db_session):
        repo = UserRepository(db_session)
        user = await repo.create(_make_user(email="a@example.com", username="alice"))
        assert user is not None
        by_email = await repo.get_by_email("a@example.com")
        assert by_email is not None
        assert by_email.id == user.id
        by_username = await repo.get_by_username("alice")
        assert by_username is not None
        assert by_username.id == user.id
        assert await repo.get_by_email("missing@example.com") is None

    @pytest.mark.asyncio
    async def test_get_with_preferences(self, db_session):
        repo = UserRepository(db_session)
        user = await repo.create(_make_user())
        fetched = await repo.get_with_preferences(str(user.id))
        assert fetched is not None

    @pytest.mark.asyncio
    async def test_add_and_remove_watchlist(self, db_session):
        repo = UserRepository(db_session)
        user = await repo.create(_make_user())
        assert user is not None
        user_id = str(user.id)
        watch = await repo.add_watchlist(user_id, "keyword", "python")
        assert isinstance(watch, Watchlist)

        # duplicate raises
        with pytest.raises(ValueError):
            await repo.add_watchlist(user_id, "keyword", "python")

        assert await repo.remove_watchlist(user_id, "keyword", "python") is True
        assert await repo.remove_watchlist(user_id, "keyword", "python") is False

    @pytest.mark.asyncio
    async def test_watchlist_helpers(self, db_session):
        repo = UserRepository(db_session)
        user = await repo.create(_make_user())
        assert user is not None
        user_id = str(user.id)
        await repo.add_company_watchlist(user_id, "company-1")
        await repo.add_keyword_watchlist(user_id, "siem")

        companies = await repo.get_company_watchlist(user_id)
        assert len(companies) == 1
        keywords = await repo.get_keyword_watchlist(user_id)
        assert len(keywords) == 1
        all_items = await repo.get_watchlist(user_id)
        assert len(all_items) == 2

        assert await repo.remove_company_watchlist(user_id, "company-1") is True
        assert await repo.remove_keyword_watchlist(user_id, "siem") is True


class TestApplicationRepository:
    @pytest.mark.asyncio
    async def test_create_application_and_get_by_status(self, db_session):
        user_repo = UserRepository(db_session)
        user = await user_repo.create(_make_user())
        assert user is not None
        user_id = str(user.id)
        job_repo = JobRepository(db_session)
        job = await job_repo.create(_make_job())

        app_repo = ApplicationRepository(db_session)
        application = Application(
            user_id=user_id,
            job_id=str(job.id),
            status="saved",
        )
        db_session.add(application)
        await db_session.flush()

        by_status = await app_repo.get_by_status(user_id, ApplicationStatus.SAVED)
        assert len(by_status) == 1

        all_apps = await app_repo.get_user_applications(user_id)
        assert len(all_apps) == 1
        filtered = await app_repo.get_user_applications(user_id, status=ApplicationStatus.SAVED)
        assert len(filtered) == 1

    @pytest.mark.asyncio
    async def test_update_status_creates_history(self, db_session):
        user_repo = UserRepository(db_session)
        user = await user_repo.create(_make_user())
        assert user is not None
        user_id = str(user.id)
        job_repo = JobRepository(db_session)
        job = await job_repo.create(_make_job())

        app_repo = ApplicationRepository(db_session)
        application = Application(user_id=user_id, job_id=str(job.id), status="saved")
        db_session.add(application)
        await db_session.flush()

        updated = await app_repo.update_status(
            str(application.id), ApplicationStatus.APPLIED, notes="sent resume"
        )
        assert updated.status == "applied"

        history = await app_repo.get_status_history(str(application.id))
        assert len(history) == 1
        assert history[0].old_status == "saved"
        assert history[0].new_status == "applied"

    @pytest.mark.asyncio
    async def test_get_application_metrics(self, db_session):
        user_repo = UserRepository(db_session)
        user = await user_repo.create(_make_user())
        job_repo = JobRepository(db_session)
        job1 = await job_repo.create(_make_job(url="https://job.example/1", title="J1"))
        job2 = await job_repo.create(_make_job(url="https://job.example/2", title="J2"))

        app_repo = ApplicationRepository(db_session)
        db_session.add_all(
            [
                Application(user_id=str(user.id), job_id=str(job1.id), status="interview"),
                Application(user_id=str(user.id), job_id=str(job2.id), status="saved"),
            ]
        )
        await db_session.flush()

        metrics = await app_repo.get_application_metrics(str(user.id))
        assert metrics["total"] == 2
        assert metrics["by_status"]["interview"] == 1
        assert metrics["success_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_get_application_metrics_empty(self, db_session):
        app_repo = ApplicationRepository(db_session)
        metrics = await app_repo.get_application_metrics("nobody")
        assert metrics["total"] == 0
        assert metrics["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_get_with_job_and_deadlines(self, db_session):
        user_repo = UserRepository(db_session)
        user = await user_repo.create(_make_user())
        assert user is not None
        user_id = str(user.id)
        job_repo = JobRepository(db_session)
        job = await job_repo.create(_make_job())

        app_repo = ApplicationRepository(db_session)
        app = Application(
            user_id=user_id,
            job_id=str(job.id),
            status="interview",
            interview_at=datetime.now(timezone.utc) + timedelta(days=2),
        )
        db_session.add(app)
        await db_session.flush()

        with_job = await app_repo.get_with_job(str(app.id))
        assert with_job is not None
        assert with_job.job is not None

        deadlines = await app_repo.get_upcoming_deadlines(user_id, days=7)
        assert len(deadlines) == 1
