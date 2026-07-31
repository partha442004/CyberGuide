"""
Internshala Scraper

Scrapes cybersecurity internships from Internshala.com (India's top internship platform).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig

logger = logging.getLogger(__name__)


class InternshalaScraper(BaseScraper):
    """Scraper for Internshala.com."""

    BASE_URL = "https://internshala.com"
    API_URL = "https://internshala.com/jobs/search"

    # Cybersecurity internship keywords
    DEFAULT_KEYWORDS = [
        "cyber security",
        "information security",
        "security intern",
        "SOC intern",
        "penetration testing",
        "ethical hacking",
        "vulnerability assessment",
        "security analyst",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="internshala",
            base_url=self.BASE_URL,
            rate_limit=0.5,
            max_retries=3,
        )
        super().__init__(config)

    def _build_search_url(self, keyword: str, page: int = 1) -> str:
        """Build search URL."""
        params = {
            "searchTerm": keyword,
            "location": "",
            "page": page,
            "per_page": 20,
            "sort_by": "posted_date",
        }
        return f"{self.API_URL}?{urlencode(params)}"

    def _parse_job_data(self, job_data: Dict[str, Any]) -> ScrapedJob:
        """Parse individual job data."""
        job = ScrapedJob()

        job.title = job_data.get("title", "").strip()
        job.company_name = job_data.get("company_name", "").strip()
        job.url = f"{self.BASE_URL}/jobs/{job_data.get('url', '')}"
        job.source = "internshala"
        job.source_id = str(job_data.get("id", ""))

        # Location
        job.location = job_data.get("location", "")
        if job.location:
            job.country = "India"
            job.city = job.location.split(",")[0].strip()

        # Salary/Stipend
        stipend = job_data.get("stipend", {})
        if stipend:
            try:
                job.salary_min = float(stipend.get("salary", 0))
                job.salary_max = float(stipend.get("salary", 0))
                job.salary_currency = "INR"
            except (ValueError, TypeError):
                pass

        # Experience
        job.experience_level = "intern"  # Internshala is primarily internships
        job.job_type = "internship"

        # Skills
        skills = job_data.get("skills", [])
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",")]
        job.required_skills = skills

        # Remote work
        if job_data.get("remote", False):
            job.is_remote = True
            job.is_onsite = False

        # Duration
        duration = job_data.get("duration", "")
        if duration:
            job.raw_data["duration"] = duration

        # Posting date
        posted_date = job_data.get("posted_date", "")
        job.posting_date = self._parse_date(posted_date)

        # Description
        job.description = job_data.get("description", "")

        # Extract skills from description
        if job.description:
            desc_skills = self._extract_skills(job.description)
            job.required_skills = list(set(job.required_skills + desc_skills))

        return job

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        max_pages: int = 5,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape internships from Internshala."""
        keywords = keywords or self.DEFAULT_KEYWORDS
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        for keyword in keywords:
            logger.info(f"Scraping Internshala for keyword: {keyword}")

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
                            seen_ids.add(job.source_id)
                            all_jobs.append(job)

                except Exception as e:
                    logger.error(f"Error scraping Internshala page {page} for '{keyword}': {e}")
                    break

        logger.info(f"Internshala scraper found {len(all_jobs)} jobs")
        return all_jobs
