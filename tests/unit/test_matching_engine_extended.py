"""
Extended unit tests for engines/matching.py.

Covers match_job_to_user full/partial/missing skill paths, recommendations
generation, find_matching_jobs, and skill gap analysis detail.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


def _skill_row(name, category_value="programming"):
    """Build a Skill-like object for query rows."""
    skill = MagicMock()
    skill.name = name
    skill.category.value = category_value
    return skill


def _job_skill_row(skill, importance):
    """Build a (JobSkill, Skill) row."""
    js = MagicMock()
    js.skill_id = f"sk-{skill.name}"
    js.importance = importance
    return (js, skill)


def _user_skill_row(skill, proficiency):
    """Build a (UserSkill, Skill) row."""
    us = MagicMock()
    us.skill_id = f"sk-{skill.name}"
    us.proficiency_level = proficiency
    return (us, skill)


class TestMatchJobToUser:
    @pytest.mark.asyncio
    async def test_full_and_partial_and_missing(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()

        # First execute call = job skills, second = user skills
        job_skills = [
            _job_skill_row(_skill_row("Python"), importance=3),
            _job_skill_row(_skill_row("Docker"), importance=2),
            _job_skill_row(_skill_row("Kubernetes"), importance=2),
        ]
        user_skills = [
            _user_skill_row(_skill_row("Python"), proficiency=4),  # full match
            _user_skill_row(_skill_row("Docker"), proficiency=1),  # partial match
        ]

        def execute_side_effect(query):
            # job_skills table => job skills; otherwise user skills
            result = MagicMock()
            if "job_skills" in str(query):
                result.all.return_value = job_skills
            else:
                result.all.return_value = user_skills
            return result

        session.execute.side_effect = execute_side_effect

        engine = MatchingEngine(session)
        # Mock skill repo so recommendations don't hit the DB
        engine.skill_repo = AsyncMock()
        engine.skill_repo.get_by_name.return_value = MagicMock(learning_resources=[])

        result = await engine.match_job_to_user("job-1", "user-1")

        assert result["job_id"] == "job-1"
        assert "match_percentage" in result
        assert "readiness_level" in result

        matched_names = [m["name"] for m in result["matched_skills"]]
        assert "Python" in matched_names
        assert all(m["match_type"] == "full" for m in result["matched_skills"])

        partial_names = [p["name"] for p in result["partial_skills"]]
        assert "Docker" in partial_names
        assert result["partial_skills"][0]["gap"] == 1

        missing_names = [m["name"] for m in result["missing_skills"]]
        assert "Kubernetes" in missing_names

        # Partial counts as half: 3 + 2*0.5 = 4 out of 7 -> 57.14
        assert result["match_percentage"] == 57.14

    @pytest.mark.asyncio
    async def test_all_missing_returns_zero_percent(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()

        job_skills = [_job_skill_row(_skill_row("Go"), importance=2)]
        user_skills = []

        def execute_side_effect(query):
            result = MagicMock()
            if "job_skills" in str(query):
                result.all.return_value = job_skills
            else:
                result.all.return_value = user_skills
            return result

        session.execute.side_effect = execute_side_effect

        engine = MatchingEngine(session)
        engine.skill_repo = AsyncMock()
        engine.skill_repo.get_by_name.return_value = MagicMock(learning_resources=None)

        result = await engine.match_job_to_user("job-2", "user-2")

        assert result["match_percentage"] == 0.0
        assert result["missing_skills"][0]["name"] == "Go"
        assert result["readiness_level"] == "needs_improvement"
        # Recommendations are generated for missing skills
        assert result["recommendations"][0]["skill"] == "Go"


class TestRecommendations:
    @pytest.mark.asyncio
    async def test_recommendations_use_skill_resources(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()
        engine = MatchingEngine(session)

        skill = MagicMock()
        skill.learning_resources = [
            {"name": "Resource 1", "url": "https://example.com/1"},
            {"name": "Resource 2", "url": "https://example.com/2"},
            {"name": "Resource 3", "url": "https://example.com/3"},
            {"name": "Resource 4", "url": "https://example.com/4"},
        ]
        engine.skill_repo = AsyncMock()
        engine.skill_repo.get_by_name.return_value = skill

        missing = [{"name": "Docker", "category": "tool", "importance": 2}]
        recommendations = await engine._get_recommendations(missing)

        assert len(recommendations) == 1
        assert recommendations[0]["skill"] == "Docker"
        assert len(recommendations[0]["resources"]) == 3  # capped at 3

    @pytest.mark.asyncio
    async def test_recommendations_fallback_defaults(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()
        engine = MatchingEngine(session)
        engine.skill_repo = AsyncMock()
        engine.skill_repo.get_by_name.return_value = None  # skill not found

        missing = [{"name": "Terraform", "category": "tool", "importance": 2}]
        recommendations = await engine._get_recommendations(missing)

        assert len(recommendations) == 1
        assert "terraform" in recommendations[0]["resources"][0]["url"].lower()

    @pytest.mark.asyncio
    async def test_recommendations_limited_to_five(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()
        engine = MatchingEngine(session)
        engine.skill_repo = AsyncMock()
        engine.skill_repo.get_by_name.return_value = MagicMock(learning_resources=[])

        missing = [
            {"name": f"Skill-{i}", "category": "tool", "importance": 1}
            for i in range(8)
        ]
        recommendations = await engine._get_recommendations(missing)

        assert len(recommendations) == 5


class TestFindMatchingJobs:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_user_skills(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result

        engine = MatchingEngine(session)
        jobs = await engine.find_matching_jobs("user-1")
        assert jobs == []

    @pytest.mark.asyncio
    async def test_returns_matching_jobs(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()

        # User skills query selects Skill.name -> (name,) rows
        user_skills = [("python",)]

        # Jobs list
        job = MagicMock()
        job.id = "job-9"
        job.title = "Python Dev"
        job.company = "Acme"
        job.location = "Remote"
        job.url = "https://acme.com/job/9"
        job.salary_min = 50000
        job.salary_max = 90000
        job.is_active = True

        job_skills = [
            _job_skill_row(_skill_row("Python"), importance=2),
            _job_skill_row(_skill_row("Django"), importance=1),
        ]

        def execute_side_effect(query):
            result = MagicMock()
            q = str(query)
            if "user_skills" in q:
                result.all.return_value = user_skills
            elif "job_skills" in q:
                result.all.return_value = job_skills
            else:
                # Job listing query
                result.scalars.return_value.all.return_value = [job]
            return result

        session.execute.side_effect = execute_side_effect

        engine = MatchingEngine(session)
        jobs = await engine.find_matching_jobs("user-1", min_match=50.0)

        assert len(jobs) == 1
        assert jobs[0]["job"]["id"] == "job-9"
        assert jobs[0]["match_percentage"] == 50.0  # 1 of 2 skills
        assert jobs[0]["matched_skills"] == 1
        assert jobs[0]["total_skills"] == 2

    @pytest.mark.asyncio
    async def test_filters_jobs_below_min_match(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()

        user_skills = [("python",)]

        job = MagicMock()
        job.id = "job-10"
        job.title = "Rust Dev"
        job.company = "Beta"
        job.location = "NYC"
        job.url = "https://beta.com/job/10"
        job.salary_min = None
        job.salary_max = None
        job.is_active = True

        job_skills = [_job_skill_row(_skill_row("Rust"), importance=2)]

        def execute_side_effect(query):
            result = MagicMock()
            q = str(query)
            if "user_skills" in q:
                result.all.return_value = user_skills
            elif "job_skills" in q:
                result.all.return_value = job_skills
            else:
                result.scalars.return_value.all.return_value = [job]
            return result

        session.execute.side_effect = execute_side_effect

        engine = MatchingEngine(session)
        jobs = await engine.find_matching_jobs("user-1", min_match=80.0)

        assert jobs == []


class TestSkillGapAnalysisDetail:
    @pytest.mark.asyncio
    async def test_matched_and_missing_with_priorities(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()

        user_result = MagicMock()
        user_result.all.return_value = [
            ("Python", MagicMock(value="programming")),
            ("SQL", MagicMock(value="tool")),
        ]

        def execute_side_effect(query):
            result = MagicMock()
            if "user_skills" in str(query):
                result.all.return_value = user_result.all.return_value
            return result

        session.execute.side_effect = execute_side_effect

        engine = MatchingEngine(session)
        result = await engine.get_skill_gap_analysis("user-1", "backend developer")

        assert result["target_role"] == "backend developer"
        assert result["total_required"] == 8
        matched_names = [m["name"].lower() for m in result["matched_skills"]]
        assert "python" in matched_names
        assert "sql" in matched_names
        assert result["match_percentage"] == 25.0  # 2 of 8
        # Missing skills sorted by priority descending
        missing = result["missing_skills"]
        assert missing
        assert all("priority" in m for m in missing)
        assert missing[0]["priority"] >= missing[-1]["priority"]
        assert result["readiness_level"] == "needs_improvement"

    @pytest.mark.asyncio
    async def test_perfect_match_excellent_readiness(self):
        from interntrack.engines.matching import MatchingEngine

        session = AsyncMock()

        user_skills = [
            "python",
            "javascript",
            "sql",
            "rest api",
            "git",
            "docker",
            "postgresql",
            "redis",
        ]

        def execute_side_effect(query):
            result = MagicMock()
            if "user_skills" in str(query):
                result.all.return_value = [
                    (s, MagicMock(value="programming")) for s in user_skills
                ]
            return result

        session.execute.side_effect = execute_side_effect

        engine = MatchingEngine(session)
        result = await engine.get_skill_gap_analysis("user-1", "backend developer")

        assert result["match_percentage"] == 100.0
        assert result["missing_skills"] == []
        assert result["readiness_level"] == "excellent"
