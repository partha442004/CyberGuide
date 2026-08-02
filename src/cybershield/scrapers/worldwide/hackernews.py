"""
HackerNews Scraper

Scrapes "Who is hiring?" threads from Hacker News for cybersecurity jobs.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig

logger = logging.getLogger(__name__)


class HackerNewsScraper(BaseScraper):
    """Scraper for Hacker News "Who is hiring?" threads."""

    HN_API = "https://hacker-news.firebaseio.com/v0"
    HN_ALGOLIA = "https://hn.algolia.com/api/v1"

    DEFAULT_KEYWORDS = [
        "security",
        "cyber",
        "soc",
        "infosec",
        "devsecops",
        "penetration",
        "vulnerability",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="hackernews",
            base_url="https://news.ycombinator.com",
            rate_limit=0.5,
            max_retries=3,
        )
        super().__init__(config)

    async def _find_hiring_threads(
        self, query: str = "who is hiring", limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find 'Who is hiring?' threads using Algolia API."""
        url = f"{self.HN_ALGOLIA}/search"
        params = {
            "query": query,
            "tags": "story",
            "hitsPerPage": limit,
        }
        response = await self._fetch(url, params=params)
        data = response.json()
        hits = data.get("hits", [])
        return [hit for hit in hits if isinstance(hit, dict)]

    async def _get_comment_items(
        self, story_id: int, max_comments: int = 100
    ) -> List[Dict[str, Any]]:
        """Get all comments for a story (limited to prevent N+1)."""
        url = f"{self.HN_API}/item/{story_id}.json"
        response = await self._fetch(url)
        story = response.json()

        if not story or "kids" not in story:
            return []

        items = []
        kid_ids = story.get("kids", [])[:max_comments]  # Limit to prevent N+1

        # Fetch in batches using asyncio
        import asyncio

        async def fetch_item(item_id: int) -> Optional[Dict[str, Any]]:
            item_url = f"{self.HN_API}/item/{item_id}.json"
            item_response = await self._fetch(item_url)
            data = item_response.json()
            return data if isinstance(data, dict) else None

        # Fetch up to 10 comments concurrently
        batch_size = 10
        for i in range(0, len(kid_ids), batch_size):
            batch = kid_ids[i : i + batch_size]
            results = await asyncio.gather(
                *[fetch_item(kid) for kid in batch], return_exceptions=True
            )
            for result in results:
                if isinstance(result, dict) and result.get("type") == "comment":
                    items.append(result)

        return items

    def _parse_comment(self, comment: Dict[str, Any]) -> List[ScrapedJob]:
        """Parse a comment (job posting) from HN thread."""
        jobs: List[ScrapedJob] = []
        text = comment.get("text", "")

        if not text or len(text) < 50:
            return jobs

        # Check if this is a job posting (not a reply to someone)
        # HN job posts typically start with company name
        text_lower = text.lower()

        # Look for security-related keywords
        security_keywords = [
            "security",
            "cyber",
            "soc",
            "infosec",
            "devsecops",
            "penetration",
            "vulnerability",
            "threat",
            "incident",
            "forensic",
            "malware",
            "compliance",
        ]

        is_security_job = any(kw in text_lower for kw in security_keywords)
        if not is_security_job:
            return jobs

        job = ScrapedJob()

        # Try to extract company name (usually first line). Comments from the
        # HN API start with "<p>", so split yields an empty first element -
        # skip blank lines to reach the real content.
        lines = text.split("<p>")
        first_line = next((ln for ln in lines if ln.strip()), text) if lines else text
        # Clean HTML
        first_line = re.sub(r"<[^>]+>", "", first_line).strip()

        if "|" in first_line:
            parts = first_line.split("|")
            job.company_name = parts[0].strip()
            # Rest might have location, role info
            for part in parts[1:]:
                part_clean = part.strip().lower()
                if "remote" in part_clean:
                    job.is_remote = True
                    job.is_onsite = False
                    job.location = "Remote"
                elif any(loc in part_clean for loc in ["sf", "new york", "london", "berlin"]):
                    job.location = part.strip()
        else:
            job.company_name = first_line[:100]  # Truncate long names

        # Title - try to extract role from text
        title_patterns = [
            r"(?:hiring|looking for|seeking)\s+(?:a\s+)?(.+?)(?:\s*\.|<)",
            r"(?:role|position)\s*:\s*(.+?)(?:\s*\.|<)",
        ]
        for pattern in title_patterns:
            match = re.search(pattern, text_lower)
            if match:
                job.title = match.group(1).strip().title()
                break

        if not job.title:
            job.title = f"Security Role at {job.company_name or 'Company'}"

        # URL
        job.url = f"https://news.ycombinator.com/item?id={comment.get('id', '')}"
        job.source = "hackernews"
        job.source_id = str(comment.get("id", ""))

        # Clean description
        clean_text = re.sub(r"<[^>]+>", " ", text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        job.description = clean_text[:2000]  # Limit length

        # Extract skills
        job.required_skills = self._extract_skills(text)

        # Country
        if job.is_remote:
            job.country = "Remote"
        else:
            job.country = "USA"  # HN is primarily USA

        job.job_type = "full_time"
        job.posting_date = datetime.fromtimestamp(comment.get("time", 0), tz=timezone.utc)

        jobs.append(job)
        return jobs

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        max_threads: int = 3,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape security jobs from Hacker News."""
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        try:
            # Find recent "Who is hiring?" threads
            threads = await self._find_hiring_threads(limit=max_threads)

            for thread in threads:
                raw_id = thread.get("objectID")
                title = thread.get("title", "")

                logger.info(f"Scraping HN thread: {title}")

                # Get comments
                comments = await self._get_comment_items(int(raw_id)) if raw_id else []

                for comment in comments:
                    jobs = self._parse_comment(comment)
                    for job in jobs:
                        if job.source_id and job.source_id not in seen_ids:
                            seen_ids.add(job.source_id)
                            all_jobs.append(job)

        except Exception as e:
            logger.error(f"Error scraping HackerNews: {e}")

        logger.info(f"HackerNews scraper found {len(all_jobs)} jobs")
        return all_jobs
