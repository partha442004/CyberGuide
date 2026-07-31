"""
Google Careers Scraper

Scrapes cybersecurity jobs from Google's career page.
"""

import logging
from typing import Any, Dict, List, Optional

from cybershield.scrapers.base import ScrapedJob, ScraperConfig
from cybershield.scrapers.companies.base_company import BaseCompanyScraper

logger = logging.getLogger(__name__)


class GoogleScraper(BaseCompanyScraper):
    """Scraper for Google Careers."""

    CAREER_URL = "https://www.google.com/about/careers/applications/jobs/results"
    API_URL = "https://www.google.com/about/careers/applications/search/job"

    DEFAULT_KEYWORDS = [
        "security engineer",
        "information security",
        "cloud security",
        "GCP security",
        "application security",
        "incident response",
        "threat analysis",
        "security analyst",
        "Trust and Safety",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="company_google",
            base_url=self.CAREER_URL,
            rate_limit=0.25,
            max_retries=3,
        )
        super().__init__(
            company_name="Google",
            career_url=self.CAREER_URL,
            config=config,
        )

    def _build_search_url(self, keyword: str, page: int = 0) -> str:
        """Build search URL."""
        from urllib.parse import urlencode
        params = {
            "q": keyword,
            "start": page * 10,
        }
        return f"{self.API_URL}?{urlencode(params)}"

    def _parse_job_data(self, job_data: Dict[str, Any]) -> ScrapedJob:
        """Parse job data from Google API."""
        job = ScrapedJob()

        job.title = job_data.get("title", "").strip()
        job.company_name = "Google"
        job.source = "company_google"
        job.source_id = job_data.get("id", "")

        # URL
        job_id = job_data.get("id", "")
        job.url = f"https://www.google.com/about/careers/applications/jobs/results/{job_id}"

        # Location
        locations = job_data.get("locations", [])
        if locations:
            job.location = locations[0] if locations else ""
            for loc in locations:
                loc_lower = loc.lower()
                if "usa" in loc_lower or "united states" in loc_lower:
                    job.country = "USA"
                elif "india" in loc_lower or "bangalore" in loc_lower:
                    job.country = "India"
                elif "remote" in loc_lower:
                    job.is_remote = True
                    job.country = "Remote"

        # Minimum/Maximum qualifications for skills
        min_quals = job_data.get("minimumQualifications", "")
        pref_quals = job_data.get("preferredQualifications", "")
        description = job_data.get("description", "")

        job.description = description

        # Skills
        combined_text = f"{min_quals} {pref_quals} {description}"
        job.required_skills = self._extract_skills(combined_text)

        # Job type
        job.job_type = "full_time"

        # Posting date
        posted = job_data.get("postedDate", "")
        job.posting_date = self._parse_date(posted)

        job = self._tag_job(job)
        return job

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        max_pages: int = 5,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape security jobs from Google."""
        keywords = keywords or self.DEFAULT_KEYWORDS
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        for keyword in keywords:
            logger.info(f"Scraping Google for: {keyword}")

            for page in range(max_pages):
                try:
                    url = self._build_search_url(keyword, page)
                    response = await self._fetch(url)
                    data = response.json()

                    jobs_data = data.get("jobs", [])
                    if not jobs_data:
                        break

                    for job_data in jobs_data:
                        job = self._parse_job_data(job_data)
                        if job.source_id and job.source_id not in seen_ids:
                            if self._is_security_role(job):
                                seen_ids.add(job.source_id)
                                all_jobs.append(job)

                except Exception as e:
                    logger.error(f"Error scraping Google for '{keyword}': {e}")
                    break

        logger.info(f"Google scraper found {len(all_jobs)} security jobs")
        return all_jobs
