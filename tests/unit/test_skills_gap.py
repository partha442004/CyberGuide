"""
Tests for the dashboard skills-gap aggregation.

``dashboard.components.skills_gap`` is streamlit-free by design. The module
is loaded directly from its file path (not through the ``dashboard``
package) because ``dashboard/components/__init__.py`` eagerly imports
streamlit, which would collide with the fake-streamlit setup in
``test_dashboard_components.py`` depending on collection order.
"""

import importlib.util
import pathlib

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "dashboard" / "components" / "skills_gap.py"


def _load_skills_gap():
    spec = importlib.util.spec_from_file_location(
        "_skills_gap_under_test", _MODULE_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


skills_gap = _load_skills_gap()
aggregate_skills_gap = skills_gap.aggregate_skills_gap
_MAX_SKILLS = skills_gap._MAX_SKILLS


def _match(missing=None, matched=None, score: float = 80.0) -> tuple:
    """One ``(job, score, match)`` tuple shaped like ``_my_top_matches``."""
    return (
        {"id": "j1", "title": "SOC Analyst"},
        score,
        {
            "matched_skills": matched or [],
            "missing_skills": missing or [],
        },
    )


def test_empty_matches_give_empty_gap():
    gap = aggregate_skills_gap([])
    assert gap["missing"] == []
    assert gap["matched"] == []
    assert gap["considered"] == 0


def test_ranks_missing_skills_by_how_many_matches_want_them():
    matches = [
        _match(missing=["Splunk", "SIEM", "Python"]),
        _match(missing=["Splunk", "SIEM"]),
        _match(missing=["Splunk"]),
        _match(missing=["Linux", "AWS"]),
    ]
    gap = aggregate_skills_gap(matches)
    names = [m["skill"] for m in gap["missing"]]
    assert names[:3] == ["Splunk", "SIEM", "AWS"]  # 3, then 2, then 1 (alpha)
    counts = {m["skill"]: m["count"] for m in gap["missing"]}
    assert counts["Splunk"] == 3
    assert counts["SIEM"] == 2
    assert gap["considered"] == 4


def test_matched_skills_are_counted_separately():
    gap = aggregate_skills_gap(
        [
            _match(matched=["Python", "Linux"], missing=["Splunk"]),
            _match(matched=["Python"], missing=["SIEM"]),
        ]
    )
    matched = {m["skill"]: m["count"] for m in gap["matched"]}
    assert matched["Python"] == 2
    assert matched["Linux"] == 1
    # Both missing skills appear once; ties break alphabetically.
    assert [m["skill"] for m in gap["missing"]] == ["SIEM", "Splunk"]


def test_low_scoring_matches_are_excluded():
    gap = aggregate_skills_gap(
        [
            _match(missing=["Splunk"], score=90.0),
            _match(missing=["Splunk", "Elastic"], score=15.0),
        ],
        min_score=30.0,
    )
    # The 15% match is ignored, so Elastic never surfaces.
    assert gap["considered"] == 1
    assert [m["skill"] for m in gap["missing"]] == ["Splunk"]


def test_case_insensitive_dedupe_keeps_first_spelling():
    gap = aggregate_skills_gap(
        [
            _match(missing=["Splunk"]),
            _match(missing=["splunk", "SIEM"]),
        ]
    )
    assert [m["skill"] for m in gap["missing"]] == ["Splunk", "SIEM"]
    assert gap["missing"][0]["count"] == 2


def test_lists_are_capped():
    many = [f"Skill {i}" for i in range(20)]
    gap = aggregate_skills_gap([_match(missing=many, matched=many)])
    assert len(gap["missing"]) == _MAX_SKILLS
    assert len(gap["matched"]) == _MAX_SKILLS


def test_junk_entries_are_dropped():
    gap = aggregate_skills_gap([_match(missing=["", None, "   ", "Splunk"])])
    assert [m["skill"] for m in gap["missing"]] == ["Splunk"]


def test_non_numeric_score_is_skipped():
    matches = [({"id": "j1"}, "n/a", {"missing_skills": ["Splunk"]})]
    gap = aggregate_skills_gap(matches)  # type: ignore[arg-type]
    assert gap["considered"] == 0
    assert gap["missing"] == []


def test_non_dict_match_is_skipped():
    matches = [({}, 80.0, 55)]  # legacy float match must never crash
    gap = aggregate_skills_gap(matches)  # type: ignore[list-item]
    assert gap == {"missing": [], "matched": [], "considered": 0}


def test_skill_learn_url_generates_youtube_search():
    from urllib.parse import parse_qs, urlparse

    url = skills_gap.skill_learn_url("Splunk")
    parsed = urlparse(url)
    assert parsed.netloc == "www.youtube.com"
    query = parse_qs(parsed.query)
    assert query.get("search_query") == ["Splunk course"]
