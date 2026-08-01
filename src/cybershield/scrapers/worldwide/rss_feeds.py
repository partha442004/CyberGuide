"""
RSS Feed Scraper

Scrapes cybersecurity jobs from various RSS feeds.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from feedparser import parse as parse_feed

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig

logger = logging.getLogger(__name__)


class RSSFeedScraper(BaseScraper):
    """Scraper for RSS feeds."""

    # Curated list of cybersecurity-related RSS feeds
    SECURITY_FEEDS = {
        "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
        "The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
        "SecurityWeek": "https://feeds.feedburner.com/securityweek",
        "Dark Reading": "https://www.darkreading.com/rss.xml",
        "Krebs on Security": "https://krebsonsecurity.com/feed/",
        "SANS Internet Storm Center": "https://isc.sans.edu/rssfeed.xml",
    }

    JOB_FEEDS = {
        "We Work Remotely Security": "https://weworkremotely.com/categories/remote-cybersecurity-jobs.rss",
        "RemoteOK Security": "https://remoteok.com/remote-security-jobs.rss",
        "Indeed USA": "https://www.indeed.com/rss?q=cyber+security&l=United+States&sort=date",
    }

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="rss_feeds",
            base_url="",
            rate_limit=0.5,
            max_retries=3,
        )
        super().__init__(config)

    def _parse_feed_entry(self, entry: Dict[str, Any], feed_name: str) -> Optional[ScrapedJob]:
        """Parse a single RSS feed entry."""
        try:
            job = ScrapedJob()

            # Title
            job.title = entry.get("title", "").strip()

            # URL
            link = entry.get("link", "")
            job.url = self._normalize_url(link)
            urlparse(link) if link else None
            job.source = f"rss_{feed_name.lower().replace(' ', '_')}"
            job.source_id = entry.get("id", link)

            # Description
            summary = entry.get("summary", "")
            job.description = summary

            # Extract skills from title and description
            combined_text = f"{job.title} {summary}"
            job.required_skills = self._extract_skills(combined_text)

            # Parse company from title if possible
            title = job.title
            if " - " in title:
                parts = title.split(" - ")
                if len(parts) >= 2:
                    # Could be "Role - Company" or "Company - Role"
                    job.company_name = parts[-1].strip()
                    job.title = parts[0].strip()

            # Date
            published = entry.get("published", "")
            job.posting_date = self._parse_date(published)

            # Check for security keywords in content
            security_keywords = ["security", "cyber", "soc", "vulnerability",
                               "threat", "penetration", "incident"]
            if not any(kw in combined_text.lower() for kw in security_keywords):
                return None

            # Job type
            job.job_type = "full_time"
            job.country = "Remote"  # RSS feeds often feature remote jobs
            job.is_remote = True

            return job

        except Exception as e:
            logger.error(f"Error parsing RSS entry from {feed_name}: {e}")
            return None

    async def scrape(
        self,
        feeds: Optional[Dict[str, str]] = None,
        include_job_feeds: bool = True,
        include_security_feeds: bool = False,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape jobs from RSS feeds."""
        all_jobs: List[ScrapedJob] = []
        seen_urls = set()

        # Determine which feeds to use
        feed_list = {}
        if feeds:
            feed_list.update(feeds)
        if include_job_feeds:
            feed_list.update(self.JOB_FEEDS)
        if include_security_feeds:
            feed_list.update(self.SECURITY_FEEDS)

        for feed_name, feed_url in feed_list.items():
            logger.info(f"Scraping RSS feed: {feed_name}")

            try:
                response = await self._fetch(feed_url)
                feed = parse_feed(response.text)

                for entry in feed.entries:
                    job = self._parse_feed_entry(entry, feed_name)
                    if job and job.source_id not in seen_urls:
                        seen_urls.add(job.source_id)
                        all_jobs.append(job)

            except Exception as e:
                logger.error(f"Error scraping RSS feed {feed_name}: {e}")
                continue

        logger.info(f"RSS feeds scraper found {len(all_jobs)} items")
        return all_jobs
