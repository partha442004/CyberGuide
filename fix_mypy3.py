"""Fix next batch of mypy errors."""
import io
import os

ROOT = "C:/Users/KIRA/CyberGuide"


def patch(path, replacements, must_apply=True):
    full = os.path.join(ROOT, path)
    with io.open(full, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("\r\n", "\n")
    for old, new in replacements:
        if old not in text:
            if must_apply:
                print(f"WARN not found in {path}: {old[:70]!r}")
            continue
        text = text.replace(old, new, 1)
    with io.open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"patched {path}")


# 1. helpers.py: type the dt param so no-any-return goes away
patch(
    "src/interntrack/utils/helpers.py",
    [
        (
            "def to_naive_utc(dt) -> datetime | None:\n"
            '    """Convert an aware datetime to naive UTC, or return naive as-is."""\n'
            "    if dt is None:\n"
            "        return None\n"
            "    if dt.tzinfo is not None:\n"
            "        return dt.astimezone(UTC).replace(tzinfo=None)\n"
            "    return dt\n",
            "def to_naive_utc(dt: datetime | None) -> datetime | None:\n"
            '    """Convert an aware datetime to naive UTC, or return naive as-is."""\n'
            "    if dt is None:\n"
            "        return None\n"
            "    if dt.tzinfo is not None:\n"
            "        return dt.astimezone(UTC).replace(tzinfo=None)\n"
            "    return dt\n",
        ),
    ],
)

# 2. application_repository.py: re-add the type ignore on status assignment
patch(
    "src/interntrack/repositories/application_repository.py",
    [
        (
            "        old_status = application.status\n"
            "        application.status = new_status\n"
            "\n"
            "        if new_status == ApplicationStatus.APPLIED and not application.applied_at:\n"
            "            application.applied_at = utcnow()  # type: ignore[assignment]\n",
            "        old_status = application.status\n"
            "        application.status = new_status  # type: ignore[assignment]\n"
            "\n"
            "        if new_status == ApplicationStatus.APPLIED and not application.applied_at:\n"
            "            application.applied_at = utcnow()  # type: ignore[assignment]\n",
        ),
        # line 170 unused ignore is on applied_at — remove it since only status needs it
        (
            "            application.applied_at = utcnow()  # type: ignore[assignment]\n",
            "            application.applied_at = utcnow()\n",
        ),
    ],
)

# 3. job_recommender.py: float() of object — cast via str()
patch(
    "src/interntrack/services/job_recommender.py",
    [
        (
            '            key=lambda x: float(x["match_score"]), reverse=True\n',
            '            key=lambda x: float(str(x["match_score"])), reverse=True\n',
        ),
    ],
)

# 4. salary_insights.py: remaining Column[str] setdefault/classify
patch(
    "src/interntrack/api/v1/salary_insights.py",
    [
        (
            "            loc = job.location or \"Remote\"\n"
            "            by_location.setdefault(loc, []).append(job.salary_max)\n",
            "            loc = str(job.location or \"Remote\")\n"
            "            by_location.setdefault(loc, []).append(job.salary_max)\n",
        ),
        (
            "            company_salaries.setdefault(job.company, []).append(job.salary_max)\n",
            "            company_salaries.setdefault(str(job.company), []).append(job.salary_max)\n",
        ),
        (
            "        j\n"
            "        for j in all_jobs\n"
            "        if _classify_domain(str(j.title), str(j.description or \"\")) == domain\n",
            "        j\n"
            "        for j in all_jobs\n"
            "        if _classify_domain(str(j.title), str(j.description or \"\")) == domain\n",
        ),
        (
            "    for job in domain_jobs:\n"
            "        if job.salary_max and job.salary_max > 0:\n"
            "            company_salaries.setdefault(str(job.company), []).append(job.salary_max)\n"
            "            salaries.append(job.salary_max)\n"
            "            company_salaries.setdefault(job.company, []).append(job.salary_max)\n",
            "    for job in domain_jobs:\n"
            "        if job.salary_max and job.salary_max > 0:\n"
            "            company_salaries.setdefault(str(job.company), []).append(job.salary_max)\n"
            "            salaries.append(job.salary_max)\n",
        ),
    ],
)

print("done")
