"""
Hacker News 'Who is hiring?' scraper.
"""

import re
from datetime import UTC, datetime

from interntrack.domain.enums import JobSource
from interntrack.scrapers.base import BaseScraper, RawJob, matches_query


class HackerNewsScraper(BaseScraper):
    """Scraper for Hacker News 'Who is hiring?' threads."""

    @property
    def source_name(self) -> str:
        return JobSource.HACKER_NEWS.value

    @property
    def rate_limit(self) -> int:
        return 30

    async def fetch(
        self,
        query: str,
        location: str | None = None,  # noqa: ARG002 (interface contract)
        limit: int = 100,
    ) -> list[RawJob]:
        """Fetch jobs from Hacker News."""
        jobs: list[RawJob] = []

        # Get "Who is hiring?" thread
        thread_id = await self._get_latest_hiring_thread()
        if not thread_id:
            return jobs

        # Get comments (job postings)
        comments = await self._get_thread_comments(thread_id)

        for comment in comments[:limit]:
            job = self._parse_comment(comment, query)
            if job:
                jobs.append(job)

        return jobs

    async def _get_latest_hiring_thread(self) -> str | None:
        """Get the latest 'Who is hiring?' thread ID."""
        url = "https://hacker-news.firebaseio.com/v0/showstories.json"
        response = await self._get(url)
        story_ids = response.json()

        for story_id in story_ids[:30]:
            story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            story_response = await self._get(story_url)
            story = story_response.json()

            if story and "who is hiring" in story.get("title", "").lower():
                return str(story_id)

        return None

    async def _get_thread_comments(self, story_id: str) -> list[dict]:
        """Get comments from a thread."""
        url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
        response = await self._get(url)
        story = response.json()

        comments = []
        kids = story.get("kids", [])

        for kid_id in kids[:100]:
            comment_url = f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json"
            comment_response = await self._get(comment_url)
            comment = comment_response.json()
            if comment and not comment.get("deleted"):
                comments.append(comment)

        return comments

    def _parse_comment(self, comment: dict, query: str) -> RawJob | None:
        """Parse a comment into a RawJob."""
        text = comment.get("text", "")
        if not text:
            return None

        # Extract job info from comment
        lines = text.split("<p>")
        if not lines:
            return None

        first_line = lines[0]
        title = self._extract_title(first_line)
        company = self._extract_company(first_line)

        if not title:
            return None

        # Check if matches query (multi-token + security-family expansion)
        if not matches_query(text, query) and not matches_query(title, query):
            return None

        return RawJob(
            title=title,
            company=company or "Unknown",
            url=f"https://news.ycombinator.com/item?id={comment.get('id')}",
            description=text,
            source=self.source_name,
            posted_at=datetime.fromtimestamp(comment.get("time", 0), tz=UTC),
            tags=self._extract_tags(text),
        )

    def _extract_title(self, text: str) -> str | None:
        """Extract job title from text."""
        # Common patterns: "Company | Title | Location | ..."
        parts = re.split(r"\||-", text)
        if len(parts) >= 2:
            # Usually title is after company
            for part in parts[:3]:
                part = re.sub(r"<[^>]+>", "", part).strip()
                if len(part) > 5 and len(part) < 100:
                    return part
        return None

    def _extract_company(self, text: str) -> str | None:
        """Extract company name from text."""
        parts = re.split(r"\||-", text)
        if parts:
            return re.sub(r"<[^>]+>", "", parts[0]).strip()
        return None

    def _extract_tags(self, text: str) -> list[str]:
        """Extract tags from job description."""
        tags = []
        text_lower = text.lower()

        tag_keywords = {
            "remote": "remote",
            "python": "python",
            "javascript": "javascript",
            "react": "react",
            "node": "node.js",
            "full stack": "fullstack",
            "backend": "backend",
            "frontend": "frontend",
            "devops": "devops",
            "senior": "senior",
            "junior": "junior",
            "intern": "internship",
        }

        for keyword, tag in tag_keywords.items():
            if keyword in text_lower:
                tags.append(tag)

        return tags
