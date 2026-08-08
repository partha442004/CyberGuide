"""Tests for the interview-prep generator (service + API endpoint)."""

import pytest
from httpx import AsyncClient

from cybershield.services.interview_prep import (
    _known_template,
    _missing_template,
    _skill_category,
    build_interview_prep,
)


class TestSkillCategory:
    def test_security_terms(self):
        assert _skill_category("burp suite") == "web_security"
        assert _skill_category("nmap") == "network_security"
        assert _skill_category("aws") == "cloud_security"
        assert _skill_category("python") == "scripting"
        assert _skill_category("sql") == "data_analysis"

    def test_unknown_falls_back_to_general(self):
        assert _skill_category("something-unheard-of") == "general"

    def test_templates_interpolate_skill(self):
        assert "{skill}" in _known_template("burp suite")
        assert "{skill}" in _missing_template("aws")
        assert "burp suite" in _known_template("burp suite").format(skill="burp suite")


class TestBuildInterviewPrep:
    def test_question_groups_present(self):
        prep = build_interview_prep(
            "Penetration Tester",
            "Zscaler",
            matched_skills=["burp suite", "nmap"],
            missing_skills=["aws", "kubernetes"],
        )
        categories = {q["category"] for q in prep["questions"]}
        assert {"role", "technical", "behavioral", "gap", "company"} <= categories

    def test_technical_questions_anchor_to_matched_skills(self):
        prep = build_interview_prep(
            "Role",
            "Acme",
            matched_skills=["nmap"],
            missing_skills=[],
        )
        tech = [q["question"] for q in prep["questions"] if q["category"] == "technical"]
        assert tech
        assert "nmap" in tech[0]

    def test_gap_questions_only_for_missing_skills(self):
        prep = build_interview_prep(
            "Role",
            "Acme",
            matched_skills=["python"],
            missing_skills=["aws", "kubernetes"],
        )
        gaps = [q["question"] for q in prep["questions"] if q["category"] == "gap"]
        # Max 3 gap prompts, all referencing a missing skill.
        assert 0 < len(gaps) <= 3
        assert any("aws" in g or "kubernetes" in g for g in gaps)

    def test_no_missing_skills_no_gap_questions(self):
        prep = build_interview_prep("Role", "Acme", matched_skills=[], missing_skills=[])
        gaps = [q["question"] for q in prep["questions"] if q["category"] == "gap"]
        assert gaps == []

    def test_no_matched_skills_still_has_role_behavioral_company(self):
        prep = build_interview_prep("Role", "Acme", matched_skills=[], missing_skills=[])
        categories = {q["category"] for q in prep["questions"]}
        assert {"role", "behavioral", "company"} <= categories

    def test_job_title_and_company_embedded(self):
        prep = build_interview_prep(
            "Cloud Security Engineer",
            "Cloudflare",
            matched_skills=[],
            missing_skills=[],
        )
        joined = " ".join(q["question"] for q in prep["questions"])
        assert "Cloud Security Engineer" in joined
        assert "Cloudflare" in joined

    def test_tips_are_actionable(self):
        prep = build_interview_prep(
            "Role",
            "Acme",
            matched_skills=["python"],
            missing_skills=["aws"],
        )
        assert any("python" in t for t in prep["tips"])
        assert any("aws" in t for t in prep["tips"])
        assert any("STAR" in t for t in prep["tips"])


class TestInterviewPrepEndpoint:
    @pytest.mark.asyncio
    async def test_interview_prep_requires_resume(self, client: AsyncClient):
        """No resume for the user -> 404 with a helpful message."""
        response = await client.post(
            "/api/v1/resumes/interview-prep",
            params={"user_id": "no-resume-user", "job_id": "job-1"},
        )
        assert response.status_code == 404
        assert "Upload a resume" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_interview_prep_generates_for_resume_and_job(
        self,
        client: AsyncClient,
        db_session,
    ):
        """With a resume + job in the DB, returns a grouped question list."""
        from cybershield.domain.models import Job, ResumeData

        db_session.add(
            ResumeData(
                user_id="prep-user",
                file_path="r.pdf",
                file_hash="h1",
                skills=[
                    {"name": "Burp Suite", "category": "web_security"},
                    {"name": "Nmap", "category": "network_security"},
                ],
            )
        )
        db_session.add(
            Job(
                id="prep-job",
                title="Penetration Tester",
                company="Zscaler",
                url="https://example.com/job/prep",
                source="test",
                job_type="full_time",
                salary_currency="INR",
                required_skills=["burp suite", "nmap"],
                preferred_skills=["aws"],
                tags=["cybersecurity", "vapt"],
            )
        )
        await db_session.flush()

        response = await client.post(
            "/api/v1/resumes/interview-prep",
            params={"user_id": "prep-user", "job_id": "prep-job"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["job_title"] == "Penetration Tester"
        assert data["company"] == "Zscaler"
        assert data["questions"]
        assert data["match_score"] is not None
        categories = {q["category"] for q in data["questions"]}
        assert "technical" in categories
        assert "role" in categories

    @pytest.mark.asyncio
    async def test_interview_prep_missing_job_404(self, client: AsyncClient, db_session):
        """Resume exists but job doesn't -> 404 'Job not found'."""
        from cybershield.domain.models import ResumeData

        db_session.add(
            ResumeData(
                user_id="prep-user2",
                file_path="r.pdf",
                file_hash="h2",
                skills=[{"name": "Python", "category": "scripting"}],
            )
        )
        await db_session.flush()

        response = await client.post(
            "/api/v1/resumes/interview-prep",
            params={"user_id": "prep-user2", "job_id": "nope"},
        )
        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]
