"""
Tests for the ATS compatibility scorer (ResumeScorer).

Covers the weighted criteria documented in docs/cscip/14-resume-engine.md:
contact info, section presence, keyword match, structure and length.
"""

from cybershield.services.resume_service import ResumeScorer


class TestResumeScorer:
    def _scorer(self) -> ResumeScorer:
        return ResumeScorer()

    def _full_resume(self, **overrides) -> dict:
        resume = {
            "skills": [
                {"name": "python", "category": "scripting"},
                {"name": "aws", "category": "cloud_security"},
                {"name": "nmap", "category": "security_tools"},
                {"name": "splunk", "category": "siem"},
                {"name": "burp suite", "category": "penetration_testing"},
            ],
            "education": [{"degree": "B.Tech", "institution": "Keystone"}],
            "experience": [{"role": "intern", "context": "SOC Analyst intern"}],
            "certifications": [{"name": "CEH"}],
            "links": {
                "email": "a@b.c",
                "github": "https://github.com/u",
                "linkedin": "https://linkedin.com/in/u",
            },
        }
        resume.update(overrides)
        return resume

    def test_full_resume_scores_high(self):
        result = self._scorer().calculate_ats_score(
            self._full_resume(),
            job_keywords=["python", "aws", "splunk"],
        )
        assert result["ats_score"] >= 70
        assert result["criteria_scores"]["contact_info"] == 100
        assert result["criteria_scores"]["skills_section"] == 100
        assert result["criteria_scores"]["experience_section"] == 100
        assert result["criteria_scores"]["education_section"] == 100
        # All 3 job keywords are present in the resume skills.
        assert result["criteria_scores"]["keywords_match"] == 100

    def test_keyword_miss_lowers_keyword_score_and_adds_feedback(self):
        result = self._scorer().calculate_ats_score(
            self._full_resume(),
            job_keywords=["python", "kubernetes", "go", "rust"],
        )
        assert result["criteria_scores"]["keywords_match"] == 25  # 1 of 4
        assert result["ats_score"] < 90
        assert any("job keywords" in f for f in result["feedback"])

    def test_empty_resume_scores_low_with_feedback(self):
        """An empty resume scores near zero — only the structure weights
        (formatting/length) contribute, matching the documented algorithm."""
        result = self._scorer().calculate_ats_score({}, job_keywords=["python"])
        assert result["ats_score"] < 15
        assert result["criteria_scores"]["contact_info"] == 0
        assert result["criteria_scores"]["skills_section"] == 0
        assert result["criteria_scores"]["experience_section"] == 0
        assert len(result["feedback"]) >= 3

    def test_no_job_keywords_is_neutral(self):
        result = self._scorer().calculate_ats_score(self._full_resume())
        assert result["criteria_scores"]["keywords_match"] == 50
        assert result["ats_score"] > 0

    def test_no_contact_info_scores_zero_and_feedback(self):
        resume = self._full_resume(links={})
        result = self._scorer().calculate_ats_score(resume, job_keywords=["python"])
        assert result["criteria_scores"]["contact_info"] == 0
        assert any("contact" in f.lower() for f in result["feedback"])

    def test_few_skills_lowers_length_and_adds_feedback(self):
        resume = self._full_resume(skills=[{"name": "python", "category": "scripting"}])
        result = self._scorer().calculate_ats_score(resume)
        assert result["criteria_scores"]["length"] <= 70
        assert any("breadth" in f for f in result["feedback"])

    def test_breakdown_matches_criteria(self):
        result = self._scorer().calculate_ats_score(self._full_resume())
        breakdown = result["breakdown"]
        assert len(breakdown) == len(ResumeScorer.CRITERIA)
        names = {b["criterion"] for b in breakdown}
        assert names == set(ResumeScorer.CRITERIA.keys())
        # Weights sum to 100.
        assert sum(b["weight"] for b in breakdown) == 100
