"""Extended unit tests for services layer."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Job Service ────────────────────────────────────────────────────────────

class TestJobServiceExtended:
    """Extended tests for JobService."""

    @pytest.mark.asyncio
    async def test_create_job_success(self):
        from interntrack.services.job_service import JobService

        session = AsyncMock()
        service = JobService(session)
        service.job_repo.get_by_url = AsyncMock(return_value=None)
        service.job_repo.create = AsyncMock(return_value=MagicMock(id="job-1"))

        result = await service.create_job({
            "title": "Dev", "company": "Co", "url": "https://example.com",
        })

        assert result.id == "job-1"

    @pytest.mark.asyncio
    async def test_create_job_duplicate(self):
        from interntrack.domain.exceptions import DuplicateJobError
        from interntrack.services.job_service import JobService

        session = AsyncMock()
        service = JobService(session)
        service.job_repo.get_by_url = AsyncMock(return_value=MagicMock(id="existing"))

        with pytest.raises(DuplicateJobError):
            await service.create_job({
                "title": "Dev", "company": "Co", "url": "https://example.com",
            })

    @pytest.mark.asyncio
    async def test_get_job(self):
        from interntrack.services.job_service import JobService

        session = AsyncMock()
        service = JobService(session)
        service.job_repo.get_by_id = AsyncMock(return_value=MagicMock(id="job-1"))

        result = await service.get_job("job-1")
        assert result.id == "job-1"

    @pytest.mark.asyncio
    async def test_get_jobs(self):
        from interntrack.services.job_service import JobService

        session = AsyncMock()
        service = JobService(session)
        service.job_repo.get_active_jobs = AsyncMock(return_value=["j1", "j2"])

        result = await service.get_jobs(skip=0, limit=10)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_search_jobs(self):
        from interntrack.services.job_service import JobService

        session = AsyncMock()
        service = JobService(session)
        service.job_repo.search_jobs = AsyncMock(return_value=["j1"])

        result = await service.search_jobs("python", limit=5)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_save_jobs(self):
        from interntrack.services.job_service import JobService

        session = AsyncMock()
        service = JobService(session)
        service.job_repo.get_by_url = AsyncMock(return_value=None)
        service.job_repo.create = AsyncMock(return_value=MagicMock(id="new"))

        result = await service.save_jobs([
            {"title": "J1", "company": "C1", "url": "https://a.com"},
            {"title": "J2", "company": "C2", "url": "https://b.com"},
        ])
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_save_jobs_skips_duplicates(self):
        from interntrack.domain.exceptions import DuplicateJobError
        from interntrack.services.job_service import JobService

        session = AsyncMock()
        service = JobService(session)
        service.job_repo.get_by_url = AsyncMock(return_value=None)

        call_count = 0
        async def mock_create(data):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise DuplicateJobError("dup", "dup")
            return MagicMock(id="ok")

        service.job_repo.create = mock_create

        result = await service.save_jobs([
            {"title": "J1", "company": "C1", "url": "https://a.com"},
            {"title": "J2", "company": "C2", "url": "https://b.com"},
        ])
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_job_statistics(self):
        from interntrack.services.job_service import JobService

        session = AsyncMock()
        service = JobService(session)
        service.job_repo.count = AsyncMock(return_value=100)
        service.job_repo.get_salary_statistics = AsyncMock(return_value={"avg_min": 80000})
        service.job_repo.get_top_companies = AsyncMock(return_value=[("TechCorp", 10)])
        service.job_repo.get_job_type_distribution = AsyncMock(
            return_value=[(MagicMock(value="full_time"), 60)]
        )

        result = await service.get_job_statistics()

        assert result["total_jobs"] == 100
        assert result["salary_stats"]["avg_min"] == 80000
        assert len(result["top_companies"]) == 1
        assert len(result["job_types"]) == 1

    @pytest.mark.asyncio
    async def test_get_closing_soon(self):
        from interntrack.services.job_service import JobService

        session = AsyncMock()
        service = JobService(session)
        service.job_repo.get_closing_soon = AsyncMock(return_value=["j1"])

        result = await service.get_closing_soon(days=3)
        assert result == ["j1"]

    @pytest.mark.asyncio
    async def test_deactivate_expired(self):
        from interntrack.services.job_service import JobService

        session = AsyncMock()
        service = JobService(session)
        service.job_repo.deactivate_expired = AsyncMock(return_value=5)

        result = await service.deactivate_expired()
        assert result == 5


# ─── Application Service ────────────────────────────────────────────────────

class TestApplicationServiceExtended:
    """Extended tests for ApplicationService."""

    @pytest.mark.asyncio
    async def test_create_application(self):
        from interntrack.services.application_service import ApplicationService

        session = AsyncMock()
        service = ApplicationService(session)
        service.app_repo.create = AsyncMock(return_value=MagicMock(id="app-1"))

        result = await service.create_application("job-1")
        assert result.id == "app-1"

    @pytest.mark.asyncio
    async def test_get_application(self):
        from interntrack.services.application_service import ApplicationService

        session = AsyncMock()
        service = ApplicationService(session)
        service.app_repo.get_by_id = AsyncMock(return_value=MagicMock(id="app-1"))

        result = await service.get_application("app-1")
        assert result.id == "app-1"

    @pytest.mark.asyncio
    async def test_get_application_for_job(self):
        from interntrack.services.application_service import ApplicationService

        session = AsyncMock()
        service = ApplicationService(session)
        service.app_repo.get_by_job_id = AsyncMock(return_value=MagicMock(id="app-1"))

        result = await service.get_application_for_job("job-1")
        assert result.id == "app-1"

    @pytest.mark.asyncio
    async def test_update_status(self):
        from interntrack.services.application_service import ApplicationService

        session = AsyncMock()
        service = ApplicationService(session)
        service.app_repo.update_status = AsyncMock(
            return_value=MagicMock(id="app-1", status="applied")
        )

        result = await service.update_status("app-1", MagicMock(value="applied"))
        assert result.status == "applied"

    @pytest.mark.asyncio
    async def test_get_applications_by_status(self):
        from interntrack.services.application_service import ApplicationService

        session = AsyncMock()
        service = ApplicationService(session)
        service.app_repo.get_by_status = AsyncMock(return_value=["a1", "a2"])

        result = await service.get_applications_by_status(MagicMock())
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_status_counts(self):
        from interntrack.services.application_service import ApplicationService

        session = AsyncMock()
        service = ApplicationService(session)
        service.app_repo.get_status_counts = AsyncMock(
            return_value={"saved": 5, "applied": 3}
        )

        result = await service.get_status_counts()
        assert result["saved"] == 5

    @pytest.mark.asyncio
    async def test_get_application_timeline(self):
        from interntrack.services.application_service import ApplicationService

        session = AsyncMock()
        service = ApplicationService(session)
        service.app_repo.get_application_timeline = AsyncMock(return_value=[])

        result = await service.get_application_timeline(days=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_metrics(self):
        from interntrack.services.application_service import ApplicationService

        session = AsyncMock()
        service = ApplicationService(session)
        service.app_repo.get_status_counts = AsyncMock(
            return_value={"saved": 5, "applied": 3}
        )
        service.app_repo.get_rejection_rate = AsyncMock(return_value=0.1)
        service.app_repo.get_response_rate = AsyncMock(return_value=0.5)
        service.app_repo.get_recent_applications = AsyncMock(return_value=["a1"])

        result = await service.get_metrics()

        assert result["total_applications"] == 8
        assert result["rejection_rate"] == 0.1
        assert result["response_rate"] == 0.5
        assert result["recent_applications"] == 1

    @pytest.mark.asyncio
    async def test_mark_reminded(self):
        from interntrack.services.application_service import ApplicationService

        session = AsyncMock()
        service = ApplicationService(session)
        mock_app = MagicMock(id="app-1", reminded=False)
        service.app_repo.get_by_id = AsyncMock(return_value=mock_app)

        await service.mark_reminded("app-1")

        assert mock_app.reminded is True
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_reminded_not_found(self):
        from interntrack.services.application_service import ApplicationService

        session = AsyncMock()
        service = ApplicationService(session)
        service.app_repo.get_by_id = AsyncMock(return_value=None)

        await service.mark_reminded("nonexistent")
        session.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_pending_reminders(self):
        from interntrack.services.application_service import ApplicationService

        session = AsyncMock()
        service = ApplicationService(session)
        service.app_repo.get_pending_reminders = AsyncMock(return_value=["a1"])

        result = await service.get_pending_reminders()
        assert result == ["a1"]

    @pytest.mark.asyncio
    async def test_set_priority(self):
        from interntrack.services.application_service import ApplicationService

        session = AsyncMock()
        service = ApplicationService(session)
        service.app_repo.update = AsyncMock(return_value=MagicMock(id="app-1", priority=3))

        result = await service.set_priority("app-1", 3)
        assert result.priority == 3


# ─── Learning Service ───────────────────────────────────────────────────────

class TestLearningServiceExtended:
    """Extended tests for LearningService."""

    @pytest.mark.asyncio
    async def test_get_learning_paths_all(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["path1", "path2"]
        session.execute.return_value = mock_result

        result = await service.get_learning_paths()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_learning_paths_by_skill(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["path1"]
        session.execute.return_value = mock_result

        result = await service.get_learning_paths(skill_id="skill-1")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_create_learning_path(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        result = await service.create_learning_path({
            "name": "Python Basics",
            "skill_id": "skill-1",
            "resources": ["https://example.com"],
        })

        session.add.assert_called_once()
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_recommendations(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        service.ai_service.generate_learning_path = AsyncMock(return_value={
            "skills": ["docker", "kubernetes"],
            "steps": ["step1"],
        })

        mock_skill = MagicMock()
        mock_skill.name = "docker"
        mock_skill.category.value = "tool"
        mock_skill.learning_resources = ["https://docker.com"]
        service.skill_repo.get_by_name = AsyncMock(return_value=mock_skill)

        result = await service.get_recommendations(
            user_skills=["python"], target_role="DevOps Engineer"
        )

        assert result["target_role"] == "DevOps Engineer"
        assert "docker" in result["missing_skills"]
        assert len(result["recommendations"]) >= 1

    @pytest.mark.asyncio
    async def test_get_platform_resources(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        mock_path = MagicMock()
        mock_path.id = "p1"
        mock_path.name = "Python Course"
        mock_path.description = "Learn Python"
        mock_path.estimated_hours = 20
        mock_path.difficulty_level = 2

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_path]
        session.execute.return_value = mock_result

        result = await service.get_platform_resources("google_cloud")

        assert len(result) == 1
        assert result[0]["name"] == "Python Course"

    @pytest.mark.asyncio
    async def test_get_skill_gap_analysis(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        result = await service.get_skill_gap_analysis(
            user_skills=["python", "sql"],
            job_skills=["python", "docker", "kubernetes"],
        )

        assert "python" in result["matched_skills"]
        assert "docker" in result["missing_skills"]
        assert "sql" in result["extra_skills"]
        assert result["match_percentage"] > 0

    def test_get_readiness_level(self):
        from interntrack.services.learning_service import LearningService

        session = AsyncMock()
        service = LearningService(session)

        assert service._get_readiness_level(90) == "excellent"
        assert service._get_readiness_level(70) == "good"
        assert service._get_readiness_level(50) == "moderate"
        assert service._get_readiness_level(20) == "needs_improvement"
