"""Fix remaining mypy errors across interntrack files."""
import io
import os

ROOT = "C:/Users/KIRA/CyberGuide"


def patch(path, replacements, must_apply=True):
    full = os.path.join(ROOT, path)
    with io.open(full, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    for old, new in replacements:
        if old not in text:
            if must_apply:
                print(f"WARN not found in {path}: {old[:70]!r}")
            continue
        text = text.replace(old, new, 1)
    with io.open(full, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"patched {path}")


# 1. helpers.py: annotate to_naive_utc return type (fixes no-any-return downstream)
patch(
    "src/interntrack/utils/helpers.py",
    [
        (
            "def to_naive_utc(dt):\n"
            '    """Convert an aware datetime to naive UTC, or return naive as-is."""\n'
            "    if dt is None:\n"
            "        return None\n"
            "    if dt.tzinfo is not None:\n"
            "        return dt.astimezone(UTC).replace(tzinfo=None)\n"
            "    return dt\n",
            "def to_naive_utc(dt) -> datetime | None:\n"
            '    """Convert an aware datetime to naive UTC, or return naive as-is."""\n'
            "    if dt is None:\n"
            "        return None\n"
            "    if dt.tzinfo is not None:\n"
            "        return dt.astimezone(UTC).replace(tzinfo=None)\n"
            "    return dt\n",
        ),
    ],
)

# 2. application_repository.py: remove unused type: ignore
patch(
    "src/interntrack/repositories/application_repository.py",
    [
        (
            "        application.status = new_status  # type: ignore[assignment]\n",
            "        application.status = new_status\n",
        ),
    ],
)

# 3. job_repository.py: bool -> Column[bool] assignment
patch(
    "src/interntrack/repositories/job_repository.py",
    [
        (
            "            # Mark original as inactive\n            job.is_active = False\n",
            "            # Mark original as inactive\n            job.is_active = False  # type: ignore[assignment]\n",
        ),
    ],
)

# 4. job_recommender.py: sort key typing
patch(
    "src/interntrack/services/job_recommender.py",
    [
        (
            "        recommendations.sort(key=lambda x: x[\"match_score\"], reverse=True)\n",
            "        recommendations.sort(\n"
            '            key=lambda x: float(x["match_score"]), reverse=True\n'
            "        )\n",
        ),
    ],
)

# 5. report_service.py: str() coercion on job dict + no-any-return fixes
patch(
    "src/interntrack/services/report_service.py",
    [
        (
            "    dt = to_naive_utc(dt)\n"
            "    if dt is None:\n"
            "        return \"\"\n"
            "    return dt.strftime(\"%Y-%m-%d %H:%M:%S\")\n",
            "    dt = to_naive_utc(dt)\n"
            "    if dt is None:\n"
            "        return \"\"\n"
            "    return dt.strftime(\"%Y-%m-%d %H:%M:%S\")\n",
        ),
        (
            '                if location_lower in (job.get("location") or "").lower()\n',
            '                if location_lower in str(job.get("location") or "").lower()\n',
        ),
    ],
)

# 6. ai_resume_enhancer.py: annotate skills lists
patch(
    "src/interntrack/services/ai_resume_enhancer.py",
    [
        (
            '        """Extract skills based on context patterns."""\n        skills = []\n',
            '        """Extract skills based on context patterns."""\n        skills: list[dict[str, Any]] = []\n',
        ),
        (
            '        """Extract skills using synonym mapping."""\n        skills = []\n',
            '        """Extract skills using synonym mapping."""\n        skills: list[dict[str, Any]] = []\n',
        ),
        (
            '        """Extract implicit skills from experience descriptions."""\n        skills = []\n',
            '        """Extract implicit skills from experience descriptions."""\n        skills: list[dict[str, Any]] = []\n',
        ),
    ],
)

# 7. applications_v2.py: Column assignment ignores + dict annotations
patch(
    "src/interntrack/api/v1/applications_v2.py",
    [
        (
            "    new_status = ApplicationStatus(payload.status)\n    app.status = new_status\n",
            "    new_status = ApplicationStatus(payload.status)\n    app.status = new_status  # type: ignore[assignment]\n",
        ),
        (
            '    if payload.status == "applied" and not app.applied_at:\n        app.applied_at = datetime.now(UTC).replace(tzinfo=None)\n',
            '    if payload.status == "applied" and not app.applied_at:\n        app.applied_at = datetime.now(UTC).replace(tzinfo=None)  # type: ignore[assignment]\n',
        ),
        (
            "    if payload.status == \"interview\" and payload.interview_at:\n        app.interview_at = datetime.fromisoformat(\n            payload.interview_at.replace(\"Z\", \"+00:00\")\n        ).replace(tzinfo=None)\n",
            "    if payload.status == \"interview\" and payload.interview_at:\n        app.interview_at = datetime.fromisoformat(\n            payload.interview_at.replace(\"Z\", \"+00:00\")\n        ).replace(tzinfo=None)  # type: ignore[assignment]\n",
        ),
        (
            "    # Update notes\n    if payload.notes:\n        app.notes = payload.notes\n",
            "    # Update notes\n    if payload.notes:\n        app.notes = payload.notes  # type: ignore[assignment]\n",
        ),
        (
            "    status_counts = {}\n",
            "    status_counts: dict[str, int] = {}\n",
        ),
        (
            '    status_info = STATUS_FLOW.get(current_status, {})\n    timeline.append(\n        {\n            "status": current_status,\n            "icon": status_info.get("icon", "❓"),\n            "timestamp": str(app.updated_at) if app.updated_at else None,\n            "note": app.notes or f"Status: {current_status}",\n        }\n    )\n',
            '    status_info = STATUS_FLOW.get(current_status, {})\n    timeline.append(\n        {\n            "status": current_status,\n            "icon": str(status_info.get("icon", "❓")),\n            "timestamp": str(app.updated_at) if app.updated_at else None,\n            "note": str(app.notes or f"Status: {current_status}"),\n        }\n    )\n',
        ),
    ],
)

# 8. domains.py: str() coercion of Column attrs
patch(
    "src/interntrack/api/v1/domains.py",
    [
        (
            "        job_domains = _classify_job(job.title, job.description, job.tags or [])\n"
            "        if domain in job_domains:\n",
            "        job_domains = _classify_job(\n"
            "            str(job.title), str(job.description or \"\"), list(job.tags or [])\n"
            "        )\n"
            "        if domain in job_domains:\n",
        ),
        (
            "        job_domains = _classify_job(job.title, job.description, job.tags or [])\n"
            "        if domain not in job_domains:\n",
            "        job_domains = _classify_job(\n"
            "            str(job.title), str(job.description or \"\"), list(job.tags or [])\n"
            "        )\n"
            "        if domain not in job_domains:\n",
        ),
    ],
)

# 9. salary_insights.py: annotations + str() coercion
patch(
    "src/interntrack/api/v1/salary_insights.py",
    [
        (
            "    salaries = []\n    by_domain = {}\n    by_location = {}\n",
            "    salaries = []\n    by_domain: dict[str, list] = {}\n    by_location: dict[str, list] = {}\n",
        ),
        (
            "            domain_key = _classify_domain(job.title, job.description)\n",
            "            domain_key = _classify_domain(\n"
            "                str(job.title), str(job.description or \"\")\n"
            "            )\n",
        ),
        (
            "        j for j in all_jobs if _classify_domain(j.title, j.description) == domain\n",
            "        j\n"
            "        for j in all_jobs\n"
            "        if _classify_domain(str(j.title), str(j.description or \"\")) == domain\n",
        ),
        (
            "    company_salaries = {}\n",
            "    company_salaries: dict[str, list] = {}\n",
        ),
    ],
)

# 10. weekly_digest.py: annotations + tags iteration
patch(
    "src/interntrack/api/v1/weekly_digest.py",
    [
        (
            "    skill_counts = {}\n"
            "    for job in recent_jobs:\n"
            "        if job.tags:\n"
            "            for tag in job.tags:\n",
            "    skill_counts: dict[str, int] = {}\n"
            "    for job in recent_jobs:\n"
            "        if job.tags:\n"
            "            for tag in list(job.tags):\n",
        ),
        (
            "    by_day = {}\n",
            "    by_day: dict[str, int] = {}\n",
        ),
    ],
)

# 11. scheduler/jobs.py: fix _location_breakdown_table call + annotations
patch(
    "src/interntrack/scheduler/jobs.py",
    [
        (
            "        parts.append(\n"
            "            _location_breakdown_table(location_sections, other_sections, loc_lower)\n"
            "        )\n",
            "        parts.append(\n"
            "            _location_breakdown_table(location_sections, other_sections)\n"
            "        )\n",
        ),
        (
            "    dom_loc = {}\n"
            "    for _, job in all_jobs:\n"
            "        d = job.get(\"domain\") or \"other\"\n",
            "    dom_loc: dict[str, Counter] = {}\n"
            "    for _, job in all_jobs:\n"
            "        d = str(job.get(\"domain\") or \"other\")\n",
        ),
    ],
)

print("done")
