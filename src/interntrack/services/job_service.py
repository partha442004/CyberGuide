"""
Job service for job management and discovery orchestration.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.domain.enums import JobType
from interntrack.domain.exceptions import DuplicateJobError
from interntrack.domain.models import Job
from interntrack.repositories.job_repository import JobRepository

# String column limits on the Job model. Postgres enforces varchar(N) on
# insert (SQLite does not), so an over-long field from a scraper crashed
# discovery with StringDataRightTruncationError. Every save path clamps to
# these limits before hitting the DB.
_JOB_FIELD_LIMITS = {"title": 500, "company": 200, "location": 200, "url": 2000}

# Title keywords that imply a job type. Checked against the lowercased
# title so the dashboard's "job types" chart isn't all unknown — most
# scrapers never set job_type.
_JOB_TYPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("internship", ("intern", "internship", "fresher", "trainee", "apprentice")),
    ("part_time", ("part-time", "part time", "parttime")),
    ("contract", ("contract", "contractor")),
    ("freelance", ("freelance", "gig")),
]

# Common skill keywords extracted from a job's title + description when the
# scraper provided no ``tags`` (very common: share-a-job entries, thin RSS
# feeds, boards that only give title/company). Jobs without tags score
# ``match_score: null`` against every resume and never appear in keyword
# matching, which is exactly the "no match %" complaint. Deriving tags at
# save time gives those jobs real match scores and ATS keyword signals.
_AUTO_TAG_KEYWORDS: tuple[str, ...] = (
    # Programming / software
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "node.js",
    "go",
    "rust",
    "c++",
    "sql",
    "mysql",
    "postgresql",
    "mongodb",
    "linux",
    "git",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
    "terraform",
    "devops",
    "ci/cd",
    "machine learning",
    "data analysis",
    "pandas",
    # Cybersecurity
    "cybersecurity",
    "information security",
    "network security",
    "cloud security",
    "application security",
    "soc analyst",
    "security analyst",
    "penetration testing",
    "pentest",
    "vapt",
    "ethical hacking",
    "burp suite",
    "nmap",
    "wireshark",
    "splunk",
    "siem",
    "incident response",
    "malware",
    "threat intelligence",
    "vulnerability assessment",
    "firewall",
    "grc",
    "compliance",
    "iso 27001",
    "gdpr",
    "risk management",
    # Expanded: scripting / cloud / tooling / soft skills commonly listed in
    # descriptions but missing from scraper tags — more signal for match %.
    "powershell",
    "bash",
    "networking",
    "tcp/ip",
    "owasp",
    "cissp",
    "ceh",
    "osint",
    "dfir",
    "zero trust",
    "iam",
    "api",
    "rest api",
    "postman",
    "jira",
    "agile",
    "scrum",
    "excel",
    "tableau",
    "power bi",
    "etl",
    "airflow",
    "spark",
    "kafka",
    "django",
    "flask",
    "fastapi",
    "spring",
    "flutter",
    "html",
    "css",
    "figma",
)


def _derive_required_skills(job_data: dict) -> list[str]:
    """Skills mentioned in the description, for match scoring.

    Scans the same keyword dictionary as :func:`auto_tag_job` over the
    title + description and returns the matched keywords — these become
    ``required_skills`` so resume match % is computed from real signals
    even when the source board never structured them.
    """
    import re

    text = " ".join(
        str(job_data.get(field) or "") for field in ("title", "description")
    ).lower()
    found: list[str] = []
    for keyword in _AUTO_TAG_KEYWORDS:
        pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
        if re.search(pattern, text):
            found.append(keyword)
    return found[:20]


def auto_tag_job(job_data: dict) -> dict:
    """Derive skill ``tags`` from the title + description.

    Only fills the gap when the scraper provided no tags at all — explicit
    scraper tags always win. Keywords are matched on word boundaries so
    short tokens (``go``, ``sql``) never hit inside unrelated words.
    Returns the (possibly unchanged) job dict.
    """
    import re

    existing = [str(t).strip() for t in (job_data.get("tags") or []) if str(t).strip()]
    if existing:
        return job_data
    text = " ".join(
        str(job_data.get(field) or "") for field in ("title", "description")
    ).lower()
    if not text.strip():
        return job_data
    found: list[str] = []
    for keyword in _AUTO_TAG_KEYWORDS:
        pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
        if re.search(pattern, text):
            found.append(keyword)
    if found:
        return {**job_data, "tags": found[:15]}
    return job_data


def classify_job_type(title: str) -> str:
    """Infer a job type from the title ("internship", "full_time", ...).

    Explicit markers (intern/contract/part-time/...) win; everything else
    defaults to full-time, which matches reality for ~95% of postings and
    keeps the dashboard chart meaningful instead of all "unknown".
    """
    text = (title or "").lower()
    for job_type, keywords in _JOB_TYPE_KEYWORDS:
        if any(k in text for k in keywords):
            return job_type
    return "full_time"


def _normalize_job_fields(job_data: dict) -> dict:
    """Clamp string fields to the Job model's column limits."""
    normalized = dict(job_data)
    for field, limit in _JOB_FIELD_LIMITS.items():
        value = normalized.get(field)
        if isinstance(value, str):
            stripped = value.strip()
            normalized[field] = stripped[:limit] if len(stripped) > limit else stripped
    # Infer a job type when the scraper didn't provide one, so dashboards
    # and filters show meaningful categories instead of all-unknown.
    if not normalized.get("job_type") or str(normalized.get("job_type")).lower() in (
        "unknown",
        "none",
    ):
        normalized["job_type"] = classify_job_type(
            normalized.get("title", ""),
        )
    # Derive skill tags when the scraper gave none — jobs without tags
    # score ``match_score: null`` against every resume (the "no match %"
    # gap). This runs before the DB insert so every saved job is scoreable.
    normalized = auto_tag_job(normalized)
    # Derive required_skills from the description when the source left them
    # empty, so match % is computed from real description signals.
    if not [s for s in (normalized.get("required_skills") or []) if str(s).strip()]:
        derived = _derive_required_skills(normalized)
        if derived:
            normalized["required_skills"] = derived
    return normalized


class JobService:
    """Job service for job management."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = JobRepository(session)

    async def create_job(self, job_data: dict) -> Job:
        """Create a new job, checking for duplicates."""
        job_data = _normalize_job_fields(job_data)
        existing = await self.job_repo.get_by_url(job_data.get("url", ""))
        if existing:
            raise DuplicateJobError(
                job_data.get("title", "Unknown"),
                job_data.get("company", "Unknown"),
            )

        # Cross-source dedup: the same posting often arrives from several
        # boards (LinkedIn India, Indeed India, TimesJobs, ...) under
        # different URLs. URL-only dedup lets copies through, so also match
        # normalized title+company within a recent window.
        same = await self.job_repo.find_cross_source_duplicate(
            job_data.get("title", ""),
            job_data.get("company", ""),
        )
        if same:
            raise DuplicateJobError(
                job_data.get("title", "Unknown"),
                job_data.get("company", "Unknown"),
            )

        job = Job(**job_data)
        return await self.job_repo.create(job)

    async def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        return await self.job_repo.get_by_id(job_id)

    async def get_jobs(
        self,
        skip: int = 0,
        limit: int = 100,
        job_type: JobType | None = None,
        is_remote: bool | None = None,
        company: str | None = None,
    ) -> list[Job]:
        """Get jobs with filters."""
        return await self.job_repo.get_active_jobs(
            skip=skip,
            limit=limit,
            job_type=job_type,
            is_remote=is_remote,
            company=company,
        )

    async def search_jobs(self, query: str, limit: int = 50) -> list[Job]:
        """Search jobs by query."""
        return await self.job_repo.search_jobs(query, limit)

    async def save_jobs(self, jobs: list[dict]) -> list[Job]:
        """Save multiple jobs, skipping duplicates."""
        saved_jobs = []
        for job_data in jobs:
            try:
                job = await self.create_job(job_data)
                saved_jobs.append(job)
            except DuplicateJobError:
                continue
        return saved_jobs

    async def get_job_statistics(self) -> dict:
        """Get job statistics."""
        top_companies_raw = await self.job_repo.get_top_companies()
        job_types_raw = await self.job_repo.get_job_type_distribution()

        return {
            "total_jobs": await self.job_repo.count({"is_active": True}),
            "salary_stats": await self.job_repo.get_salary_statistics(),
            "top_companies": [{"company": c, "jobs": n} for c, n in top_companies_raw],
            "job_types": [
                {"type": t.value if hasattr(t, "value") else str(t), "count": n}
                for t, n in job_types_raw
            ],
        }

    async def get_closing_soon(self, days: int = 2) -> list[Job]:
        """Get jobs closing soon."""
        return await self.job_repo.get_closing_soon(days)

    async def deactivate_expired(self) -> int:
        """Deactivate expired jobs."""
        return await self.job_repo.deactivate_expired()
