"""
Verification engine for validating job postings.
"""

import re

from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.repositories.job_repository import JobRepository


class VerificationEngine:
    """Engine for verifying job postings."""

    # Suspicious patterns
    SPAM_PATTERNS = [
        r"make money fast",
        r"work from home.*\$\d+",
        r"guaranteed income",
        r"no experience needed.*high pay",
        r"click here to apply",
        r"limited time offer",
        r"act now",
    ]

    REQUIRED_FIELDS = ["title", "company", "url"]

    def __init__(self, session: AsyncSession):
        self.session = session
        self.job_repo = JobRepository(session)

    async def verify_job(self, job_data: dict) -> tuple[bool, list[str]]:
        """Verify a job posting and return (is_valid, issues)."""
        issues = []

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if not job_data.get(field):
                issues.append(f"Missing required field: {field}")

        # Check for spam patterns
        spam_issues = self._check_spam(job_data)
        issues.extend(spam_issues)

        # Validate URL
        url_issues = self._validate_url(job_data.get("url", ""))
        issues.extend(url_issues)

        # Validate salary
        salary_issues = self._validate_salary(job_data)
        issues.extend(salary_issues)

        is_valid = len(issues) == 0
        return is_valid, issues

    async def verify_jobs(self, jobs: list[dict]) -> tuple[list[dict], list[dict]]:
        """Verify multiple jobs and return (valid_jobs, invalid_jobs)."""
        valid_jobs = []
        invalid_jobs = []

        for job in jobs:
            is_valid, issues = await self.verify_job(job)
            if is_valid:
                valid_jobs.append(job)
            else:
                invalid_jobs.append({**job, "_issues": issues})

        return valid_jobs, invalid_jobs

    def _check_spam(self, job_data: dict) -> list[str]:
        """Check for spam patterns."""
        issues = []
        text = f"{job_data.get('title', '')} {job_data.get('description', '')}".lower()

        for pattern in self.SPAM_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Potential spam detected: {pattern}")
                break

        return issues

    def _validate_url(self, url: str) -> list[str]:
        """Validate job URL."""
        issues = []

        if not url:
            issues.append("Empty URL")
            return issues

        if not url.startswith(("http://", "https://")):
            issues.append("Invalid URL format")

        if len(url) > 2000:
            issues.append("URL too long")

        return issues

    def _validate_salary(self, job_data: dict) -> list[str]:
        """Validate salary information."""
        issues = []
        salary_min = job_data.get("salary_min")
        salary_max = job_data.get("salary_max")

        if salary_min and salary_max:
            if salary_min > salary_max:
                issues.append("Minimum salary greater than maximum")

            # Check for unrealistic salaries
            if salary_max and salary_max > 1000000:
                issues.append("Suspiciously high salary")

        return issues

    async def check_link_health(self, url: str) -> dict[str, any]:
        """Check if job URL is still accessible."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.head(url, follow_redirects=True)
                return {
                    "url": url,
                    "status_code": response.status_code,
                    "is_alive": response.status_code < 400,
                    "redirect_url": str(response.url) if response.url != url else None,
                }
        except Exception as e:
            return {
                "url": url,
                "status_code": None,
                "is_alive": False,
                "error": str(e),
            }

    async def verify_all_links(self, job_ids: list[str] | None = None) -> list[dict]:
        """Verify links for multiple jobs."""
        if job_ids:
            jobs = [await self.job_repo.get_by_id(jid) for jid in job_ids]
            jobs = [j for j in jobs if j]
        else:
            jobs = await self.job_repo.get_all(limit=100)

        results = []
        for job in jobs:
            result = await self.check_link_health(job.url)
            result["job_id"] = job.id
            result["job_title"] = job.title
            results.append(result)

        return results
