"""
Tests for AI Engines

Tests for deduplication, verification, scam detection, and classification engines.
"""

import pytest

from cybershield.engines.classification import ClassificationEngine
from cybershield.engines.deduplication import DeduplicationEngine
from cybershield.engines.scam_detection import ScamDetectionEngine
from cybershield.engines.verification import VerificationEngine


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
            {
                "id": "1",
                "title": "Security Analyst",
                "company_name": "Tech Corp",
                "url": "https://example.com/job/1",
            },
            {
                "id": "2",
                "title": "Security Analyst",
                "company_name": "Tech Corp",
                "url": "https://example.com/job/1?utm_source=test",
            },
            {
                "id": "3",
                "title": "Different Role",
                "company_name": "Other Corp",
                "url": "https://other.com/job/2",
            },
        ]
        result = await engine.process(jobs)
        assert result.success
        assert result.data["duplicate_groups_count"] >= 1

    def test_normalize_url_removes_fragment_and_slash(self, engine):
        """Normalization strips fragments and trailing slashes."""
        normalized = engine._normalize_url("https://example.com/job/1/#section")
        assert "section" not in normalized
        assert normalized.endswith("/job/1")

    def test_normalize_url_empty(self, engine):
        """Empty URL normalizes to empty string."""
        assert engine._normalize_url("") == ""
        assert engine._normalize_url(None) == ""

    def test_generate_hash_case_insensitive_and_blank_skipped(self, engine):
        """Hashes ignore case, whitespace, and blank parts."""
        h1 = engine._generate_hash("Security Analyst", "Tech Corp")
        h2 = engine._generate_hash("security analyst", "tech corp")
        h3 = engine._generate_hash("Security Analyst", "", "Tech Corp")
        assert h1 == h2
        assert h1 == h3
        assert len(h1) == 64  # sha256 hex digest

    def test_calculate_similarity_empty_inputs(self, engine):
        """Empty similarity inputs score zero."""
        assert engine._calculate_similarity("", "hello") == 0.0
        assert engine._calculate_similarity("hello", "") == 0.0
        assert engine._calculate_similarity("", "") == 0.0

    def test_select_canonical_prefers_complete_official_job(self, engine):
        """Canonical selection prefers official URLs and richer data."""
        scraped = {
            "id": "scraped",
            "title": "Security Analyst",
            "company_name": "Acme Corp",
            "url": "https://jobboard.example/job/1",
        }
        official = {
            "id": "official",
            "title": "Security Analyst",
            "company_name": "Acme Corp",
            "url": "https://acmecorp.com/careers/job/1",
            "description": "Full description",
            "salary_min": 90000,
            "deadline": "2026-12-31",
            "apply_url": "https://acmecorp.com/apply/1",
            "source": "company_acme",
        }
        canonical = engine._select_canonical([scraped, official])
        assert canonical["id"] == "official"

    def test_select_canonical_single_job(self, engine):
        """A single job is its own canonical."""
        job = {"id": "only", "title": "T"}
        assert engine._select_canonical([job]) is job

    @pytest.mark.asyncio
    async def test_find_duplicates_not_duplicate(self, engine):
        """find_duplicates returns is_duplicate False for distinct jobs."""
        new_job = {
            "id": "new",
            "title": "Unique Role",
            "company_name": "Distinct Corp",
            "url": "https://distinct.example/job/new",
        }
        existing = [
            {
                "id": "old",
                "title": "Security Analyst",
                "company_name": "Tech Corp",
                "url": "https://example.com/job/old",
            }
        ]
        result = await engine.find_duplicates(new_job, existing)
        assert result.success
        assert result.data["is_duplicate"] is False


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

    def test_check_deadline_naive_datetime(self, engine):
        """Naive datetimes are treated as UTC."""
        from datetime import datetime, timedelta

        future_naive = datetime.now() + timedelta(days=3)
        result = engine._check_deadline(future_naive)
        assert result["active"] is True

    def test_calculate_verification_score_empty(self, engine):
        """Empty checks score zero."""
        assert engine._calculate_verification_score([]) == 0.0

    def test_calculate_verification_score_weighted(self, engine):
        """Weights only count toward passed checks."""
        checks = [
            {"type": "url_valid", "passed": True},
            {"type": "apply_url_valid", "passed": False},
            {"type": "deadline_active", "passed": True},
        ]
        score = engine._calculate_verification_score(checks)
        # passed weights (0.3 + 0.2) / total weight (0.3 + 0.2 + 0.2)
        assert score == round(0.5 / 0.7, 2)

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

    def test_email_none_and_professional(self, engine):
        """Missing or professional emails are not suspicious."""
        assert engine._analyze_email("")["suspicious"] is False
        assert engine._analyze_email(None)["suspicious"] is False
        assert engine._analyze_email("hr@acmecorp.com")["suspicious"] is False

    def test_email_personal_provider(self, engine):
        """Personal email providers in professional context are suspicious."""
        result = engine._analyze_email("recruiter@gmail.com")
        assert result["suspicious"] is True

    def test_domain_typosquatting(self, engine):
        """Typosquatting of known companies is suspicious."""
        result = engine._analyze_domain("https://microsoft-jobs.xyz/careers")
        assert result["suspicious"] is True

    def test_domain_legit(self, engine):
        """Legit non-company domains are not suspicious."""
        result = engine._analyze_domain("https://jobs.acmecorp.com/job/1")
        assert result["suspicious"] is False

    def test_domain_empty(self, engine):
        """Empty URL is suspicious."""
        result = engine._analyze_domain("")
        assert result["suspicious"] is True

    def test_calculate_scam_score_risk_levels(self, engine):
        """Risk levels and actions map correctly."""
        clean = {"score": 0.0}
        assert (
            engine._calculate_scam_score(clean, {"suspicious": False}, {"suspicious": False})[
                "risk_level"
            ]
            == "low"
        )

        medium = {"score": 35.0}
        medium_res = engine._calculate_scam_score(
            medium, {"suspicious": False}, {"suspicious": False}
        )
        assert medium_res["risk_level"] == "medium"
        assert medium_res["action"] == "flag"

        high = {"score": 55.0}
        high_res = engine._calculate_scam_score(high, {"suspicious": False}, {"suspicious": False})
        assert high_res["risk_level"] == "high"
        assert high_res["action"] == "warn"

        critical = {"score": 80.0}
        critical_res = engine._calculate_scam_score(
            critical, {"suspicious": False}, {"suspicious": False}
        )
        assert critical_res["risk_level"] == "critical"
        assert critical_res["action"] == "block"

    def test_calculate_scam_score_breakdown(self, engine):
        """Breakdown reports content score plus domain/email penalties."""
        content = {"score": 40.0}
        result = engine._calculate_scam_score(content, {"suspicious": True}, {"suspicious": True})
        breakdown = result["breakdown"]
        assert breakdown["content_score"] == 40.0
        assert breakdown["domain_penalty"] == 25
        assert breakdown["email_penalty"] == 15
        # 40 + 25 + 15 capped at 100
        assert result["score"] == 80.0

    @pytest.mark.asyncio
    async def test_analyze_batch_counts_scams(self, engine):
        """Batch analysis reports scam vs safe counts."""
        scam_job = {
            "id": "s1",
            "title": "Easy Money",
            "company_name": "",
            "description": "Training fee required. Guaranteed income.",
            "url": "https://suspicious.xyz/job/1",
        }
        safe_job = {
            "id": "ok1",
            "title": "Security Analyst",
            "company_name": "Microsoft",
            "description": "Join our security team.",
            "url": "https://careers.microsoft.com/job/1",
        }
        result = await engine.analyze_batch([scam_job, safe_job])
        assert result.success
        assert result.data["total_analyzed"] == 2
        assert result.data["scam_detected"] == 1
        assert result.data["safe_jobs"] == 1

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

    def test_classify_experience_years_extraction(self, engine):
        """Explicit years fall into experience buckets."""
        assert (
            engine._classify_experience_level("Requires 10 years experience")["level"] == "senior"
        )
        assert engine._classify_experience_level("3-5 years experience")["level"] == "mid"
        assert engine._classify_experience_level("No years mentioned")["level"] == "entry"

    @pytest.mark.asyncio
    async def test_classify_batch_aggregates(self, engine):
        """Batch classification aggregates domains and skills."""
        jobs = [
            {
                "id": "c1",
                "title": "SOC Analyst",
                "description": "Python and SIEM experience.",
            },
            {
                "id": "c2",
                "title": "Cloud Security Engineer",
                "description": "AWS and Docker experience.",
            },
        ]
        result = await engine.classify_batch(jobs)
        assert result.success
        assert result.data["total_classified"] == 2
        assert result.data["top_domains"]
        assert result.data["top_skills"]
