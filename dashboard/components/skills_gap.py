"""
Skills-gap aggregation for the My Matches page.

Turns the per-job match breakdowns (matched / missing skills) the resume
API already computes into one ranked "what to learn next" view: the
skills your top matches expect but your resume lacks, sorted by how many
of those matches want them.

Deliberately free of streamlit imports so it can be unit-tested without
faking the Streamlit runtime.
"""

from __future__ import annotations

from typing import Any

# Cap each list so a long skill set never floods the panel.
_MAX_SKILLS = 12


def skill_learn_url(skill: str) -> str:
    """A free-course search link for any skill (YouTube fallback).

    Kept generic (no curated map here) so the dashboard and the digest
    never drift on hand-maintained URLs — the digest carries the curated
    resources, the dashboard always resolves to a YouTube course search.
    """
    from urllib.parse import quote

    query = f"{str(skill or '').strip()} course"
    return "https://www.youtube.com/results?search_query=" + quote(query)


def aggregate_skills_gap(
    matches: list[tuple[dict, float, dict]],
    min_score: float = 30.0,
) -> dict[str, Any]:
    """Rank missing / matched skills across a user's top job matches.

    Args:
        matches: ``[(job, score, match)]`` tuples exactly as returned by
            the dashboard's ``_my_top_matches`` — ``match`` carries the
            breakdown the resume API computed (``matched_skills`` /
            ``missing_skills``).
        min_score: only matches at or above this score are considered, so
            low-value postings can't dictate the learning list.

    Returns:
        ``{"missing": [...], "matched": [...], "considered": int}`` where
        each skill entry is ``{"skill": str, "count": int}`` — counts are
        of matches (not mentions), case-insensitive, display casing kept
        from the first spelling seen. Lists are sorted by count desc then
        alphabetically and capped at ``_MAX_SKILLS``. ``considered`` is
        the number of matches that made the cut.
    """
    missing: dict[str, dict[str, Any]] = {}
    matched: dict[str, dict[str, Any]] = {}
    considered = 0

    for _job, score, match in matches:
        if not isinstance(match, dict):
            continue
        try:
            score = float(score)
        except (TypeError, ValueError):
            continue
        if score < min_score:
            continue
        considered += 1
        for bucket, source in (
            (missing, match.get("missing_skills") or []),
            (matched, match.get("matched_skills") or []),
        ):
            for skill in source:
                name = str(skill or "").strip()
                if not name:
                    continue
                key = name.lower()
                entry = bucket.get(key)
                if entry is None:
                    entry = {"skill": name, "count": 0}
                    bucket[key] = entry
                entry["count"] += 1

    def ranked(items: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        out = sorted(
            items.values(),
            key=lambda e: (-e["count"], e["skill"].lower()),
        )
        return out[:_MAX_SKILLS]

    return {
        "missing": ranked(missing),
        "matched": ranked(matched),
        "considered": considered,
    }
