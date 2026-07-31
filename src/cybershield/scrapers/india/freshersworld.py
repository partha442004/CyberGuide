"""
Freshersworld Scraper

Scrapes cybersecurity jobs for freshers from Freshersworld.com.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig

logger = logging.getLogger(__name__)


class FreshersworldScraper(BaseScraper):
    """Scraper for Freshersworld.com."""

    BASE_URL = "https://www.freshersworld.com"
    SEARCH_URL = "https://www.freshersworld.com/jobs/search"

    # Cybersecurity keywords for freshers
    DEFAULT_KEYWORDS = [
        "cyber security",
        "information security",
        "security analyst",
        "network security",
        "SOC",
        "ethical hacking",
        "VAPT",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="freshersworld",
            base_url=self.BASE_URL,
            rate_limit=0.5,
            max_retries=3,
        )
        super().__init__(config)

    def _build_search_url(self, keyword: str, page: int = 1) -> str:
        """Build search URL."""
        params = {
            "searchTerm": keyword,
            "pageNo": page,
        }
        return f"{self.SEARCH_URL}?{urlencode(params)}"

    def _parse_job_data(self, job_data: Dict[str, Any]) -> ScrapedJob:
        """Parse individual job data."""
        job = ScrapedJob()

        job.title = job_data.get("jobTitle", "").strip()
        job.company_name = job_data.get("companyName", "").strip()
        job.url = job_data.get("jobUrl", "")
        job.source = "freshersworld"
        job.source_id = job_data.get("jobId", job_data.get("id", ""))

        # Location
        job.location = job_data.get("location", "")
        if job.location:
            job.country = "India"
            job.city = job.location.split(",")[0].strip()

        # Salary
        salary = job_data.get("salary", "")
        if salary and salary != "Not Disclosed":
            try:
                salary_clean = salary.replace("₹", "").replace(",", "").replace("LPA", "").strip()
                if "-" in salary_clean:
                    parts = salary_clean.split("-")
                    job.salary_min = float(parts[0].strip()) * 100000  # Convert LPA to annual
                    job.salary_max = float(parts[1].strip()) * 100000
                else:
                    job.salary_min = float(salary_clean) * 100000
                    job.salary_max = job.salary_min
                job.salary_currency = "INR"
            except (ValueError, IndexError):
                pass

        # Experience - Freshersworld is for freshers
        job.experience_level = "fresher"
        job.job_type = "full_time"

        # Skills
        skills = job_data.get("skills", [])
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",")]
        job.required_skills = skills

        # Posting date
        posted_date = job_data.get("postedDate", "")
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
        """Scrape jobs from Freshersworld."""
        keywords = keywords or self.DEFAULT_KEYWORDS
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        for keyword in keywords:
            logger.info(f"Scraping Freshersworld for keyword: {keyword}")

            for page in range(1, max_pages + 1):
                try:
                    url = self._build_search_url(keyword, page)
                    response = await self._fetch(url)
                    data = response.json()

                    jobs_data = data.get("jobs", data.get("results", []))
                    if not jobs_data:
                        break

                    for job_data in jobs_data:
                        job = self._parse_job_data(job_data)
                        if job.source_id and job.source_id not in seen_ids:
                            seen_ids.add(job.source_id)
                            all_jobs.append(job)

                except Exception as e:
                    logger.error(f"Error scraping Freshersworld page {page} for '{keyword}': {e}")
                    break

        logger.info(f"Freshersworld scraper found {len(all_jobs)} jobs")
        return all_jobs
