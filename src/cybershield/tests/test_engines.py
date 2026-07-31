"""
Tests for AI Engines

Tests for deduplication, verification, scam detection, and classification engines.
"""

import pytest
from cybershield.engines.deduplication import DeduplicationEngine
from cybershield.engines.verification import VerificationEngine
from cybershield.engines.scam_detection import ScamDetectionEngine
from cybershield.engines.classification import ClassificationEngine


class TestDeduplicationEngine:
    """Tests for DeduplicationEngine."""

    @pytest.fixture
    def engine(self):
        return DeduplicationEngine()

    def test_normalize_url(self, engine):
        """Test URL normalization removes tracking params."""
        url = "https://example.com/job/123?utm_source=linkedin&utm_medium=cpc&ref=test"
        normalized = engine._normalize_url(url)
        assert "utm_source" not in normalized
        assert "utm_medium" not in normalized
        assert "job/123" in normalized

    def test_generate_hash(self, engine):
        """Test content hash generation."""
        hash1 = engine._generate_hash("Security Analyst", "Tech Corp", "Remote")
        hash2 = engine._generate_hash("Security Analyst", "Tech Corp", "Remote")
        hash3 = engine._generate_hash("Different Title", "Tech Corp", "Remote")
        assert hash1 == hash2
        assert hash1 != hash3

    def test_calculate_similarity(self, engine):
        """Test string similarity calculation."""
        sim_exact = engine._calculate_similarity("hello", "hello")
        sim_similar = engine._calculate_similarity("hello", "helo")
        sim_different = engine._calculate_similarity("hello", "world")
        assert sim_exact == 1.0
        assert sim_similar > sim_different

    @pytest.mark.asyncio
    async def test_process_empty_list(self, engine):
        """Test processing empty job list."""
        result = await engine.process([])
        assert result.success
        assert result.data["unique_count"] == 0

    @pytest.mark.asyncio
    async def test_find_duplicates(self, engine):
        """Test duplicate detection."""
        jobs = [
            {"id": "1", "title": "Security Analyst", "company_name": "Tech Corp", "url": "https://example.com/job/1"},
            {"id": "2", "title": "Security Analyst", "company_name": "Tech Corp", "url": "https://example.com/job/1?utm_source=test"},
            {"id": "3", "title": "Different Role", "company_name": "Other Corp", "url": "https://other.com/job/2"},
        ]
        result = await engine.process(jobs)
        assert result.success
        assert result.data["duplicate_groups_count"] >= 1


class TestVerificationEngine:
    """Tests for VerificationEngine."""

    @pytest.fixture
    def engine(self):
        return VerificationEngine()

    def test_check_deadline_active(self, engine):
        """Test active deadline check."""
        from datetime import datetime, timedelta, timezone
        future = datetime.now(timezone.utc) + timedelta(days=7)
        result = engine._check_deadline(future)
        assert result["active"] is True
        assert result["expired"] is False

    def test_check_deadline_expired(self, engine):
        """Test expired deadline check."""
        from datetime import datetime, timedelta, timezone
        past = datetime.now(timezone.utc) - timedelta(days=1)
        result = engine._check_deadline(past)
        assert result["active"] is False
        assert result["expired"] is True

    def test_check_deadline_none(self, engine):
        """Test None deadline."""
        result = engine._check_deadline(None)
        assert result["active"] is True

    @pytest.mark.asyncio
    async def test_process_job(self, engine):
        """Test job verification."""
        job = {
            "id": "test_1",
            "title": "Test Job",
            "company_name": "Test Corp",
            "url": "https://httpbin.org/status/200",
        }
        result = await engine.process(job)
        assert result.success
        assert "verification_score" in result.data


class TestScamDetectionEngine:
    """Tests for ScamDetectionEngine."""

    @pytest.fixture
    def engine(self):
        return ScamDetectionEngine()

    def test_critical_indicators(self, engine):
        """Test critical scam indicators detection."""
        text = "Training fee required. Guaranteed income."
        critical = engine._check_critical_indicators(text)
        assert len(critical) > 0
        assert any("training fee" in i[0].lower() for i in critical)

    def test_high_risk_indicators(self, engine):
        """Test high-risk indicators detection."""
        text = "WhatsApp only contact. No official website."
        high_risk = engine._check_high_risk_indicators(text)
        assert len(high_risk) > 0

    def test_suspicious_domain(self, engine):
        """Test suspicious domain detection."""
        result = engine._analyze_domain("https://suspicious.xyz/job/123")
        assert result["suspicious"] is True

    def test_disposable_email(self, engine):
        """Test disposable email detection."""
        result = engine._analyze_email("test@mailinator.com")
        assert result["suspicious"] is True

    @pytest.mark.asyncio
    async def test_process_scam_job(self, engine):
        """Test scam detection on suspicious job."""
        job = {
            "id": "scam_1",
            "title": "Easy Money Work From Home",
            "company_name": "",
            "description": "Training fee required. Guaranteed income. WhatsApp only.",
            "url": "https://suspicious.xyz/job/123",
        }
        result = await engine.process(job)
        assert result.success
        assert result.data["is_scam"] is True
        assert result.data["scam_score"] >= 50

    @pytest.mark.asyncio
    async def test_process_legit_job(self, engine):
        """Test scam detection on legitimate job."""
        job = {
            "id": "legit_1",
            "title": "Security Analyst",
            "company_name": "Microsoft",
            "description": "Join our security team to protect cloud infrastructure.",
            "url": "https://careers.microsoft.com/job/123",
        }
        result = await engine.process(job)
        assert result.success
        assert result.data["scam_score"] < 50


class TestClassificationEngine:
    """Tests for ClassificationEngine."""

    @pytest.fixture
    def engine(self):
        return ClassificationEngine()

    def test_classify_job_type_internship(self, engine):
        """Test internship classification."""
        text = "Summer internship position for students."
        result = engine._classify_job_type(text)
        assert result["type"] == "internship"

    def test_classify_experience_fresher(self, engine):
        """Test fresher experience classification."""
        text = "Fresher position. 0-1 years experience."
        result = engine._classify_experience_level(text)
        assert result["level"] == "fresher"

    def test_classify_security_domain_soc(self, engine):
        """Test SOC domain classification."""
        text = "SOC analyst position. SIEM monitoring experience required."
        domains = engine._classify_security_domain(text)
        assert any(d["domain"] == "SOC" for d in domains)

    def test_extract_skills(self, engine):
        """Test skill extraction."""
        text = "Python, SIEM, AWS, Docker experience required."
        skills = engine._extract_skills(text)
        skill_names = [s["skill"] for s in skills]
        assert "Python" in skill_names
        assert "AWS" in skill_names

    @pytest.mark.asyncio
    async def test_process_job(self, engine):
        """Test full job classification."""
        job = {
            "id": "class_1",
            "title": "SOC Analyst",
            "company_name": "Tech Corp",
            "description": "SOC analyst with Python and SIEM experience. 2-3 years.",
        }
        result = await engine.process(job)
        assert result.success
        assert "job_type" in result.data
        assert "experience_level" in result.data
        assert "security_domains" in result.data
        assert "skills" in result.data
