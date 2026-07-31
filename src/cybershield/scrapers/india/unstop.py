"""
Unstop (formerly Dare2Compete) Scraper

Scrapes cybersecurity competitions, hackathons, and jobs from Unstop.com.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig

logger = logging.getLogger(__name__)


class UnstopScraper(BaseScraper):
    """Scraper for Unstop.com."""

    BASE_URL = "https://unstop.com"
    API_URL = "https://unstop.com/api/search"

    # Cybersecurity keywords
    DEFAULT_KEYWORDS = [
        "cyber security",
        "CTF",
        "hackathon",
        "bug bounty",
        "ethical hacking",
        "security challenge",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="unstop",
            base_url=self.BASE_URL,
            rate_limit=0.5,
            max_retries=3,
        )
        super().__init__(config)

    def _build_search_url(self, keyword: str, page: int = 1) -> str:
        """Build search URL."""
        params = {
            "query": keyword,
            "type": "all",  # competitions, hackathons, jobs
            "page": page,
        }
        return f"{self.API_URL}?{urlencode(params)}"

    def _parse_job_data(self, item_data: Dict[str, Any], item_type: str) -> ScrapedJob:
        """Parse item data."""
        job = ScrapedJob()

        job.title = item_data.get("title", "").strip()
        job.company_name = item_data.get("organization", {}).get("name", "").strip()
        job.url = f"{self.BASE_URL}/{'hackathon' if item_type == 'hackathon' else 'competitions'}/{item_data.get('slug', '')}"
        job.source = "unstop"
        job.source_id = str(item_data.get("id", ""))

        # Location
        job.location = item_data.get("location", "")
        if not job.location or "online" in job.location.lower():
            job.is_remote = True
            job.is_onsite = False
        job.country = "India"  # Unstop is primarily India-focused

        # Type mapping
        if item_type == "hackathon":
            job.job_type = "hackathon"
        elif item_type == "competition":
            job.job_type = "competition"
        else:
            job.job_type = "full_time"

        # Skills
        job.required_skills = item_data.get("skills", [])

        # Dates
        start_date = item_data.get("start_date", "")
        end_date = item_data.get("end_date", "")
        job.posting_date = self._parse_date(start_date)
        job.deadline = self._parse_date(end_date)

        # Description
        job.description = item_data.get("description", "")
        if job.description:
            desc_skills = self._extract_skills(job.description)
            job.required_skills = list(set(job.required_skills + desc_skills))

        # Prize/rewards for competitions
        prize = item_data.get("prize", "")
        if prize:
            job.raw_data["prize"] = prize

        return job

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        max_pages: int = 3,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape from Unstop."""
        keywords = keywords or self.DEFAULT_KEYWORDS
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        for keyword in keywords:
            logger.info(f"Scraping Unstop for keyword: {keyword}")

            for page in range(1, max_pages + 1):
                try:
                    url = self._build_search_url(keyword, page)
                    response = await self._fetch(url)
                    data = response.json()

                    # Parse different item types
                    for item_type in ["hackathons", "competitions", "jobs"]:
                        items = data.get(item_type, [])
                        for item_data in items:
                            job = self._parse_job_data(item_data, item_type.rstrip("s"))
                            if job.source_id and job.source_id not in seen_ids:
                                seen_ids.add(job.source_id)
                                all_jobs.append(job)

                except Exception as e:
                    logger.error(f"Error scraping Unstop page {page} for '{keyword}': {e}")
                    break

        logger.info(f"Unstop scraper found {len(all_jobs)} items")
        return all_jobs
