"""Apply remaining mypy fixes, normalizing CRLF/LF so patterns match."""
import io
import os

ROOT = "C:/Users/KIRA/CyberGuide"


def patch(path, replacements, must_apply=True):
    full = os.path.join(ROOT, path)
    with io.open(full, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("\r\n", "\n")  # normalize
    for old, new in replacements:
        if old not in text:
            if must_apply:
                print(f"WARN not found in {path}: {old[:70]!r}")
            continue
        text = text.replace(old, new, 1)
    with io.open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"patched {path}")


# 1. helpers.py: annotate to_naive_utc return type
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

# 2. application_repository.py: remove unused type: ignore (was at line 170)
patch(
    "src/interntrack/repositories/application_repository.py",
    [
        (
            "        application.status = new_status  # type: ignore[assignment]\n",
            "        application.status = new_status\n",
        ),
    ],
)

# 3. job_repository.py: bool -> Column[bool]
patch(
    "src/interntrack/repositories/job_repository.py",
    [
        (
            "            # Mark original as inactive\n            job.is_active = False\n",
            "            # Mark original as inactive\n            job.is_active = False  # type: ignore[assignment]\n",
        ),
    ],
)

# 4. report_service.py: str() coercion + no-any-return (helpers fix covers most)
patch(
    "src/interntrack/services/report_service.py",
    [
        (
            '                if location_lower in (job.get("location") or "").lower()\n',
            '                if location_lower in str(job.get("location") or "").lower()\n',
        ),
    ],
)

# 5. scheduler/jobs.py: fix _location_breakdown_table call + annotations
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
