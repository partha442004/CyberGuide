"""
Unit tests for the AI job-hunting tools (cover letter / questions / match).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeJob:
    """Minimal Job stand-in for the apply-kit endpoint."""

    id = "job-1"
    title = "SOC Analyst L2"
    company = "Zscaler"
    description = (
        "Monitor SIEM alerts and triage incidents. Requires Splunk, "
        "network security and incident response experience."
    )
    required_skills = ["splunk", "siem", "incident response"]
    tags = ["soc", "siem"]


class _FakeSession:
    """AsyncSession stand-in (the endpoint only passes it to JobService)."""

    async def execute(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_apply_kit_returns_templates_without_ai():
    from interntrack.api.v1.ai_tools import apply_kit

    service = MagicMock()
    service.get_job = AsyncMock(return_value=_FakeJob())

    with (
        patch("interntrack.api.v1.ai_tools.JobService", lambda _db: service),
        patch(
            "interntrack.scheduler.jobs._latest_resume_skill_names",
            AsyncMock(return_value={"splunk", "python", "linux"}),
        ),
        patch(
            "interntrack.scheduler.jobs._job_match_score",
            lambda _skills, _job: 67.0,
        ),
    ):
        result = await apply_kit("job-1", _FakeSession())

    assert result["title"] == "SOC Analyst L2"
    assert result["company"] == "Zscaler"
    assert result["match_score"] == 67.0
    assert "SOC Analyst" in result["cover_letter"]
    assert "Zscaler" in result["cover_letter"]
    assert len(result["interview_questions"]) == 5
    assert result["generated_by"] == "template"
    assert "splunk" in result["matched_skills"]
    assert any("SIEM" in why or "splunk" in why.lower() for why in result["why_match"])


@pytest.mark.asyncio
async def test_apply_kit_404_when_job_missing():
    from fastapi import HTTPException

    from interntrack.api.v1.ai_tools import apply_kit

    service = MagicMock()
    service.get_job = AsyncMock(return_value=None)

    with patch("interntrack.api.v1.ai_tools.JobService", lambda _db: service):
        with pytest.raises(HTTPException) as exc:
            await apply_kit("missing", _FakeSession())
        assert exc.value.status_code == 404
