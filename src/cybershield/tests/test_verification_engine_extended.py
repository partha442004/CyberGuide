"""
Extended tests for the VerificationEngine.

Covers _check_url success/error branches (405 fallback, 4xx, timeouts,
request errors, unexpected errors), process() with apply_url, string
deadlines, redirect loops, and verify_batch concurrency.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cybershield.engines.verification import VerificationEngine


class _FakeResponse:
    def __init__(self, status_code=200, url="https://example.com/job"):
        self.status_code = status_code
        self.url = url


@pytest.fixture
def engine():
    return VerificationEngine()


class TestCheckUrl:
    @pytest.mark.asyncio
    async def test_empty_url(self, engine):
        result = await engine._check_url("")
        assert result["valid"] is False
        assert result["error"] == "No URL provided"

    @pytest.mark.asyncio
    async def test_successful_head(self, engine):
        mock_client = AsyncMock()
        mock_client.head.return_value = _FakeResponse(200, "https://example.com/job")
        mock_client.get = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("cybershield.engines.verification.httpx.AsyncClient", return_value=mock_client):
            result = await engine._check_url("https://example.com/job")
        assert result["valid"] is True
        assert result["status_code"] == 200
        assert result["redirect_url"] is None
        mock_client.get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_405_falls_back_to_get(self, engine):
        mock_client = AsyncMock()
        mock_client.head.return_value = _FakeResponse(405)
        mock_client.get.return_value = _FakeResponse(200, "https://example.com/job")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("cybershield.engines.verification.httpx.AsyncClient", return_value=mock_client):
            result = await engine._check_url("https://example.com/job")
        assert result["valid"] is True
        assert result["status_code"] == 200
        mock_client.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_404_marks_invalid(self, engine):
        mock_client = AsyncMock()
        mock_client.head.return_value = _FakeResponse(404)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("cybershield.engines.verification.httpx.AsyncClient", return_value=mock_client):
            result = await engine._check_url("https://example.com/gone")
        assert result["valid"] is False
        assert result["error"] == "HTTP 404"

    @pytest.mark.asyncio
    async def test_redirect_detected(self, engine):
        mock_client = AsyncMock()
        mock_client.head.return_value = _FakeResponse(301, "https://example.com/new-job")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("cybershield.engines.verification.httpx.AsyncClient", return_value=mock_client):
            result = await engine._check_url("https://example.com/old-job")
        assert result["redirect_url"] == "https://example.com/new-job"

    @pytest.mark.asyncio
    async def test_timeout(self, engine):
        import httpx

        mock_client = AsyncMock()
        mock_client.head.side_effect = httpx.TimeoutException("timeout")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("cybershield.engines.verification.httpx.AsyncClient", return_value=mock_client):
            result = await engine._check_url("https://example.com/slow")
        assert result["valid"] is False
        assert result["error"] == "Timeout"

    @pytest.mark.asyncio
    async def test_request_error(self, engine):
        import httpx

        mock_client = AsyncMock()
        mock_client.head.side_effect = httpx.ConnectError("dns fail")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("cybershield.engines.verification.httpx.AsyncClient", return_value=mock_client):
            result = await engine._check_url("https://example.com")
        assert result["valid"] is False
        assert "dns fail" in (result["error"] or "")

    @pytest.mark.asyncio
    async def test_unexpected_error(self, engine):
        mock_client = AsyncMock()
        mock_client.head.side_effect = RuntimeError("weird")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("cybershield.engines.verification.httpx.AsyncClient", return_value=mock_client):
            result = await engine._check_url("https://example.com")
        assert result["valid"] is False
        assert "Unexpected error" in (result["error"] or "")


class TestProcess:
    @pytest.mark.asyncio
    async def test_process_full_job_with_apply_url(self, engine, monkeypatch):
        job = {
            "id": "j1",
            "url": "https://example.com/job",
            "apply_url": "https://example.com/apply",
            "company_name": "Acme Corp",
            "deadline": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        }

        async def fake_check_url(url):
            return {"valid": True, "status_code": 200, "error": None, "redirect_url": None}

        monkeypatch.setattr(engine, "_check_url", fake_check_url)
        result = await engine.process(job)
        assert result.success is True
        assert result.data["is_verified"] is True
        # apply_url and url are both checked
        types = {c["type"] for c in result.data["checks"]}
        assert "apply_url_valid" in types

    @pytest.mark.asyncio
    async def test_process_invalid_url_marks_check_failed(self, engine, monkeypatch):
        job = {
            "id": "j2",
            "url": "https://example.com/gone",
            "company_name": "Acme",
            "deadline": None,
        }

        async def fake_check_url(url):
            return {"valid": False, "status_code": 404, "error": "HTTP 404", "redirect_url": None}

        monkeypatch.setattr(engine, "_check_url", fake_check_url)
        result = await engine.process(job)
        url_check = next(c for c in result.data["checks"] if c["type"] == "url_valid")
        assert url_check["passed"] is False
        assert result.data["passed_checks"] < result.data["total_checks"]

    @pytest.mark.asyncio
    async def test_process_multiple_failures_not_verified(self, engine, monkeypatch):
        """With url + company checks failing the score drops below 0.6."""
        job = {
            "id": "j2b",
            "url": "https://example.com/gone",
            "company_name": "",
            "deadline": None,
        }

        async def fake_check_url(url):
            return {
                "valid": False,
                "status_code": 404,
                "error": "HTTP 404",
                "redirect_url": "https://example.com/redirect",
            }

        monkeypatch.setattr(engine, "_check_url", fake_check_url)
        result = await engine.process(job)
        # url(0) + redirect(0) + company(0) + deadline(0.2) + apply(0.2) = 0.4
        assert result.data["verification_score"] == 0.4
        assert result.data["is_verified"] is False
        assert result.data["status"] == "needs_review"

    @pytest.mark.asyncio
    async def test_process_bad_deadline_string_ignored(self, engine, monkeypatch):
        job = {
            "id": "j3",
            "url": "https://example.com/job",
            "company_name": "Acme",
            "deadline": "not-a-date",
        }

        async def fake_check_url(url):
            return {"valid": True, "status_code": 200, "error": None, "redirect_url": None}

        monkeypatch.setattr(engine, "_check_url", fake_check_url)
        result = await engine.process(job)
        deadline_check = next(c for c in result.data["checks"] if c["type"] == "deadline_active")
        assert deadline_check["passed"] is True

    @pytest.mark.asyncio
    async def test_process_redirect_loop_fails_check(self, engine, monkeypatch):
        job = {"id": "j4", "url": "https://example.com/a", "company_name": "Acme"}

        async def fake_check_url(url):
            return {
                "valid": True,
                "status_code": 200,
                "error": None,
                "redirect_url": "https://example.com/b",
            }

        monkeypatch.setattr(engine, "_check_url", fake_check_url)
        result = await engine.process(job)
        redirect_check = next(c for c in result.data["checks"] if c["type"] == "no_redirect_loops")
        assert redirect_check["passed"] is False

    @pytest.mark.asyncio
    async def test_process_same_apply_url_skips_second_check(self, engine, monkeypatch):
        job = {"id": "j5", "url": "https://example.com/job", "company_name": "Acme"}

        calls = []

        async def fake_check_url(url):
            calls.append(url)
            return {"valid": True, "status_code": 200, "error": None, "redirect_url": None}

        monkeypatch.setattr(engine, "_check_url", fake_check_url)
        await engine.process(job)
        # Only the job URL is checked when no separate apply_url is present.
        assert calls == ["https://example.com/job"]


class TestVerifyBatch:
    @pytest.mark.asyncio
    async def test_verify_batch_mixed_results(self, engine, monkeypatch):
        async def fake_process(job):
            if job["id"] == "good":
                return MagicMock(
                    success=True,
                    data={
                        "is_verified": True,
                        "checks": [],
                        "passed_checks": 5,
                        "total_checks": 5,
                        "verification_score": 1.0,
                        "status": "verified",
                    },
                )
            return MagicMock(
                success=True,
                data={
                    "is_verified": False,
                    "checks": [],
                    "passed_checks": 1,
                    "total_checks": 5,
                    "verification_score": 0.2,
                    "status": "needs_review",
                },
            )

        monkeypatch.setattr(engine, "process", fake_process)
        result = await engine.verify_batch([{"id": "good"}, {"id": "bad"}])
        assert result.data["verified_count"] == 1
        assert result.data["failed_count"] == 1
        assert result.data["verified"] == ["good"]
        assert result.data["failed"] == ["bad"]

    @pytest.mark.asyncio
    async def test_verify_batch_captures_errors(self, engine, monkeypatch):
        async def fake_process(job):
            if job["id"] == "broken":
                raise RuntimeError("boom")
            return MagicMock(
                success=True,
                data={
                    "is_verified": True,
                    "checks": [],
                    "passed_checks": 5,
                    "total_checks": 5,
                    "verification_score": 1.0,
                    "status": "verified",
                },
            )

        monkeypatch.setattr(engine, "process", fake_process)
        result = await engine.verify_batch([{"id": "good"}, {"id": "broken"}])
        assert result.data["verified_count"] == 1
        assert result.data["error_count"] == 1
        assert result.data["errors"] == ["boom"]

    @pytest.mark.asyncio
    async def test_verify_batch_empty(self, engine):
        result = await engine.verify_batch([])
        assert result.data["verified_count"] == 0
        assert result.data["failed_count"] == 0
