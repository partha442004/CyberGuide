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


class TestDomainTransitionMatching:
    """Fair scoring for candidates switching domains.

    A resume should not flatline at 0.0 just because it words skills
    differently (synonyms) or because it has transferable same-family
    skills (categories) — e.g. a Data Analyst resume vs a Software
    Engineer job.
    """

    def test_data_analyst_vs_software_job_gets_nonzero_score(self):
        """Resume with python/sql partially covers a SWE job asking for
        go/kubernetes via the shared ``scripting``/``cicd`` families."""
        job = _make_job(required_skills=["go", "kubernetes", "aws"], preferred_skills=[])
        result = _calculate_job_match({"python", "sql"}, job)
        assert result.match_score is not None
        assert result.match_score > 0
        # ``go`` is scripting — same family as ``python``.
        assert "go" in result.related_skills
        assert "go" not in result.missing_skills
        # ``kubernetes``/``aws`` are out-of-family for a data analyst.
        assert "kubernetes" in result.missing_skills
        assert any("Transferable skills" in s for s in result.suggestions)

    def test_synonym_skills_count_as_partial_match(self):
        """k8s vs kubernetes / golang vs go are the same skill."""
        job = _make_job(required_skills=["k8s"], preferred_skills=["golang"])
        result = _calculate_job_match({"kubernetes", "go"}, job)
        assert result.match_score is not None
        assert result.match_score > 0
        assert "k8s" in result.matched_skills
        assert "golang" in result.matched_skills
        assert result.missing_skills == []

    def test_category_match_weights_less_than_exact(self):
        """Partial credit must not beat a real exact match."""
        exact_job = _make_job(required_skills=["python"], preferred_skills=[])
        exact = _calculate_job_match({"python"}, exact_job)
        category_job = _make_job(required_skills=["go"], preferred_skills=[])
        category = _calculate_job_match({"python"}, category_job)
        assert exact.match_score is not None
        assert category.match_score is not None
        assert exact.match_score > category.match_score

    def test_related_skills_exposed_in_response(self):
        job = _make_job(required_skills=["go"], preferred_skills=[])
        result = _calculate_job_match({"python"}, job)
        assert result.related_skills == ["go"]
        assert result.matched_skills == []


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
