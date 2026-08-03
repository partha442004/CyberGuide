"""
Unit tests for the remaining uncovered branches of the scam detection engine
(``src/cybershield/engines/scam_detection.py``) and the deduplication engine
(``src/cybershield/engines/deduplication.py``).
"""

from unittest.mock import patch

import pytest

from cybershield.engines.deduplication import DeduplicationEngine
from cybershield.engines.scam_detection import ScamDetectionEngine


class TestScamDetectionRound9:
    """Branches not yet covered in ScamDetectionEngine."""

    @pytest.fixture
    def engine(self):
        return ScamDetectionEngine()

    def test_medium_risk_indicators_found(self, engine):
        """Medium-risk indicators append with score 40."""
        found = engine._check_medium_risk_indicators(
            "Urgent hiring! Immediate join. Too good to be true."
        )
        assert len(found) > 0
        assert all(score == 40 for _, score in found)

    def test_domain_hosted_on_suspicious_platform(self, engine):
        """URLs hosted on free-blog platforms are flagged."""
        result = engine._analyze_domain("https://jobs.blogspot.com/careers/1")
        assert result["suspicious"] is True
        assert "Hosted on" in result["reason"]

    def test_domain_invalid_url_raises(self, engine):
        """Malformed URLs fall back to suspicious with Invalid URL format."""
        with patch("cybershield.engines.scam_detection.urlparse", side_effect=ValueError("bad")):
            result = engine._analyze_domain("https://example.com/job/1")
        assert result["suspicious"] is True
        assert result["reason"] == "Invalid URL format"

    def test_content_score_uses_weighted_average_without_critical(self, engine):
        """Non-critical indicators use the max*0.6 + avg*0.4 blend."""
        content = engine._analyze_content(
            {
                "title": "Earn lakhs working from home",
                "description": "WhatsApp number. Urgent hiring. No interview.",
                "company_name": "Acme",
            }
        )
        # No critical indicators present -> weighted average path.
        assert content["critical_indicators"] == []
        assert content["score"] > 0
        assert content["total_indicators"] > 1

    @pytest.mark.asyncio
    async def test_process_flags_high_and_email(self, engine):
        """process() builds HIGH and EMAIL flags when applicable."""
        job = {
            "id": "flags-1",
            "title": "Earn lakhs instantly",
            "company_name": "Acme",
            "description": "WhatsApp number. No interview. Pay to apply.",
            "url": "https://jobs.blogspot.com/careers/1",
            "contact_email": "recruiter@gmail.com",
        }
        result = await engine.process(job)
        assert result.success
        flags = result.data["flags"]
        assert any(f.startswith("HIGH:") for f in flags)
        assert any(f.startswith("EMAIL:") for f in flags)


class TestDeduplicationRound9:
    """Branches not yet covered in DeduplicationEngine."""

    @pytest.fixture
    def engine(self):
        return DeduplicationEngine()

    def test_normalize_url_falls_back_on_parse_error(self, engine):
        """Malformed URLs fall back to lowercased/stripped raw url."""
        with patch("cybershield.engines.deduplication.urlparse", side_effect=ValueError("bad")):
            normalized = engine._normalize_url("HTTPS://Example.COM/Job/1")
        assert normalized == "https://example.com/job/1"

    def test_are_urls_similar_empty_inputs(self, engine):
        """Empty URL inputs return (False, 0.0)."""
        assert engine._are_urls_similar("", "https://example.com/job/1") == (False, 0.0)
        assert engine._are_urls_similar("https://example.com/job/1", "") == (False, 0.0)

    def test_are_titles_similar_empty_inputs(self, engine):
        """Empty title inputs return (False, 0.0)."""
        assert engine._are_titles_similar("", "Security Analyst") == (False, 0.0)
        assert engine._are_titles_similar("Security Analyst", "") == (False, 0.0)

    def test_select_canonical_prefers_posting_date(self, engine):
        """Jobs with a posting date score higher."""
        with_date = {
            "id": "dated",
            "title": "Security Analyst",
            "company_name": "Acme",
            "url": "https://jobboard.example/job/1",
            "posting_date": "2026-07-01",
        }
        without_date = {
            "id": "undated",
            "title": "Security Analyst",
            "company_name": "Acme",
            "url": "https://jobboard.example/job/2",
        }
        canonical = engine._select_canonical([without_date, with_date])
        assert canonical["id"] == "dated"

    @pytest.mark.asyncio
    async def test_find_duplicates_returns_result_on_failure(self, engine):
        """find_duplicates propagates an unsuccessful engine result."""
        new_job = {"id": "new", "title": "T", "company_name": "C", "url": "https://x.job"}
        engine.process = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock(
            return_value=engine._create_result(False, data={})
        )
        result = await engine.find_duplicates(new_job, [])
        assert result.success is False

    @pytest.mark.asyncio
    async def test_find_duplicates_detects_existing_duplicate(self, engine):
        """find_duplicates reports is_duplicate when the new job is a dup."""
        new_job = {
            "id": "new",
            "title": "Security Analyst",
            "company_name": "Tech Corp",
            "url": "https://example.com/job/new",
        }
        existing = [
            {
                "id": "old",
                "title": "Security Analyst",
                "company_name": "Tech Corp",
                "url": "https://example.com/job/old",
                "description": "Full description of the role.",
                "salary_min": 90000,
                "apply_url": "https://example.com/apply",
            }
        ]
        result = await engine.find_duplicates(new_job, existing)
        assert result.success
        assert result.data["is_duplicate"] is True
