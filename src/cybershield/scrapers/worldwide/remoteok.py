"""
RemoteOK Scraper

Scrapes remote cybersecurity jobs from RemoteOK.com.
"""

import logging
from typing import Any, Dict, List, Optional

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig

logger = logging.getLogger(__name__)


class RemoteOKScraper(BaseScraper):
    """Scraper for RemoteOK.com."""

    API_URL = "https://remoteok.com/api"

    DEFAULT_KEYWORDS = [
        "security",
        "cyber",
        "soc",
        "infosec",
        "devsecops",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="remoteok",
            base_url="https://remoteok.com",
            rate_limit=0.5,
            max_retries=3,
        )
        super().__init__(config)

    def _parse_job_data(self, job_data: Dict[str, Any]) -> ScrapedJob:
        """Parse job data from RemoteOK API."""
        job = ScrapedJob()

        job.title = job_data.get("position", "").strip()
        job.company_name = job_data.get("company", "").strip()
        job.url = job_data.get("url", "")
        job.source = "remoteok"
        job.source_id = str(job_data.get("id", ""))

        # RemoteOK is always remote
        job.is_remote = True
        job.is_onsite = False
        job.country = "Remote"
        job.location = "Remote"

        # Salary
        salary_min = job_data.get("salary_min")
        salary_max = job_data.get("salary_max")
        if salary_min:
            job.salary_min = float(salary_min)
        if salary_max:
            job.salary_max = float(salary_max)
        job.salary_currency = "USD"

        # Tags/skills
        tags = job_data.get("tags", [])
        job.required_skills = tags

        # Job type
        job.job_type = "full_time"

        # Description
        job.description = job_data.get("description", "")
        if job.description:
            desc_skills = self._extract_skills(job.description)
            job.required_skills = list(set(job.required_skills + desc_skills))

        # Date
        date_created = job_data.get("date", "")
        job.posting_date = self._parse_date(date_created)

        return job

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape jobs from RemoteOK."""
        all_jobs: List[ScrapedJob] = []

        try:
            response = await self._fetch(self.API_URL)
            jobs_data = response.json()

            # First entry is usually metadata, skip it
            if jobs_data and isinstance(jobs_data[0], dict) and "legal" in jobs_data[0]:
                jobs_data = jobs_data[1:]

            keywords = keywords or self.DEFAULT_KEYWORDS
            keywords_lower = [k.lower() for k in keywords]

            for job_data in jobs_data:
                # Filter by security-related keywords
                tags = [t.lower() for t in job_data.get("tags", [])]
                position = job_data.get("position", "").lower()
                company = job_data.get("company", "").lower()

                # Check if job matches any keyword
                matches = False
                for kw in keywords_lower:
                    if (kw in tags or kw in position or
                        any(kw in tag for tag in tags)):
                        matches = True
                        break

                if matches:
                    job = self._parse_job_data(job_data)
                    if job.source_id:
                        all_jobs.append(job)

        except Exception as e:
            logger.error(f"Error scraping RemoteOK: {e}")

        logger.info(f"RemoteOK scraper found {len(all_jobs)} jobs")
        return all_jobs
