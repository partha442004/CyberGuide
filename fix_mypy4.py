"""Fix final batch of mypy errors."""
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


# 1. resume_parser.py
patch(
    "src/interntrack/api/v1/resume_parser.py",
    [
        (
            "    # Strategy 2: PyMuPDF (fast, good quality)\n"
            "    try:\n"
            "        import fitz  # PyMuPDF\n",
            "    # Strategy 2: PyMuPDF (fast, good quality)\n"
            "    try:\n"
            "        import fitz  # PyMuPDF  # type: ignore[import-untyped]\n",
        ),
        (
            "    # Strategy 3: pdfplumber (good fallback)\n"
            "    try:\n"
            "        import io\n"
            "\n"
            "        import pdfplumber\n",
            "    # Strategy 3: pdfplumber (good fallback)\n"
            "    try:\n"
            "        import io\n"
            "\n"
            "        import pdfplumber  # type: ignore[import-not-found]\n",
        ),
        (
            '    """Extract education entries from resume text."""\n    education = []\n',
            '    """Extract education entries from resume text."""\n    education: list[dict] = []\n',
        ),
        (
            "    # Categorize skills\n    skill_categories = {}\n",
            "    # Categorize skills\n    skill_categories: dict[str, list] = {}\n",
        ),
    ],
)

# 2. observability.py
patch(
    "src/interntrack/api/v1/observability.py",
    [
        (
            "        by_company[job.company] = by_company.get(job.company, 0) + 1\n",
            "        company_key = str(job.company)\n"
            "        by_company[company_key] = by_company.get(company_key, 0) + 1\n",
        ),
    ],
)

# 3. bookmarks.py
patch(
    "src/interntrack/api/v1/bookmarks.py",
    [
        (
            "    enriched = []\n    for bm in bookmarks:\n        item = {\n",
            "    enriched = []\n    for bm in bookmarks:\n        item: dict[str, Any] = {\n",
        ),
        (
            "    if payload.notes is not None:\n        bookmark.notes = payload.notes\n"
            "    if payload.tags is not None:\n        bookmark.tags = payload.tags\n",
            "    if payload.notes is not None:\n"
            "        bookmark.notes = payload.notes  # type: ignore[assignment]\n"
            "    if payload.tags is not None:\n"
            "        bookmark.tags = payload.tags  # type: ignore[assignment]\n",
        ),
        (
            "    all_tags = set()\n    for bm in bookmarks:\n        if bm.tags:\n            all_tags.update(bm.tags)\n",
            "    all_tags: set[str] = set()\n"
            "    for bm in bookmarks:\n"
            "        if bm.tags:\n"
            "            all_tags.update(bm.tags)\n",
        ),
    ],
)

# 4. weekly_digest.py
patch(
    "src/interntrack/api/v1/weekly_digest.py",
    [
        (
            "    # Group by source\n    by_source = {}\n"
            "    for job in jobs:\n        source = job.source.value if job.source else \"unknown\"\n",
            "    # Group by source\n    by_source: dict[str, int] = {}\n"
            "    for job in jobs:\n        source = job.source.value if job.source else \"unknown\"\n",
        ),
        (
            "    by_domain = {}\n"
            "    for job in jobs:\n"
            "        domain = _classify_domain(job.title, job.description)\n",
            "    by_domain: dict[str, int] = {}\n"
            "    for job in jobs:\n"
            "        domain = _classify_domain(str(job.title), str(job.description or \"\"))\n",
        ),
    ],
)

# 5. scheduler/jobs.py: annotate loc_totals
patch(
    "src/interntrack/scheduler/jobs.py",
    [
        (
            "    dom_loc[d][loc] += 1\n    loc_totals = Counter()\n",
            "    dom_loc[d][loc] += 1\n    loc_totals: Counter[str] = Counter()\n",
        ),
    ],
)

# 6. bookmarks.py needs Any import? check
print("done")
