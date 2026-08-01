"""
Check Point Software Technologies Careers Scraper

Scrapes cybersecurity jobs from Check Point's custom careers portal.
Check Point uses a custom PHP-based ATS (not Workday).
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from cybershield.scrapers.base import ScrapedJob, ScraperConfig
from cybershield.scrapers.companies.base_company import BaseCompanyScraper

logger = logging.getLogger(__name__)

__all__ = ["CheckPointScraper"]


class CheckPointScraper(BaseCompanyScraper):
    """Scraper for Check Point Software Technologies Careers."""

    CAREER_URL = "https://careers.checkpoint.com"
    SEARCH_URL = "https://careers.checkpoint.com/index.php?m=cpcareers&a=search"

    DEFAULT_KEYWORDS = [
        "security engineer",
        "security analyst",
        "cybersecurity",
        "information security",
        "cloud security",
        "network security",
        "SOC",
        "threat intelligence",
        "incident response",
        "penetration testing",
        "vulnerability",
        "firewall",
        "Check Point",
        "Quantum",
        "SIEM",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="company_checkpoint",
            base_url=self.CAREER_URL,
            rate_limit=0.33,
            max_retries=3,
        )
        super().__init__(
            company_name="Check Point Software Technologies",
            career_url=self.CAREER_URL,
            config=config,
        )

    def _parse_job_from_html(self, job_data: Dict[str, Any]) -> ScrapedJob:
        """Parse job data from HTML response."""
        job = ScrapedJob()

        job.title = job_data.get("title", "").strip()
        job.company_name = "Check Point Software Technologies"
        job.source = "company_checkpoint"
        job.source_id = str(job_data.get("job_id", ""))

        # URL
        job_id = job_data.get("job_id", "")
        if job_id:
            job.url = f"{self.CAREER_URL}/index.php?m=cpcareers&a=show&joborderid={job_id}"
        else:
            job.url = self.CAREER_URL

        # Location
        location = job_data.get("location", "")
        if location:
            job.location = location.strip()
            loc_lower = location.lower()
            if "united states" in loc_lower or "usa" in loc_lower or "(us)" in loc_lower:
                job.country = "USA"
            elif "india" in loc_lower or "bangalore" in loc_lower or "hyderabad" in loc_lower:
                job.country = "India"
            elif "remote" in loc_lower:
                job.is_remote = True
                job.country = "Remote"
            elif "uk" in loc_lower or "london" in loc_lower:
                job.country = "UK"
            elif "israel" in loc_lower or "tel aviv" in loc_lower or "herzliya" in loc_lower:
                job.country = "Israel"
            elif "singapore" in loc_lower:
                job.country = "Singapore"
            elif "australia" in loc_lower or "sydney" in loc_lower:
                job.country = "Australia"
            elif "canada" in loc_lower or "toronto" in loc_lower:
                job.country = "Canada"
            elif "germany" in loc_lower or "berlin" in loc_lower:
                job.country = "Germany"
            else:
                job.country = "Global"
        else:
            job.country = "Remote"

        # Job type
        job.job_type = "full_time"

        # Experience level
        job.experience_level = "mid"

        # Description
        job.description = job_data.get("description", "")

        # Skills - extract from title and description
        all_text = f"{job.title} {job.description}"
        job.required_skills = self._extract_skills(all_text)

        job = self._tag_job(job)
        return job

    async def _fetch_search_page(self, keyword: str, page: int = 1) -> str:
        """Fetch search results HTML page."""
        params = {
            "m": "cpcareers",
            "a": "search",
            "q": keyword,
            "page": page,
        }
        url = f"{self.SEARCH_URL}?{urlencode(params)}"
        await self._rate_limit_wait()
        response = await self._fetch(url)
        return response.text

    def _extract_jobs_from_html(self, html: str) -> List[Dict[str, Any]]:
        """Extract job listings from HTML response."""
        jobs = []

        # Match job listing patterns from Check Point's HTML
        # Pattern: <a href="...joborderid=XXXX">Title</a> with location info
        job_pattern = re.compile(r'joborderid=(\d+)[^"]*"[^>]*>([^<]+)</a>', re.IGNORECASE)

        # Also try to extract location from nearby elements
        location_pattern = re.compile(
            r'<td[^>]*class="[^"]*location[^"]*"[^>]*>([^<]+)</td>', re.IGNORECASE
        )

        matches = job_pattern.findall(html)
        locations = location_pattern.findall(html)

        for i, (job_id, title) in enumerate(matches):
            location = locations[i].strip() if i < len(locations) else ""
            jobs.append(
                {
                    "job_id": job_id,
                    "title": title.strip(),
                    "location": location,
                    "description": "",
                }
            )

        return jobs

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        max_pages: int = 3,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape security jobs from Check Point careers."""
        keywords = keywords or self.DEFAULT_KEYWORDS
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        for keyword in keywords:
            logger.info(f"Scraping Check Point for: {keyword}")

            for page in range(1, max_pages + 1):
                try:
                    html = await self._fetch_search_page(keyword, page)
                    job_listings = self._extract_jobs_from_html(html)

                    if not job_listings:
                        break

                    for job_data in job_listings:
                        job = self._parse_job_from_html(job_data)
                        if job.source_id and job.source_id not in seen_ids:
                            if self._is_security_role(job):
                                seen_ids.add(job.source_id)
                                all_jobs.append(job)

                except Exception as e:
                    logger.error(f"Error scraping Check Point for '{keyword}': {e}")
                    break

        logger.info(f"Check Point scraper found {len(all_jobs)} security jobs")
        return all_jobs
