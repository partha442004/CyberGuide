"""
Tests for the Resumes API Router.

Covers upload, get, match, delete, and batch-match endpoints plus the
helper functions used for serialization and match scoring.
"""

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from cybershield.api.v1.resumes import (
    MAX_FILE_SIZE,
    _calculate_job_match,
    _extract_skill_names,
    _serialize_resume_response,
)
from cybershield.domain.models import Job, ResumeData
from cybershield.services.resume_service import ResumeParser

UPLOAD_URL = "/api/v1/resumes/upload"


# ==================== Helper Function Tests ====================


class TestExtractSkillNames:
    def test_strings_lowercased(self):
        skills = _extract_skill_names(["Python", "AWS", "SIEM"])
        assert skills == {"python", "aws", "siem"}

    def test_dict_skills_use_name_key(self):
        skills = _extract_skill_names([{"name": "Nmap"}, {"name": "Splunk"}])
        assert skills == {"nmap", "splunk"}

    def test_empty_and_invalid_entries_ignored(self):
        skills = _extract_skill_names(["", None, 42, {}, {"name": ""}, "Bash"])
        assert skills == {"bash"}

    def test_none_returns_empty_set(self):
        assert _extract_skill_names(None) == set()


class TestCalculateJobMatch:
    def _make_job(self, **overrides):
        job = SimpleNamespace(
            id="job-1",
            title="Security Analyst",
            company="Acme",
            required_skills=["python", "aws"],
            preferred_skills=["docker"],
        )
        for key, value in overrides.items():
            setattr(job, key, value)
        return job

    def test_full_match_scores_high(self):
        job = self._make_job()
        result = _calculate_job_match({"python", "aws", "docker"}, job)
        assert result.job_id == "job-1"
        assert result.job_title == "Security Analyst"
        assert result.company == "Acme"
        assert result.match_score == 100.0
        assert "python" in result.matched_skills
        assert result.missing_skills == []
        assert any("Strong match" in s for s in result.suggestions)

    def test_partial_match(self):
        job = self._make_job()
        result = _calculate_job_match({"python"}, job)
        assert result.match_score is not None
        assert 0 < result.match_score < 100
        assert "aws" in result.missing_skills
        # 1/2 required (0.7) + 0/1 preferred (0.3) -> 35.0
        assert result.match_score == 35.0
        assert any("Build projects" in s for s in result.suggestions)

    def test_no_skills_on_job_returns_none_score(self):
        job = self._make_job(required_skills=[], preferred_skills=[])
        result = _calculate_job_match({"python"}, job)
        assert result.match_score is None
        assert result.matched_skills == []
        assert result.missing_skills == []
        assert result.suggestions == []

    def test_low_match_suggests_projects(self):
        job = self._make_job(required_skills=["go", "rust", "kubernetes"])
        result = _calculate_job_match({"python"}, job)
        assert any("Build projects" in s for s in result.suggestions)
        assert any("Learn missing skills" in s for s in result.suggestions)


class TestSerializeResumeResponse:
    def test_serializes_all_fields(self):
        resume = SimpleNamespace(
            id="r-1",
            user_id="u-1",
            file_path="resume.pdf",
            file_hash="abc123",
            skills=[{"name": "python", "category": "scripting"}],
            education=[{"degree": "B.Tech"}],
            experience=[{"role": "intern"}],
            certifications=[{"name": "CEH"}],
            projects=[{"name": "Project"}],
            github_url="https://github.com/u",
            linkedin_url="https://linkedin.com/in/u",
            parsed_at=None,
        )
        data = _serialize_resume_response(resume)
        assert data.id == "r-1"
        assert data.file_name == "resume.pdf"
        assert data.file_hash == "abc123"
        assert data.skills == [{"name": "python", "category": "scripting"}]
        assert data.links == {
            "github": "https://github.com/u",
            "linkedin": "https://linkedin.com/in/u",
        }


# ==================== Upload Endpoint Tests ====================


class TestUploadResume:
    @pytest.mark.asyncio
    async def test_rejects_non_pdf(self, client: AsyncClient):
        response = await client.post(
            UPLOAD_URL,
            params={"user_id": "u-1"},
            files={"file": ("resume.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400
        assert "Only PDF" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_rejects_empty_file(self, client: AsyncClient):
        response = await client.post(
            UPLOAD_URL,
            params={"user_id": "u-1"},
            files={"file": ("resume.pdf", b"", "application/pdf")},
        )
        assert response.status_code == 400
        assert "Empty file" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_rejects_oversized_file(self, client: AsyncClient):
        big_content = b"x" * (MAX_FILE_SIZE + 1)
        response = await client.post(
            UPLOAD_URL,
            params={"user_id": "u-1"},
            files={"file": ("resume.pdf", big_content, "application/pdf")},
        )
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_creates_resume(self, client: AsyncClient, monkeypatch):
        async def fake_parse(self, content: bytes, filename: str):
            return {
                "file_hash": "hash-xyz",
                "skills": [{"name": "Python", "category": "scripting"}],
                "education": [{"degree": "B.Tech"}],
                "experience": [{"role": "intern"}],
                "projects": [],
                "certifications": [],
                "links": {"github": "https://github.com/u"},
            }

        monkeypatch.setattr(ResumeParser, "parse_upload", fake_parse)

        response = await client.post(
            UPLOAD_URL,
            params={"user_id": "u-1"},
            files={"file": ("resume.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["file_hash"] == "hash-xyz"
        assert data["user_id"] == "u-1"
        assert data["skills"][0]["name"] == "Python"
        assert data["links"]["github"] == "https://github.com/u"

    @pytest.mark.asyncio
    async def test_upload_updates_existing_resume(
        self, client: AsyncClient, db_session, monkeypatch
    ):
        # Pre-create a resume for the user
        existing = ResumeData(
            user_id="u-2",
            file_path="old.pdf",
            file_hash="old-hash",
            skills=[{"name": "Bash", "category": "scripting"}],
        )
        db_session.add(existing)
        await db_session.flush()

        async def fake_parse(self, content: bytes, filename: str):
            return {
                "file_hash": "new-hash",
                "skills": [{"name": "Python", "category": "scripting"}],
                "education": [],
                "experience": [],
                "projects": [],
                "certifications": [],
                "links": {},
            }

        monkeypatch.setattr(ResumeParser, "parse_upload", fake_parse)

        response = await client.post(
            UPLOAD_URL,
            params={"user_id": "u-2"},
            files={"file": ("resume.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["file_hash"] == "new-hash"
        assert data["file_name"] == "resume.pdf"
        assert data["skills"][0]["name"] == "Python"

    @pytest.mark.asyncio
    async def test_upload_parser_value_error_returns_400(self, client: AsyncClient, monkeypatch):
        async def fake_parse(self, content: bytes, filename: str):
            raise ValueError("Corrupt PDF")

        monkeypatch.setattr(ResumeParser, "parse_upload", fake_parse)

        response = await client.post(
            UPLOAD_URL,
            params={"user_id": "u-1"},
            files={"file": ("resume.pdf", b"bad", "application/pdf")},
        )
        assert response.status_code == 400
        assert "Corrupt PDF" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_parser_exception_returns_500(self, client: AsyncClient, monkeypatch):
        async def fake_parse(self, content: bytes, filename: str):
            raise RuntimeError("boom")

        monkeypatch.setattr(ResumeParser, "parse_upload", fake_parse)

        response = await client.post(
            UPLOAD_URL,
            params={"user_id": "u-1"},
            files={"file": ("resume.pdf", b"bad", "application/pdf")},
        )
        assert response.status_code == 500
        assert "Failed to parse resume" in response.json()["detail"]


# ==================== Get Endpoint Tests ====================


class TestGetResume:
    @pytest.mark.asyncio
    async def test_get_existing_resume(self, client: AsyncClient, db_session):
        resume = ResumeData(
            user_id="u-get",
            file_path="a.pdf",
            file_hash="h1",
            skills=[{"name": "Go", "category": "programming"}],
        )
        db_session.add(resume)
        await db_session.flush()

        response = await client.get("/api/v1/resumes/u-get")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "u-get"
        assert data["skills"] == [{"name": "Go", "category": "programming"}]

    @pytest.mark.asyncio
    async def test_get_missing_resume_returns_404(self, client: AsyncClient):
        response = await client.get("/api/v1/resumes/no-such-user")
        assert response.status_code == 404


# ==================== Match Endpoint Tests ====================


class TestMatchResumeToJob:
    @pytest.mark.asyncio
    async def test_match_success(self, client: AsyncClient, db_session):
        resume = ResumeData(user_id="u-match", file_path="a.pdf", file_hash="h1", skills=["python"])
        job = Job(
            title="Backend Dev",
            company="Acme",
            url="https://acme.com/job/1",
            source="test",
            job_type="full_time",
            required_skills=["python", "go"],
            preferred_skills=[],
        )
        db_session.add_all([resume, job])
        await db_session.flush()

        response = await client.post(
            f"/api/v1/resumes/match/{job.id}", params={"user_id": "u-match"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job.id
        assert data["job_title"] == "Backend Dev"
        assert "python" in data["matched_skills"]
        assert "go" in data["missing_skills"]

    @pytest.mark.asyncio
    async def test_match_no_resume_returns_404(self, client: AsyncClient, db_session):
        job = Job(
            title="Dev",
            company="Acme",
            url="https://acme.com/job/2",
            source="test",
            job_type="full_time",
        )
        db_session.add(job)
        await db_session.flush()

        response = await client.post(f"/api/v1/resumes/match/{job.id}", params={"user_id": "ghost"})
        assert response.status_code == 404
        assert "Upload a resume" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_match_no_job_returns_404(self, client: AsyncClient, db_session):
        resume = ResumeData(
            user_id="u-match2", file_path="a.pdf", file_hash="h2", skills=["python"]
        )
        db_session.add(resume)
        await db_session.flush()

        response = await client.post(
            "/api/v1/resumes/match/does-not-exist", params={"user_id": "u-match2"}
        )
        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]


# ==================== Delete Endpoint Tests ====================


class TestDeleteResume:
    @pytest.mark.asyncio
    async def test_delete_existing(self, client: AsyncClient, db_session):
        resume = ResumeData(user_id="u-del", file_path="a.pdf", file_hash="h3")
        db_session.add(resume)
        await db_session.flush()

        response = await client.delete("/api/v1/resumes/u-del")
        assert response.status_code == 200
        assert response.json()["message"] == "Resume deleted successfully"

    @pytest.mark.asyncio
    async def test_delete_missing_returns_404(self, client: AsyncClient):
        response = await client.delete("/api/v1/resumes/ghost")
        assert response.status_code == 404


# ==================== Batch Match Endpoint Tests ====================


class TestMatchResumeBatch:
    @pytest.mark.asyncio
    async def test_batch_match_success(self, client: AsyncClient, db_session):
        resume = ResumeData(user_id="u-batch", file_path="a.pdf", file_hash="h4", skills=["python"])
        job_a = Job(
            title="Python Dev",
            company="Acme",
            url="https://acme.com/job/a",
            source="test",
            job_type="full_time",
            required_skills=["python"],
            preferred_skills=[],
        )
        job_b = Job(
            title="Go Dev",
            company="Beta",
            url="https://beta.com/job/b",
            source="test",
            job_type="full_time",
            required_skills=["go"],
            preferred_skills=[],
        )
        db_session.add_all([resume, job_a, job_b])
        await db_session.flush()

        response = await client.post(
            "/api/v1/resumes/match-batch",
            params={"user_id": "u-batch", "job_ids": [job_a.id, job_b.id]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_jobs_matched"] == 2
        # Sorted by score descending -> python job (higher score) first
        assert data["matches"][0]["job_id"] == job_a.id
        assert data["top_match"]["job_id"] == job_a.id
        assert data["average_score"] is not None

    @pytest.mark.asyncio
    async def test_batch_match_no_resume_returns_404(self, client: AsyncClient, db_session):
        job = Job(
            title="Dev",
            company="Acme",
            url="https://acme.com/job/c",
            source="test",
            job_type="full_time",
        )
        db_session.add(job)
        await db_session.flush()

        response = await client.post(
            "/api/v1/resumes/match-batch",
            params={"user_id": "ghost", "job_ids": [job.id]},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_batch_match_no_jobs_returns_404(self, client: AsyncClient, db_session):
        resume = ResumeData(
            user_id="u-batch2", file_path="a.pdf", file_hash="h5", skills=["python"]
        )
        db_session.add(resume)
        await db_session.flush()

        response = await client.post(
            "/api/v1/resumes/match-batch",
            params={"user_id": "u-batch2", "job_ids": ["nope-1", "nope-2"]},
        )
        assert response.status_code == 404
        assert "No jobs found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_batch_match_skips_missing_jobs(self, client: AsyncClient, db_session):
        resume = ResumeData(
            user_id="u-batch3", file_path="a.pdf", file_hash="h6", skills=["python"]
        )
        job = Job(
            title="Py Dev",
            company="Acme",
            url="https://acme.com/job/d",
            source="test",
            job_type="full_time",
            required_skills=["python"],
            preferred_skills=[],
        )
        db_session.add_all([resume, job])
        await db_session.flush()

        response = await client.post(
            "/api/v1/resumes/match-batch",
            params={"user_id": "u-batch3", "job_ids": [job.id, "missing-1"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_jobs_matched"] == 1
        assert data["matches"][0]["job_id"] == job.id
