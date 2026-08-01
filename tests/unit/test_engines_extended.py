"""Extended unit tests for engines module — covers async methods and edge cases."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_classification_engine():
    from interntrack.engines.classification import ClassificationEngine
    session = AsyncMock()
    return ClassificationEngine(session)


def _make_dedup_engine():
    from interntrack.engines.deduplication import DeduplicationEngine
    session = AsyncMock()
    engine = DeduplicationEngine(session)
    engine.job_repo = AsyncMock()
    return engine


def _make_verification_engine():
    from interntrack.engines.verification import VerificationEngine
    session = AsyncMock()
    engine = VerificationEngine(session)
    engine.job_repo = AsyncMock()
    return engine


# ─── Classification Engine ──────────────────────────────────────────────────

class TestClassificationEngineExtended:
    """Extended tests for ClassificationEngine async methods."""

    @pytest.mark.asyncio
    async def test_extract_skills_ai_and_description(self):
        engine = _make_classification_engine()

        mock_skill = MagicMock()
        mock_skill.id = "skill-1"
        mock_skill.name = "python"
        mock_skill.category.value = "programming"

        engine.skill_repo.create_or_get = AsyncMock(return_value=mock_skill)

        result = await engine._extract_skills(
            ai_skills=["python"],
            description="We also need Django and Docker experience.",
        )

        assert len(result) >= 1
        assert engine.skill_repo.create_or_get.call_count >= 1

    @pytest.mark.asyncio
    async def test_extract_skills_no_ai_skills(self):
        engine = _make_classification_engine()

        mock_skill = MagicMock()
        mock_skill.id = "skill-1"
        mock_skill.name = "react"
        mock_skill.category.value = "framework"

        engine.skill_repo.create_or_get = AsyncMock(return_value=mock_skill)

        result = await engine._extract_skills(
            ai_skills=[],
            description="We need React and TypeScript.",
        )

        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_extract_skills_deduplication(self):
        engine = _make_classification_engine()

        mock_skill = MagicMock()
        mock_skill.id = "skill-1"
        mock_skill.name = "python"
        mock_skill.category.value = "programming"

        engine.skill_repo.create_or_get = AsyncMock(return_value=mock_skill)

        result = await engine._extract_skills(
            ai_skills=["python"],
            description="Python experience required.",
        )

        python_calls = [
            c for c in engine.skill_repo.create_or_get.call_args_list
            if c[0][0] == "python"
        ]
        assert len(python_calls) == 1

    @pytest.mark.asyncio
    async def test_get_skill_demand(self):
        engine = _make_classification_engine()

        mock_row = MagicMock()
        mock_row.name = "python"
        mock_row.category.value = "programming"
        mock_row.demand = 5

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        engine.session.execute.return_value = mock_result

        result = await engine.get_skill_demand()

        assert len(result) == 1
        assert result[0]["skill"] == "python"
        assert result[0]["demand"] == 5

    @pytest.mark.asyncio
    async def test_get_skill_demand_empty(self):
        engine = _make_classification_engine()

        mock_result = MagicMock()
        mock_result.all.return_value = []
        engine.session.execute.return_value = mock_result

        result = await engine.get_skill_demand()
        assert result == []

    def test_categorize_skill_more_programming(self):
        engine = _make_classification_engine()
        from interntrack.domain.enums import SkillCategory

        assert engine._categorize_skill("c++") == SkillCategory.PROGRAMMING
        assert engine._categorize_skill("rust") == SkillCategory.PROGRAMMING
        assert engine._categorize_skill("ruby") == SkillCategory.PROGRAMMING
        assert engine._categorize_skill("swift") == SkillCategory.PROGRAMMING
        assert engine._categorize_skill("kotlin") == SkillCategory.PROGRAMMING

    def test_categorize_skill_more_frameworks(self):
        engine = _make_classification_engine()
        from interntrack.domain.enums import SkillCategory

        assert engine._categorize_skill("express") == SkillCategory.FRAMEWORK
        assert engine._categorize_skill("spring") == SkillCategory.FRAMEWORK
        assert engine._categorize_skill("nextjs") == SkillCategory.FRAMEWORK

    def test_categorize_skill_more_tools(self):
        engine = _make_classification_engine()
        from interntrack.domain.enums import SkillCategory

        assert engine._categorize_skill("gcp") == SkillCategory.TOOL
        assert engine._categorize_skill("azure") == SkillCategory.TOOL
        assert engine._categorize_skill("redis") == SkillCategory.TOOL
        assert engine._categorize_skill("mysql") == SkillCategory.TOOL

    def test_extract_skills_from_text_more_patterns(self):
        engine = _make_classification_engine()

        text = "We need TypeScript, React, Node.js, and GraphQL experience."
        skills = engine._extract_skills_from_text(text)

        assert "typescript" in skills
        assert "react" in skills
        assert "node.js" in skills
        assert "graphql" in skills


# ─── Deduplication Engine ───────────────────────────────────────────────────

class TestDeduplicationEngineExtended:
    """Extended tests for DeduplicationEngine."""

    @pytest.mark.asyncio
    async def test_filter_unique_batch_duplicates(self):
        engine = _make_dedup_engine()
        engine.job_repo.get_by_url.return_value = None
        engine.job_repo.find_duplicate.return_value = None

        jobs = [
            {"title": "Python Dev", "company": "TechCorp", "url": "https://example.com/1"},
            {"title": "Python Dev", "company": "TechCorp", "url": "https://example.com/1"},
            {"title": "Java Dev", "company": "OtherCorp", "url": "https://example.com/2"},
        ]

        result = await engine.filter_unique(jobs)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filter_unique_finds_existing_by_title(self):
        engine = _make_dedup_engine()
        engine.job_repo.get_by_url.return_value = None
        engine.job_repo.find_duplicate.return_value = MagicMock(id="existing")

        jobs = [
            {"title": "Python Dev", "company": "TechCorp", "url": "https://example.com/1", "source": "linkedin"},
        ]

        result = await engine.filter_unique(jobs)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_find_existing_by_url(self):
        engine = _make_dedup_engine()
        engine.job_repo.get_by_url.return_value = MagicMock(id="found-by-url")

        result = await engine._find_existing({"url": "https://example.com"})
        assert result.id == "found-by-url"

    @pytest.mark.asyncio
    async def test_find_existing_by_title_company(self):
        engine = _make_dedup_engine()
        engine.job_repo.get_by_url.return_value = None
        engine.job_repo.find_duplicate.return_value = MagicMock(id="found-by-title")

        result = await engine._find_existing({
            "title": "Dev", "company": "Co", "source": "hackernews",
        })
        assert result.id == "found-by-title"

    @pytest.mark.asyncio
    async def test_find_existing_not_found(self):
        engine = _make_dedup_engine()
        engine.job_repo.get_by_url.return_value = None
        engine.job_repo.find_duplicate.return_value = None

        result = await engine._find_existing({
            "title": "Dev", "company": "Co", "url": "https://example.com",
        })
        assert result is None

    @pytest.mark.asyncio
    async def test_find_duplicates_in_database(self):
        engine = _make_dedup_engine()

        job1 = MagicMock()
        job1.id, job1.title, job1.company, job1.url = "j1", "Python Developer", "TechCorp", "https://example.com/1"
        job2 = MagicMock()
        job2.id, job2.title, job2.company, job2.url = "j2", "Python Developer", "TechCorp", "https://example.com/2"
        job3 = MagicMock()
        job3.id, job3.title, job3.company, job3.url = "j3", "Java Developer", "OtherCorp", "https://different.com/1"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [job1, job2, job3]
        engine.session.execute.return_value = mock_result

        duplicates = await engine.find_duplicates_in_database(threshold=0.85)

        assert len(duplicates) >= 1

    @pytest.mark.asyncio
    async def test_find_duplicates_in_database_empty(self):
        engine = _make_dedup_engine()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        engine.session.execute.return_value = mock_result

        duplicates = await engine.find_duplicates_in_database()
        assert duplicates == []

    def test_compute_hash_case_insensitive(self):
        engine = _make_dedup_engine()
        job1 = {"title": "Python Dev", "company": "TechCorp", "url": "https://example.com"}
        job2 = {"title": "python dev", "company": "techcorp", "url": "https://example.com"}
        assert engine._compute_hash(job1) == engine._compute_hash(job2)

    def test_calculate_similarity_partial_match(self):
        engine = _make_dedup_engine()
        job1 = {"title": "Python Developer", "company": "TechCorp", "url": "https://example.com/1"}
        job2 = {"title": "Python Engineer", "company": "TechCorp", "url": "https://example.com/2"}
        similarity = engine.calculate_similarity(job1, job2)
        assert 0.5 < similarity < 1.0

    def test_normalize_url_http(self):
        engine = _make_dedup_engine()
        assert engine._normalize_url("http://example.com") == "example.com"

    def test_normalize_url_www(self):
        engine = _make_dedup_engine()
        assert engine._normalize_url("https://www.example.com") == "example.com"

    def test_normalize_url_trailing_slash(self):
        engine = _make_dedup_engine()
        assert engine._normalize_url("https://example.com/") == "example.com"


# ─── Verification Engine ────────────────────────────────────────────────────

class TestVerificationEngineExtended:
    """Extended tests for VerificationEngine."""

    @pytest.mark.asyncio
    async def test_check_link_health_alive(self):
        engine = _make_verification_engine()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com/job/1"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            result = await engine.check_link_health("https://example.com/job/1")

        assert result["is_alive"] is True
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_check_link_health_dead(self):
        engine = _make_verification_engine()

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.url = "https://example.com/job/1"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            result = await engine.check_link_health("https://example.com/job/1")

        assert result["is_alive"] is False
        assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_check_link_health_exception(self):
        engine = _make_verification_engine()

        mock_client = AsyncMock()
        mock_client.head.side_effect = Exception("Connection refused")
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            result = await engine.check_link_health("https://dead.example.com")

        assert result["is_alive"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_check_link_health_redirect(self):
        engine = _make_verification_engine()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://new.example.com/job/1"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            result = await engine.check_link_health("https://old.example.com/job/1")

        assert result["is_alive"] is True
        assert result["redirect_url"] == "https://new.example.com/job/1"

    @pytest.mark.asyncio
    async def test_verify_all_links_with_ids(self):
        engine = _make_verification_engine()

        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.title = "Python Dev"
        mock_job.url = "https://example.com"

        engine.job_repo.get_by_id = AsyncMock(return_value=mock_job)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            results = await engine.verify_all_links(job_ids=["job-1"])

        assert len(results) == 1
        assert results[0]["job_id"] == "job-1"

    @pytest.mark.asyncio
    async def test_verify_all_links_no_ids(self):
        engine = _make_verification_engine()

        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.title = "Dev"
        mock_job.url = "https://example.com"

        engine.job_repo.get_all = AsyncMock(return_value=[mock_job])

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            results = await engine.verify_all_links()

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_verify_all_links_filters_none(self):
        engine = _make_verification_engine()

        engine.job_repo.get_by_id = AsyncMock(
            side_effect=[MagicMock(id="j1", title="Dev", url="https://a.com"), None]
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://a.com"

        mock_client = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        fake_httpx = MagicMock()
        fake_httpx.AsyncClient.return_value = mock_cm

        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            results = await engine.verify_all_links(job_ids=["j1", "j2"])

        assert len(results) == 1

    def test_validate_salary_no_salary(self):
        engine = _make_verification_engine()
        assert engine._validate_salary({}) == []

    def test_validate_salary_normal(self):
        engine = _make_verification_engine()
        assert engine._validate_salary({"salary_min": 50000, "salary_max": 100000}) == []

    def test_validate_salary_unrealistic(self):
        engine = _make_verification_engine()
        issues = engine._validate_salary({"salary_min": 500000, "salary_max": 2000000})
        assert any("suspicious" in i.lower() for i in issues)

    def test_check_spam_guaranteed_income(self):
        engine = _make_verification_engine()
        job_data = {
            "title": "Easy Job", "company": "Co", "url": "https://example.com",
            "description": "Guaranteed income of $5000 per week!",
        }
        issues = engine._check_spam(job_data)
        assert len(issues) > 0

    def test_check_spam_no_match(self):
        engine = _make_verification_engine()
        job_data = {
            "title": "Python Developer", "company": "TechCorp", "url": "https://example.com",
            "description": "Build scalable APIs with Python.",
        }
        issues = engine._check_spam(job_data)
        assert issues == []

    def test_validate_url_http(self):
        engine = _make_verification_engine()
        assert engine._validate_url("http://example.com") == []
