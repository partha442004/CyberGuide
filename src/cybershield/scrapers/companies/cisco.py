"""
Cisco Careers Scraper

Scrapes cybersecurity jobs from Cisco's career page.
"""

import logging
from typing import Any, Dict, List, Optional

from cybershield.scrapers.base import ScrapedJob, ScraperConfig
from cybershield.scrapers.companies.base_company import BaseCompanyScraper

logger = logging.getLogger(__name__)


class CiscoScraper(BaseCompanyScraper):
    """Scraper for Cisco Careers."""

    CAREER_URL = "https://jobs.cisco.com/jobs"
    API_URL = "https://jobs.cisco.com/api/search"

    DEFAULT_KEYWORDS = [
        "security engineer",
        "cybersecurity",
        "information security",
        "network security",
        "cloud security",
        "SOC",
        "threat intelligence",
        "incident response",
        "Talos",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="company_cisco",
            base_url=self.CAREER_URL,
            rate_limit=0.33,
            max_retries=3,
        )
        super().__init__(
            company_name="Cisco",
            career_url=self.CAREER_URL,
            config=config,
        )

    def _build_search_url(self, keyword: str, page: int = 0) -> str:
        """Build search URL."""
        from urllib.parse import urlencode
        params = {
            "keyword": keyword,
            "sortBy": "most relevant",
            "startDate": "custom",
            "customDate": "last15Days",
        }
        return f"{self.API_URL}?{urlencode(params)}"

    def _parse_job_data(self, job_data: Dict[str, Any]) -> ScrapedJob:
        """Parse job data from Cisco API."""
        job = ScrapedJob()

        job.title = job_data.get("title", "").strip()
        job.company_name = "Cisco"
        job.source = "company_cisco"
        job.source_id = str(job_data.get("jobId", ""))

        # URL
        job_id = job_data.get("jobId", "")
        job.url = f"https://jobs.cisco.com/jobs/{job_id}"

        # Location
        locations = job_data.get("locations", [])
        if locations:
            job.location = ", ".join(locations[:3])
            for loc in locations:
                loc_lower = loc.lower()
                if "united states" in loc_lower or "usa" in loc_lower:
                    job.country = "USA"
                elif "india" in loc_lower or "bangalore" in loc_lower:
                    job.country = "India"
                elif "remote" in loc_lower:
                    job.is_remote = True
                    job.country = "Remote"

        # Description
        job.description = job_data.get("jobDescription", "")

        # Skills from tags
        tags = job_data.get("tags", [])
        job.required_skills = tags

        # Extract skills from description
        if job.description:
            desc_skills = self._extract_skills(job.description)
            job.required_skills = list(set(job.required_skills + desc_skills))

        # Job type
        job.job_type = "full_time"

        # Posting date
        posted = job_data.get("datePosted", "")
        job.posting_date = self._parse_date(posted)

        # Department
        dept = job_data.get("department", "")
        if dept:
            job.raw_data["department"] = dept

        job = self._tag_job(job)
        return job

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        max_pages: int = 3,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape security jobs from Cisco."""
        keywords = keywords or self.DEFAULT_KEYWORDS
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        for keyword in keywords:
            logger.info(f"Scraping Cisco for: {keyword}")

            for page in range(max_pages):
                try:
                    url = self._build_search_url(keyword, page)
                    response = await self._fetch(url)
                    data = response.json()

                    jobs_data = data.get("jobRequisitions", {}).get("requisitionList", [])
                    if not jobs_data:
                        break

                    for job_data in jobs_data:
                        job = self._parse_job_data(job_data)
                        if job.source_id and job.source_id not in seen_ids:
                            if self._is_security_role(job):
                                seen_ids.add(job.source_id)
                                all_jobs.append(job)

                except Exception as e:
                    logger.error(f"Error scraping Cisco for '{keyword}': {e}")
                    break

        logger.info(f"Cisco scraper found {len(all_jobs)} security jobs")
        return all_jobs
