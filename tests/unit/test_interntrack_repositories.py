"""
Unit Tests for the interntrack repository layer.

Exercises BaseRepository, UserRepository, SkillRepository, JobRepository and
ApplicationRepository against the in-memory test database (db_session fixture).
"""

from datetime import UTC, datetime, timedelta

import pytest

from interntrack.domain.enums import (
    ApplicationStatus,
    ExperienceLevel,
    JobSource,
    JobType,
    SkillCategory,
)
from interntrack.domain.models import (
    Application,
    Job,
    Skill,
)
from interntrack.repositories.application_repository import ApplicationRepository
from interntrack.repositories.base import BaseRepository
from interntrack.repositories.job_repository import JobRepository
from interntrack.repositories.skill_repository import SkillRepository
from interntrack.repositories.user_repository import UserRepository

_JOB_URL_COUNTER = 0


def make_job(**overrides) -> Job:
    """Create a Job with sensible defaults (unique url per call)."""
    global _JOB_URL_COUNTER
    _JOB_URL_COUNTER += 1
    defaults = {
        "title": "Security Engineer",
        "company": "CyberCorp",
        "url": f"https://example.com/job/security-{_JOB_URL_COUNTER}",
        "source": JobSource.LINKEDIN,
        "job_type": JobType.FULL_TIME,
        "experience_level": ExperienceLevel.MID,
        "location": "Remote",
        "description": "Build security tooling",
        "is_remote": True,
        "is_active": True,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Job(**defaults)


def make_skill(**overrides) -> Skill:
    """Create a Skill with sensible defaults."""
    defaults = {
        "name": "python",
        "category": SkillCategory.PROGRAMMING,
        "difficulty_level": 2,
        "is_active": True,
        "learning_resources": ["https://learn.example/python"],
    }
    defaults.update(overrides)
    return Skill(**defaults)


class TestBaseRepository:
    """Tests for the generic CRUD repository."""

    @pytest.mark.asyncio
    async def test_create_and_get_by_id(self, db_session):
        repo = BaseRepository(Skill, db_session)
        skill = await repo.create(make_skill())
        fetched = await repo.get_by_id(skill.id)
        assert fetched is not None
        assert fetched.name == "python"

    @pytest.mark.asyncio
    async def test_get_by_id_missing_returns_none(self, db_session):
        repo = BaseRepository(Skill, db_session)
        assert await repo.get_by_id("missing") is None

    @pytest.mark.asyncio
    async def test_get_all_with_skip_limit_and_filters(self, db_session):
        repo = BaseRepository(Skill, db_session)
        await repo.create_many(
            [
                make_skill(name="python", category=SkillCategory.PROGRAMMING),
                make_skill(name="aws", category=SkillCategory.TOOL),
                make_skill(name="java", category=SkillCategory.PROGRAMMING),
            ]
        )

        all_skills = await repo.get_all()
        assert len(all_skills) == 3

        filtered = await repo.get_all(filters={"category": SkillCategory.PROGRAMMING})
        assert len(filtered) == 2

        paginated = await repo.get_all(skip=1, limit=1)
        assert len(paginated) == 1

        # Filter on a non-existent attribute is ignored.
        ignored = await repo.get_all(filters={"nonexistent_col": 5})
        assert len(ignored) == 3

    @pytest.mark.asyncio
    async def test_count_with_and_without_filters(self, db_session):
        repo = BaseRepository(Skill, db_session)
        await repo.create_many(
            [
                make_skill(name="python", category=SkillCategory.PROGRAMMING),
                make_skill(name="aws", category=SkillCategory.TOOL),
            ]
        )
        assert await repo.count() == 2
        assert await repo.count(filters={"category": SkillCategory.PROGRAMMING}) == 1

    @pytest.mark.asyncio
    async def test_create_many(self, db_session):
        repo = BaseRepository(Skill, db_session)
        created = await repo.create_many(
            [make_skill(name="python"), make_skill(name="bash")]
        )
        assert len(created) == 2
        assert all(s.id for s in created)
        assert await repo.count() == 2

    @pytest.mark.asyncio
    async def test_update_existing_and_missing(self, db_session):
        repo = BaseRepository(Skill, db_session)
        skill = await repo.create(make_skill(name="python"))

        updated = await repo.update(skill.id, {"difficulty_level": 4})
        assert updated is not None
        assert updated.difficulty_level == 4

        # Unknown attribute keys are skipped, not fatal.
        updated2 = await repo.update(skill.id, {"unknown_field": 1})
        assert updated2 is not None

        assert await repo.update("missing", {"difficulty_level": 4}) is None

    @pytest.mark.asyncio
    async def test_delete_existing_and_missing(self, db_session):
        repo = BaseRepository(Skill, db_session)
        skill = await repo.create(make_skill(name="python"))
        assert await repo.delete(skill.id) is True
        assert await repo.delete("missing") is False
        assert await repo.count() == 0

    @pytest.mark.asyncio
    async def test_exists(self, db_session):
        repo = BaseRepository(Skill, db_session)
        skill = await repo.create(make_skill(name="python"))
        assert await repo.exists(skill.id) is True
        assert await repo.exists("missing") is False


class TestUserRepository:
    """Tests for the user repository."""

    @pytest.mark.asyncio
    async def test_add_and_get_user_skills(self, db_session):
        skill_repo = SkillRepository(db_session)
        skill = await skill_repo.create(make_skill(name="python"))
        user_repo = UserRepository(db_session)

        created = await user_repo.add_user_skill("user-1", skill.id, proficiency=3)
        assert created.proficiency_level == 3

        skills = await user_repo.get_user_skills("user-1")
        assert len(skills) == 1
        assert skills[0].skill_id == skill.id

        assert await user_repo.get_user_skills("user-2") == []

    @pytest.mark.asyncio
    async def test_update_skill_proficiency(self, db_session):
        skill_repo = SkillRepository(db_session)
        skill = await skill_repo.create(make_skill(name="python"))
        user_repo = UserRepository(db_session)
        await user_repo.add_user_skill("user-1", skill.id, proficiency=1)

        updated = await user_repo.update_skill_proficiency("user-1", skill.id, 5)
        assert updated is not None
        assert updated.proficiency_level == 5

        missing = await user_repo.update_skill_proficiency("user-1", "nope", 5)
        assert missing is None

    @pytest.mark.asyncio
    async def test_add_and_get_bookmarks(self, db_session):
        user_repo = UserRepository(db_session)
        created = await user_repo.add_bookmark("job", "job-1", notes="check later")
        assert created.item_type == "job"
        assert created.item_id == "job-1"

        await user_repo.add_bookmark("company", "company-1")

        all_bookmarks = await user_repo.get_bookmarks("user-1")
        assert len(all_bookmarks) == 2

        job_bookmarks = await user_repo.get_bookmarks("user-1", item_type="job")
        assert len(job_bookmarks) == 1
        assert job_bookmarks[0].item_id == "job-1"

    @pytest.mark.asyncio
    async def test_remove_bookmark(self, db_session):
        user_repo = UserRepository(db_session)
        bookmark = await user_repo.add_bookmark("job", "job-1")
        assert await user_repo.remove_bookmark(bookmark.id) is True
        assert await user_repo.remove_bookmark(bookmark.id) is False

    @pytest.mark.asyncio
    async def test_add_and_get_watchlists(self, db_session):
        user_repo = UserRepository(db_session)
        created = await user_repo.add_watchlist(
            "keyword", "security", notification_channels=["email", "telegram"]
        )
        assert created.notification_channels == ["email", "telegram"]

        defaulted = await user_repo.add_watchlist("company", "Acme")
        assert defaulted.notification_channels == ["email"]

        all_watchlists = await user_repo.get_watchlists()
        assert len(all_watchlists) == 2

        keyword_watchlists = await user_repo.get_watchlists(watch_type="keyword")
        assert len(keyword_watchlists) == 1


class TestSkillRepository:
    """Tests for the skill repository."""

    @pytest.mark.asyncio
    async def test_get_by_name(self, db_session):
        repo = SkillRepository(db_session)
        await repo.create(make_skill(name="python"))
        found = await repo.get_by_name("Python")
        assert found is not None
        assert found.name == "python"
        assert await repo.get_by_name("rust") is None

    @pytest.mark.asyncio
    async def test_get_by_category(self, db_session):
        repo = SkillRepository(db_session)
        await repo.create_many(
            [
                make_skill(name="python", category=SkillCategory.PROGRAMMING),
                make_skill(name="aws", category=SkillCategory.TOOL),
            ]
        )
        programming = await repo.get_by_category(SkillCategory.PROGRAMMING)
        assert len(programming) == 1
        assert programming[0].name == "python"

    @pytest.mark.asyncio
    async def test_search_skills(self, db_session):
        repo = SkillRepository(db_session)
        await repo.create_many(
            [
                make_skill(name="python"),
                make_skill(name="pyramid"),
                make_skill(name="java"),
            ]
        )
        results = await repo.search_skills("py")
        assert {s.name for s in results} == {"python", "pyramid"}

    @pytest.mark.asyncio
    async def test_get_active_skills(self, db_session):
        repo = SkillRepository(db_session)
        await repo.create_many(
            [
                make_skill(name="python", is_active=True),
                make_skill(name="rust", is_active=False),
            ]
        )
        active = await repo.get_active_skills()
        assert [s.name for s in active] == ["python"]

    @pytest.mark.asyncio
    async def test_create_or_get(self, db_session):
        repo = SkillRepository(db_session)
        created = await repo.create_or_get("Python", SkillCategory.PROGRAMMING)
        assert created.name == "python"

        existing = await repo.create_or_get("Python", SkillCategory.PROGRAMMING)
        assert existing.id == created.id
        assert await repo.count() == 1


class TestJobRepository:
    """Tests for the job repository."""

    @pytest.mark.asyncio
    async def test_create_get_by_url_and_find_duplicate(self, db_session):
        repo = JobRepository(db_session)
        job = await repo.create(make_job())
        assert await repo.get_by_url(job.url) is not None
        assert await repo.get_by_url("https://nope.example") is None

        dup = await repo.find_duplicate(
            "Security Engineer", "CyberCorp", JobSource.LINKEDIN
        )
        assert dup is not None

        # Tolerance window 0 means cutoff == now; use a future created_at so
        # the job is still >= cutoff regardless of clock skew.
        future_job = await repo.create(
            make_job(created_at=datetime.now(UTC) + timedelta(days=1))
        )
        old = await repo.find_duplicate(
            future_job.title, future_job.company, JobSource.LINKEDIN, tolerance_days=0
        )
        assert old is not None

    @pytest.mark.asyncio
    async def test_get_active_jobs_with_filters(self, db_session):
        repo = JobRepository(db_session)
        await repo.create_many(
            [
                make_job(title="Security Engineer", company="Acme"),
                make_job(
                    title="Backend Engineer",
                    company="Globex",
                    is_remote=False,
                    job_type=JobType.CONTRACT,
                ),
            ]
        )

        all_active = await repo.get_active_jobs()
        assert len(all_active) == 2

        remote = await repo.get_active_jobs(is_remote=True)
        assert len(remote) == 1

        contract = await repo.get_active_jobs(job_type=JobType.CONTRACT)
        assert len(contract) == 1

        acme = await repo.get_active_jobs(company="Acme")
        assert len(acme) == 1

        none = await repo.get_active_jobs(company="Missing", is_remote=True)
        assert none == []

    @pytest.mark.asyncio
    async def test_get_jobs_by_source_and_recent(self, db_session):
        repo = JobRepository(db_session)
        await repo.create_many(
            [
                make_job(source=JobSource.LINKEDIN),
                make_job(source=JobSource.INDEED),
            ]
        )
        linkedin = await repo.get_jobs_by_source(JobSource.LINKEDIN)
        assert len(linkedin) == 1

        recent = await repo.get_recent_jobs(days=1)
        assert len(recent) == 2
        assert await repo.get_recent_jobs(days=-1) == []

    @pytest.mark.asyncio
    async def test_get_recent_jobs_enforces_days_window(self, db_session):
        """Old listings fall outside the window; fresh ones stay."""
        repo = JobRepository(db_session)
        now = datetime.now(UTC).replace(tzinfo=None)
        await repo.create_many(
            [
                make_job(title="Fresh Job", created_at=now),
                make_job(title="Stale Job", created_at=now - timedelta(days=10)),
            ]
        )
        recent = await repo.get_recent_jobs(days=1)
        assert [j.title for j in recent] == ["Fresh Job"]
        wide = await repo.get_recent_jobs(days=30)
        assert {j.title for j in wide} == {"Fresh Job", "Stale Job"}

    @pytest.mark.asyncio
    async def test_get_closing_soon(self, db_session):
        repo = JobRepository(db_session)
        soon = datetime.now(UTC) + timedelta(days=1)
        past = datetime.now(UTC) - timedelta(days=1)
        await repo.create_many(
            [
                make_job(title="Closing Soon", expires_at=soon),
                make_job(title="Already Expired", expires_at=past),
                make_job(title="No Expiry", expires_at=None),
            ]
        )
        closing = await repo.get_closing_soon(days=2)
        assert [j.title for j in closing] == ["Closing Soon"]

    @pytest.mark.asyncio
    async def test_top_companies_and_type_distribution(self, db_session):
        repo = JobRepository(db_session)
        await repo.create_many(
            [
                make_job(title="A", company="Acme"),
                make_job(title="B", company="Acme"),
                make_job(title="C", company="Globex", job_type=JobType.CONTRACT),
            ]
        )
        top = await repo.get_top_companies(limit=5)
        assert top[0] == ("Acme", 2)

        dist = await repo.get_job_type_distribution()
        by_type = dict(dist)
        assert by_type[JobType.FULL_TIME] == 2
        assert by_type[JobType.CONTRACT] == 1

    @pytest.mark.asyncio
    async def test_search_jobs(self, db_session):
        repo = JobRepository(db_session)
        await repo.create_many(
            [
                make_job(title="Security Engineer", description="SIEM and response"),
                make_job(title="Data Engineer", description="pipelines"),
            ]
        )
        hits = await repo.search_jobs("siem")
        assert len(hits) == 1
        assert hits[0].title == "Security Engineer"

    @pytest.mark.asyncio
    async def test_get_salary_statistics(self, db_session):
        repo = JobRepository(db_session)
        await repo.create_many(
            [
                make_job(salary_min=80000, salary_max=120000),
                make_job(salary_min=60000, salary_max=90000),
                make_job(salary_min=None, salary_max=None),
            ]
        )
        stats = await repo.get_salary_statistics()
        assert stats["min_salary"] == 60000
        assert stats["max_salary"] == 120000
        assert stats["avg_min"] == 70000.0
        assert stats["avg_max"] == 105000.0

    @pytest.mark.asyncio
    async def test_deactivate_expired(self, db_session):
        repo = JobRepository(db_session)
        past = datetime.now(UTC) - timedelta(days=1)
        future = datetime.now(UTC) + timedelta(days=1)
        await repo.create_many(
            [
                make_job(title="Expired", expires_at=past),
                make_job(title="Future", expires_at=future),
                make_job(title="No Expiry", expires_at=None),
            ]
        )
        count = await repo.deactivate_expired()
        assert count == 1
        active = await repo.get_active_jobs()
        assert {j.title for j in active} == {"Future", "No Expiry"}
        assert "Expired" not in {j.title for j in active}

    @pytest.mark.asyncio
    async def test_backfill_job_tags_tags_tagless_jobs(self, db_session):
        """Jobs saved before auto-tagging get skill tags from their title +
        description so they earn match scores (the ``match_score: null`` gap)."""
        repo = JobRepository(db_session)
        await repo.create_many(
            [
                make_job(
                    title="SOC Analyst",
                    description="Monitor SIEM alerts in Splunk, drive "
                    "incident response, hunt malware.",
                    tags=[],
                ),
                make_job(title="Already Tagged", description="python", tags=["python"]),
                make_job(
                    title="General Role",
                    description="No keywords here at all.",
                    tags=[],
                ),
            ]
        )

        updated = await repo.backfill_job_tags(limit=10)

        assert updated == 1  # only the SOC Analyst job gains tags
        all_jobs = await repo.get_active_jobs(limit=10)
        by_title = {j.title: j for j in all_jobs}
        soc_tags = [str(t).lower() for t in (by_title["SOC Analyst"].tags or [])]
        assert "soc analyst" in soc_tags
        assert "siem" in soc_tags
        assert "splunk" in soc_tags
        # Already-tagged job untouched.
        assert by_title["Already Tagged"].tags == ["python"]
        # No-keyword job still empty.
        assert not by_title["General Role"].tags

    @pytest.mark.asyncio
    async def test_backfill_job_tags_respects_limit(self, db_session):
        """The limit caps how many jobs are backfilled per call."""
        repo = JobRepository(db_session)
        await repo.create_many(
            [
                make_job(
                    title="SOC Analyst",
                    description="Splunk SIEM incident response",
                    tags=[],
                ),
                make_job(
                    title="Pentester",
                    description="burp suite nmap vapt",
                    tags=[],
                ),
            ]
        )

        updated = await repo.backfill_job_tags(limit=1)
        assert updated == 1


class TestApplicationRepository:
    """Tests for the application repository."""

    async def _make_app(self, db_session, **overrides) -> Application:
        job_repo = JobRepository(db_session)
        job = await job_repo.create(make_job())
        app_defaults = {
            "job_id": job.id,
            "status": ApplicationStatus.SAVED,
            "created_at": datetime.now(UTC),
        }
        app_defaults.update(overrides)
        return Application(**app_defaults)

    @pytest.mark.asyncio
    async def test_get_by_job_id_and_status(self, db_session):
        repo = ApplicationRepository(db_session)
        app = await self._make_app(db_session)
        db_session.add(app)
        await db_session.flush()

        assert await repo.get_by_job_id(app.job_id) is not None
        assert await repo.get_by_job_id("missing-job") is None

        saved = await repo.get_by_status(ApplicationStatus.SAVED)
        assert len(saved) == 1
        assert await repo.get_by_status(ApplicationStatus.APPLIED) == []

    @pytest.mark.asyncio
    async def test_get_status_counts(self, db_session):
        repo = ApplicationRepository(db_session)
        job_repo = JobRepository(db_session)
        job = await job_repo.create(make_job())
        for status in [
            ApplicationStatus.SAVED,
            ApplicationStatus.APPLIED,
            ApplicationStatus.SAVED,
        ]:
            db_session.add(Application(job_id=job.id, status=status))
        await db_session.flush()

        counts = await repo.get_status_counts()
        assert counts == {"saved": 2, "applied": 1}

    @pytest.mark.asyncio
    async def test_recent_applications_and_timeline(self, db_session):
        repo = ApplicationRepository(db_session)
        job_repo = JobRepository(db_session)
        job = await job_repo.create(make_job())
        db_session.add(Application(job_id=job.id, status=ApplicationStatus.SAVED))
        await db_session.flush()

        recent = await repo.get_recent_applications(days=30)
        assert len(recent) == 1

        timeline = await repo.get_application_timeline(days=30)
        assert len(timeline) == 1
        assert timeline[0]["status"] == ApplicationStatus.SAVED
        assert timeline[0]["count"] == 1

    @pytest.mark.asyncio
    async def test_pending_reminders_and_priority(self, db_session):
        repo = ApplicationRepository(db_session)
        job_repo = JobRepository(db_session)
        job = await job_repo.create(make_job())
        db_session.add(
            Application(
                job_id=job.id,
                status=ApplicationStatus.APPLIED,
                reminded=False,
                priority=3,
            )
        )
        db_session.add(
            Application(
                job_id=job.id, status=ApplicationStatus.REJECTED, reminded=False
            )
        )
        await db_session.flush()

        pending = await repo.get_pending_reminders()
        assert len(pending) == 1

        priority = await repo.get_priority_applications(min_priority=2)
        assert len(priority) == 1
        assert priority[0].priority == 3

    @pytest.mark.asyncio
    async def test_update_status_with_history(self, db_session):
        repo = ApplicationRepository(db_session)
        job_repo = JobRepository(db_session)
        job = await job_repo.create(make_job())
        app = Application(job_id=job.id, status=ApplicationStatus.SAVED)
        db_session.add(app)
        await db_session.flush()

        updated = await repo.update_status(
            app.id, ApplicationStatus.APPLIED, notes="applied today"
        )
        assert updated is not None
        assert updated.status == ApplicationStatus.APPLIED
        assert updated.applied_at is not None

        assert await repo.update_status("missing", ApplicationStatus.APPLIED) is None

    @pytest.mark.asyncio
    async def test_rejection_and_response_rate(self, db_session):
        repo = ApplicationRepository(db_session)
        job_repo = JobRepository(db_session)
        job = await job_repo.create(make_job())

        # Empty table -> 0.0 for both.
        assert await repo.get_rejection_rate() == 0.0
        assert await repo.get_response_rate() == 0.0

        db_session.add(Application(job_id=job.id, status=ApplicationStatus.REJECTED))
        db_session.add(Application(job_id=job.id, status=ApplicationStatus.APPLIED))
        db_session.add(Application(job_id=job.id, status=ApplicationStatus.INTERVIEW))
        await db_session.flush()

        assert await repo.get_rejection_rate() == round(1 / 3 * 100, 2)
        assert await repo.get_response_rate() == 100.0
