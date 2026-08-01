"""
Amazon Careers Scraper

Scrapes cybersecurity jobs from Amazon's career page.
"""

import logging
from typing import Any, Dict, List, Optional

from cybershield.scrapers.base import ScrapedJob, ScraperConfig
from cybershield.scrapers.companies.base_company import BaseCompanyScraper

logger = logging.getLogger(__name__)


class AmazonScraper(BaseCompanyScraper):
    """Scraper for Amazon Careers."""

    CAREER_URL = "https://www.amazon.jobs/en/search"
    API_URL = "https://www.amazon.jobs/en/search.json"

    DEFAULT_KEYWORDS = [
        "security engineer",
        "information security",
        "AWS security",
        "cloud security",
        "application security",
        "security analyst",
        "threat intelligence",
        "compliance",
        "identity and access management",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="company_amazon",
            base_url=self.CAREER_URL,
            rate_limit=0.33,
            max_retries=3,
        )
        super().__init__(
            company_name="Amazon",
            career_url=self.CAREER_URL,
            config=config,
        )

    def _build_search_url(self, keyword: str, page: int = 1) -> str:
        """Build search URL."""
        from urllib.parse import urlencode

        params = {
            "base": keyword,
            "locGroup": "",
            "loc": "",
            "bg": "",
            "p": page,
            "ie": "",
            "oo": "",
            "src": "GBSS",
        }
        return f"{self.API_URL}?{urlencode(params)}"

    def _parse_job_data(self, job_data: Dict[str, Any]) -> ScrapedJob:
        """Parse job data from Amazon API."""
        job = ScrapedJob()

        job.title = job_data.get("title", "").strip()
        job.company_name = "Amazon"
        job.source = "company_amazon"
        job.source_id = job_data.get("job_id", "")

        # URL
        job_id = job_data.get("job_id", "")
        job.url = f"https://www.amazon.jobs/en/jobs/{job_id}"

        # Location
        location = job_data.get("location", "")
        job.location = location
        if location:
            loc_lower = location.lower()
            if "united states" in loc_lower or "usa" in loc_lower:
                job.country = "USA"
            elif "india" in loc_lower:
                job.country = "India"
            elif "remote" in loc_lower:
                job.is_remote = True
                job.country = "Remote"

        # Description
        job.description = job_data.get("description", "")

        # Basic qualifications
        basic_quals = job_data.get("basic_qualifications", "")
        pref_quals = job_data.get("preferred_qualifications", "")
        combined_text = f"{basic_quals} {pref_quals} {job.description}"
        job.required_skills = self._extract_skills(combined_text)

        # Job type
        job.job_type = "full_time"

        # Posting date
        posted = job_data.get("posted_date", "")
        job.posting_date = self._parse_date(posted)

        # Team
        team = job_data.get("team", "")
        if team:
            job.raw_data["team"] = team

        job = self._tag_job(job)
        return job

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        max_pages: int = 5,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape security jobs from Amazon."""
        keywords = keywords or self.DEFAULT_KEYWORDS
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        for keyword in keywords:
            logger.info(f"Scraping Amazon for: {keyword}")

            for page in range(1, max_pages + 1):
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
                    logger.error(f"Error scraping Amazon for '{keyword}': {e}")
                    break

        logger.info(f"Amazon scraper found {len(all_jobs)} security jobs")
        return all_jobs
