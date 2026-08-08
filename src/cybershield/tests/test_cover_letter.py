"""Tests for the cover-letter generator (service + API endpoint)."""

import pytest

from cybershield.services.cover_letter import _as_skill_names, _top_skills, build_cover_letter


class TestAsSkillNames:
    def test_strings_and_dicts_normalized(self):
        assert _as_skill_names(["python", {"name": "SQL"}, 3, None, ""]) == [
            "python",
            "SQL",
        ]

    def test_empty_returns_empty(self):
        assert _as_skill_names(None) == []
        assert _as_skill_names([]) == []


class TestTopSkills:
    def test_matched_skills_come_first(self):
        skills = ["python", "sql", "linux", "metasploit", "bash"]
        matched = ["metasploit", "bash"]
        top = _top_skills(skills, matched, limit=4)
        assert top[0] == "metasploit"
        assert top[1] == "bash"
        assert len(top) == 4

    def test_no_duplicates(self):
        top = _top_skills(["python", "python", "SQL"], None, limit=10)
        assert top == ["python", "SQL"]

    def test_limit_respected(self):
        top = _top_skills(["a", "b", "c", "d", "e"], None, limit=2)
        assert len(top) == 2


class TestBuildCoverLetter:
    def test_letter_mentions_role_company_and_skills(self):
        letter = build_cover_letter(
            ["python", "sql", "metasploit"],
            "Penetration Tester",
            "Zscaler",
            matched_skills=["metasploit", "python"],
        )
        assert "Penetration Tester" in letter
        assert "Zscaler" in letter
        assert "metasploit" in letter
        assert "python" in letter
        assert letter.startswith("Dear Zscaler Hiring Team,")
        assert "Best regards," in letter
        # Three paragraphs + salutation + signoff
        assert letter.count("\n\n") >= 3

    def test_no_matched_skills_uses_general_line(self):
        letter = build_cover_letter(["python"], "Role", "Acme", matched_skills=None)
        assert "hands-on experience with python" in letter
        assert "maps directly" not in letter

    def test_missing_title_and_company_fall_back(self):
        letter = build_cover_letter([], "", "", None)
        assert "this role" in letter
        assert "your company" in letter

    def test_resume_name_in_signoff(self):
        letter = build_cover_letter(["x"], "R", "C", None, resume_name="Parthasarathi B")
        assert letter.rstrip().endswith("Parthasarathi B")


class TestCoverLetterEndpoint:
    @pytest.mark.asyncio
    async def test_cover_letter_requires_resume(self, client: pytest.fixture):
        """No resume for the user -> 404 with a helpful message."""
        response = await client.post(
            "/api/v1/resumes/cover-letter",
            params={"user_id": "no-resume-user", "job_id": "job-1"},
        )
        assert response.status_code == 404
        assert "Upload a resume" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_cover_letter_generates_for_resume_and_job(
        self, client: pytest.fixture, db_session: pytest.fixture
    ):
        """With a resume + job in the DB, returns a tailored letter."""
        from cybershield.domain.models import Job, ResumeData

        db_session.add(
            ResumeData(
                user_id="letter-user",
                file_path="r.pdf",
                file_hash="h1",
                skills=[
                    {"name": "Python", "category": "scripting"},
                    {"name": "Metasploit", "category": "security"},
                ],
            )
        )
        db_session.add(
            Job(
                id="letter-job",
                title="Penetration Tester",
                company="Zscaler",
                url="https://example.com/job/letter",
                source="test",
                job_type="full_time",
                salary_currency="INR",
                required_skills=["metasploit", "python"],
                preferred_skills=[],
                tags=["cybersecurity", "vapt"],
            )
        )
        await db_session.flush()

        response = await client.post(
            "/api/v1/resumes/cover-letter",
            params={"user_id": "letter-user", "job_id": "letter-job"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["job_title"] == "Penetration Tester"
        assert data["company"] == "Zscaler"
        assert "Penetration Tester" in data["cover_letter"]
        assert "Zscaler" in data["cover_letter"]
        assert "metasploit" in data["cover_letter"].lower()
        assert data["match_score"] is not None

    @pytest.mark.asyncio
    async def test_cover_letter_missing_job_404(
        self, client: pytest.fixture, db_session: pytest.fixture
    ):
        """Resume exists but job doesn't -> 404 'Job not found'."""
        from cybershield.domain.models import ResumeData

        db_session.add(
            ResumeData(
                user_id="letter-user2",
                file_path="r.pdf",
                file_hash="h2",
                skills=[{"name": "Python", "category": "scripting"}],
            )
        )
        await db_session.flush()

        response = await client.post(
            "/api/v1/resumes/cover-letter",
            params={"user_id": "letter-user2", "job_id": "nope"},
        )
        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]
