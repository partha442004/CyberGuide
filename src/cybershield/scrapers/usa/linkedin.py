"""
LinkedIn Scraper

Scrapes cybersecurity jobs from LinkedIn Jobs (via public RSS feeds).
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from feedparser import parse as parse_feed

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn Jobs (via RSS)."""

    BASE_URL = "https://www.linkedin.com/jobs/search"
    RSS_URL = "https://www.linkedin.com/jobs/search/rss"

    DEFAULT_KEYWORDS = [
        "cyber security",
        "information security",
        "SOC analyst",
        "security engineer",
        "penetration testing",
        "threat hunting",
        "cloud security",
        "application security",
        "DevSecOps",
        "incident response",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="linkedin",
            base_url=self.BASE_URL,
            rate_limit=0.25,  # 1 request per 4 seconds
            max_retries=3,
        )
        super().__init__(config)

    def _build_rss_url(self, keyword: str, location: str = "United States") -> str:
        """Build LinkedIn RSS feed URL."""
        params = {
            "keywords": keyword,
            "location": location,
            "f_TPR": "r604800",  # Past week
            "sortBy": "DD",  # Sort by date
        }
        return f"{self.RSS_URL}?{urlencode(params)}"

    def _parse_feed_entry(self, entry: Dict[str, Any]) -> Optional[ScrapedJob]:
        """Parse individual RSS feed entry."""
        try:
            job = ScrapedJob()

            # Title
            job.title = entry.get("title", "").strip()

            # URL
            job.url = self._normalize_url(entry.get("link", ""))

            # Description/Summary
            summary = entry.get("summary", "")
            job.description = summary

            # Parse company and location from title (LinkedIn format: "Job at Company in Location")
            title = job.title
            if " at " in title and " in " in title:
                parts = title.split(" at ")
                if len(parts) == 2:
                    job.title = parts[0].strip()
                    location_parts = parts[1].split(" in ")
                    if len(location_parts) == 2:
                        job.company_name = location_parts[0].strip()
                        job.location = location_parts[1].strip()
                    else:
                        job.company_name = parts[1].strip()
            elif " at " in title:
                parts = title.split(" at ")
                if len(parts) == 2:
                    job.title = parts[0].strip()
                    job.company_name = parts[1].strip()

            # Location
            if job.location:
                if "remote" in job.location.lower():
                    job.is_remote = True
                    job.is_onsite = False
                if "united states" in job.location.lower() or "usa" in job.location.lower():
                    job.country = "USA"
                elif "india" in job.location.lower():
                    job.country = "India"
                elif "remote" in job.location.lower():
                    job.country = "Remote"
            else:
                job.country = "USA"

            # Source
            job.source = "linkedin"
            job.source_id = self._extract_job_id(job.url)

            # Job type
            job.job_type = "full_time"

            # Posted date
            published = entry.get("published", "")
            job.posting_date = self._parse_date(published)

            # Skills from description
            job.required_skills = self._extract_skills(summary)

            return job

        except Exception as e:
            logger.error(f"Error parsing LinkedIn feed entry: {e}")
            return None

    def _extract_job_id(self, url: str) -> str:
        """Extract job ID from LinkedIn URL."""
        import re
        if not url:
            return ""
        match = re.search(r'/view/[^/]*/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'currentJob=(\d+)', url)
        if match:
            return match.group(1)
        return ""

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        location: str = "United States",
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape jobs from LinkedIn RSS feeds."""
        keywords = keywords or self.DEFAULT_KEYWORDS
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        for keyword in keywords:
            logger.info(f"Scraping LinkedIn for keyword: {keyword}")

            try:
                url = self._build_rss_url(keyword, location)
                response = await self._fetch(url)
                feed = parse_feed(response.text)

                for entry in feed.entries:
                    job = self._parse_feed_entry(entry)
                    if job and job.source_id and job.source_id not in seen_ids:
                        seen_ids.add(job.source_id)
                        all_jobs.append(job)

            except Exception as e:
                logger.error(f"Error scraping LinkedIn for '{keyword}': {e}")
                continue

        logger.info(f"LinkedIn scraper found {len(all_jobs)} jobs")
        return all_jobs
