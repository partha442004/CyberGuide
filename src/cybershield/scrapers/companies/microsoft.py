"""
Microsoft Careers Scraper

Scrapes cybersecurity jobs from Microsoft's career page.
"""

import logging
from typing import Any, Dict, List, Optional

from cybershield.scrapers.base import ScrapedJob, ScraperConfig
from cybershield.scrapers.companies.base_company import BaseCompanyScraper

logger = logging.getLogger(__name__)


class MicrosoftScraper(BaseCompanyScraper):
    """Scraper for Microsoft Careers."""

    CAREER_URL = "https://careers.microsoft.com/global/en/search"
    API_URL = "https://gcsservices.careers.microsoft.com/search/api/v1/search"

    DEFAULT_KEYWORDS = [
        "security engineer",
        "security analyst",
        "cybersecurity",
        "information security",
        "cloud security",
        "Azure security",
        "SOC",
        "threat intelligence",
        "identity security",
        "compliance",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="company_microsoft",
            base_url=self.CAREER_URL,
            rate_limit=0.33,
            max_retries=3,
        )
        super().__init__(
            company_name="Microsoft",
            career_url=self.CAREER_URL,
            config=config,
        )

    def _build_search_url(self, keyword: str, page: int = 1) -> str:
        """Build API search URL."""
        params = {
            "q": keyword,
            "lc": ["United States", "India", "Remote"],
            "pg": page,
            "pgSz": 20,
            "flt": True,
        }
        # URL encode manually for complex params
        from urllib.parse import urlencode
        return f"{self.API_URL}?{urlencode(params, doseq=True)}"

    def _parse_job_data(self, job_data: Dict[str, Any]) -> ScrapedJob:
        """Parse job data from Microsoft API."""
        job = ScrapedJob()

        job.title = job_data.get("title", "").strip()
        job.company_name = "Microsoft"
        job.source = "company_microsoft"
        job.source_id = job_data.get("jobId", "")

        # URL
        job_id = job_data.get("jobId", "")
        job.url = f"https://careers.microsoft.com/global/en/job/{job_id}"

        # Location
        locations = job_data.get("locations", [])
        if locations:
            job.location = ", ".join(locations[:3])
            # Determine country
            for loc in locations:
                loc_lower = loc.lower()
                if "united states" in loc_lower or "usa" in loc_lower:
                    job.country = "USA"
                elif "india" in loc_lower:
                    job.country = "India"
                elif "remote" in loc_lower:
                    job.is_remote = True
                    job.country = "Remote"

        # Job type
        job.job_type = job_data.get("jobType", "full_time").lower()

        # Description
        job.description = job_data.get("description", "")

        # Skills
        tags = job_data.get("tags", [])
        job.required_skills = tags

        # Extract skills from description
        if job.description:
            desc_skills = self._extract_skills(job.description)
            job.required_skills = list(set(job.required_skills + desc_skills))

        # Posting date
        posted = job_data.get("postedDate", "")
        job.posting_date = self._parse_date(posted)

        job = self._tag_job(job)
        return job

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        max_pages: int = 3,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape security jobs from Microsoft."""
        keywords = keywords or self.DEFAULT_KEYWORDS
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        for keyword in keywords:
            logger.info(f"Scraping Microsoft for: {keyword}")

            for page in range(1, max_pages + 1):
                try:
                    url = self._build_search_url(keyword, page)
                    response = await self._fetch(url)
                    data = response.json()

                    jobs_data = data.get("operationResult", {}).get("result", {}).get("jobs", [])
                    if not jobs_data:
                        break

                    for job_data in jobs_data:
                        job = self._parse_job_data(job_data)
                        if job.source_id and job.source_id not in seen_ids:
                            if self._is_security_role(job):
                                seen_ids.add(job.source_id)
                                all_jobs.append(job)

                except Exception as e:
                    logger.error(f"Error scraping Microsoft for '{keyword}': {e}")
                    break

        logger.info(f"Microsoft scraper found {len(all_jobs)} security jobs")
        return all_jobs
