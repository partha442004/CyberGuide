"""
Extended unit tests for the resumes API match helpers.

Covers the missing 'Good match' (50-79) suggestion branch of
_calculate_job_match plus additional _extract_skill_names edge cases
that the existing suite does not exercise.
"""

from types import SimpleNamespace

from cybershield.api.v1.resumes import _calculate_job_match, _extract_skill_names


def _make_job(**overrides):
    job = SimpleNamespace(
        id="job-x",
        title="Security Analyst",
        company="Acme",
        required_skills=["python", "aws"],
        preferred_skills=["docker"],
    )
    for key, value in overrides.items():
        setattr(job, key, value)
    return job


class TestCalculateJobMatchBranches:
    def test_good_match_suggests_applying(self):
        """Score in the 50-79 band yields the 'Good match' suggestion."""
        # 2/2 required (1.0*0.7) + 0/1 preferred (0*0.3) = 70.0
        job = _make_job()
        result = _calculate_job_match({"python", "aws"}, job)
        assert result.match_score == 70.0
        assert any("Good match" in s for s in result.suggestions)

    def test_missing_skills_limited_to_five(self):
        """Only the first five missing skills appear in the suggestion."""
        job = _make_job(
            required_skills=["a", "b", "c", "d", "e", "f", "g"],
            preferred_skills=[],
        )
        result = _calculate_job_match(set(), job)
        learn = [s for s in result.suggestions if "Learn missing skills" in s]
        assert learn
        assert len(result.missing_skills) == 7
        assert len(learn[0].split(": ")[1].split(", ")) == 5

    def test_preferred_only_match(self):
        """Matching only preferred skills still counts toward the score."""
        job = _make_job()
        result = _calculate_job_match({"docker"}, job)
        # 0/2 required (0) + 1/1 preferred (1.0*0.3) = 30.0
        assert result.match_score == 30.0

    def test_required_only_scores_seventy(self):
        job = _make_job(required_skills=["python"], preferred_skills=[])
        result = _calculate_job_match({"python"}, job)
        assert result.match_score == 70.0
        assert result.missing_skills == []


class TestExtractSkillNamesEdgeCases:
    def test_dict_without_name_key_ignored(self):
        assert _extract_skill_names([{"other": "x"}]) == set()

    def test_dict_with_empty_name_ignored(self):
        assert _extract_skill_names([{"name": ""}]) == set()

    def test_mixed_str_and_dict(self):
        result = _extract_skill_names(["Python", {"name": "AWS"}])
        assert result == {"python", "aws"}

    def test_none_entries_ignored(self):
        assert _extract_skill_names([None, "Go", 42]) == {"go"}

    def test_case_insensitive_dedup(self):
        assert _extract_skill_names(["Python", "PYTHON", "pYtHoN"]) == {"python"}
