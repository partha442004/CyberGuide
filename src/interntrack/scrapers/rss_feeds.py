"""
RSS Feed job scraper.
"""

import contextlib
from datetime import UTC, datetime

import feedparser

from interntrack.domain.enums import JobSource
from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

# Popular job RSS feeds.
#
# URLs may contain {query} / {location} placeholders that are substituted
# with the discovery query/location before fetching. Only feeds that return
# actual job postings are listed here. Dropped for being dead or bot-gated:
# remoteok (410), Naukri RSS (404), Instahyre (Cloudflare 403), the LinkedIn
# jobs "RSS" (login wall, returns HTML), and hnrss.org feeds (they return
# news articles / thread shells, not job posts).
DEFAULT_FEEDS = {
    "weworkremotely": "https://weworkremotely.com/remote-jobs.rss",
    "remotive": "https://remotive.com/remote-jobs/feed",
}


class RSSFeedScraper(BaseScraper):
    """Scraper for RSS job feeds."""

    def __init__(self, feeds: dict | None = None):
        super().__init__()
        self.feeds = feeds or DEFAULT_FEEDS

    @property
    def source_name(self) -> str:
        return JobSource.RSS_FEED.value

    @property
    def rate_limit(self) -> int:
        return 60

    async def fetch(
        self,
        query: str,
        location: str | None = None,  # noqa: ARG002 (interface contract)
        limit: int = 100,
    ) -> list[RawJob]:
        """Fetch jobs from RSS feeds."""
        jobs = []

        for feed_name, feed_url in self.feeds.items():
            try:
                # Substitute {query}/{location} placeholders so keyword-aware
                # feeds actually search for what the user asked for.
                feed_url = feed_url.replace("{query}", (query or "").replace(" ", "+"))
                if location:
                    feed_url = feed_url.replace(
                        "{location}",
                        location.replace(" ", "+"),
                    )
                # Always emit the enum source name ("rss_feed") so the stored
                # value round-trips through the JobSource column; the raw feed
                # key is only used for logging/tracking below.
                feed_jobs = await self._fetch_feed(feed_url, query, self.source_name)
                jobs.extend(feed_jobs)
            except Exception as e:
                print(f"Error fetching RSS feed {feed_name}: {e}")
                continue

        return jobs[:limit]

    async def _fetch_feed(
        self,
        feed_url: str,
        query: str,
        source_name: str,
    ) -> list[RawJob]:
        """Fetch and parse a single RSS feed."""
        jobs = []

        response = await self._get(feed_url)
        feed = feedparser.parse(response.text)

        for entry in feed.entries[:50]:
            job = self._parse_entry(entry, query, source_name)
            if job:
                jobs.append(job)

        return jobs

    def _parse_entry(
        self,
        entry: dict,
        query: str,
        source_name: str,
    ) -> RawJob | None:
        """Parse RSS entry into RawJob."""
        title = entry.get("title", "")
        link = entry.get("link", "")
        summary = entry.get("summary", "")
        published = entry.get("published_parsed")

        # Check if matches query (multi-token + security-family expansion;
        # security queries match against the title so descriptions mentioning
        # "security" generically don't flood the results)
        if not matches_query(f"{title} {summary}", query, title=title):
            return None

        # Parse published date
        posted_at = None
        if published:
            with contextlib.suppress(Exception):
                posted_at = datetime(
                    published[0],
                    published[1],
                    published[2],
                    published[3],
                    published[4],
                    published[5],
                    tzinfo=UTC,
                )

        return RawJob(
            title=title,
            company=self._extract_company_from_title(title),
            url=link,
            description=summary,
            posted_at=posted_at,
            tags=self._extract_tags(summary),
            source=source_name,
        )

    def _extract_company_from_title(self, title: str) -> str:
        """Try to extract company name from title."""
        import re

        # Common patterns: "Company is hiring" or "Hiring: Company"
        patterns = [
            r"^(.+?)\s+(?:is|are)\s+hiring",
            r"(?:hiring|hired)\s*[:\-]\s*(.+?)$",
            r"^\[(.+?)\]",
        ]

        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "Unknown"

    def _extract_tags(self, text: str) -> list[str]:
        """Extract tags from text."""
        tags = []
        text_lower = text.lower()

        common_tags = [
            "python",
            "javascript",
            "react",
            "node",
            "aws",
            "docker",
            "kubernetes",
            "remote",
            "fullstack",
            "backend",
            "frontend",
        ]

        for tag in common_tags:
            if tag in text_lower:
                tags.append(tag)

        return tags


class CustomRSSFeedScraper(RSSFeedScraper):
    """Scraper for custom RSS feeds."""

    def __init__(self, feed_urls: list[str]):
        feeds = {f"custom_{i}": url for i, url in enumerate(feed_urls)}
        super().__init__(feeds=feeds)
