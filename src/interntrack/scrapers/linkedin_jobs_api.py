"""
LinkedIn Jobs API integration.

Uses LinkedIn's public job search API for fetching jobs.
Note: LinkedIn has strict rate limits and requires proper headers.
"""

import contextlib
import logging
from datetime import datetime
from urllib.parse import urlencode

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

logger = logging.getLogger(__name__)


class LinkedInJobsAPIScraper(BaseScraper):
    """Scraper for LinkedIn Jobs using public API."""

    BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    @property
    def source_name(self) -> str:
        return "linkedin_jobs_api"

    @property
    def rate_limit(self) -> int:
        return 10  # Very conservative rate limit for LinkedIn

    async def fetch(
        self,
        query: str,
        location: str | None = None,
        limit: int = 25,
    ) -> list[RawJob]:
        """Fetch jobs from LinkedIn Jobs API."""
        jobs = []

        try:
            # Build search query
            search_query = query
            if location and location.lower() not in query.lower():
                search_query = f"{query} {location}"

            params = {
                "keywords": search_query,
                "sortBy": "DD",  # Sort by date
                "f_TPR": "r604800",  # Last 7 days
                "position": 1,
                "pageNum": 0,
            }

            if location:
                params["location"] = location

            url = f"{self.BASE_URL}?{urlencode(params)}"
            response = await self._get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )

            if response.status_code == 200:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")

                # Find job cards
                job_cards = soup.find_all("li")

                for card in job_cards[:limit]:
                    job = self._parse_job_card(card)
                    if job and matches_query(job.title, query, title=job.title):
                        jobs.append(job)

        except Exception as e:
            logger.error(f"Error fetching from LinkedIn Jobs API: {e}")

        return jobs

    def _parse_job_card(self, card) -> RawJob | None:
        """Parse a job card from LinkedIn HTML."""
        try:
            # Extract title
            title_elem = card.find("h3", class_="base-search-card__title")
            if not title_elem:
                title_elem = card.find("a", class_="hidden-nested-link")
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract company
            company_elem = card.find("h4", class_="base-search-card__subtitle")
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Extract URL
            link_elem = card.find("a", href=True)
            url = None
            if link_elem:
                href = link_elem.get("href", "")
                url = (
                    href
                    if href.startswith("http")
                    else f"https://www.linkedin.com{href}"
                )

            # Extract location
            location_elem = card.find("span", class_="job-search-card__location")
            location = location_elem.get_text(strip=True) if location_elem else "Remote"

            # Extract posted date
            date_elem = card.find("time", class_="job-search-card__listdate")
            posted_at = None
            if date_elem:
                datetime_attr = date_elem.get("datetime")
                if datetime_attr:
                    with contextlib.suppress(ValueError):
                        posted_at = datetime.fromisoformat(
                            datetime_attr.replace("Z", "+00:00")
                        )

            if not title:
                return None

            return RawJob(
                title=title,
                company=company,
                url=url or f"https://www.linkedin.com/jobs/search/?keywords={title}",
                location=location,
                posted_at=posted_at,
                source=self.source_name,
                tags=self._extract_tags(title),
            )

        except Exception:
            return None

    def _extract_tags(self, title: str) -> list[str]:
        """Extract skill tags from job title."""
        tags = []
        text = title.lower()

        skill_keywords = {
            "python": "python",
            "javascript": "javascript",
            "security": "security",
            "cyber": "cybersecurity",
            "soc": "soc",
            "pentest": "penetration testing",
            "vapt": "vapt",
            "aws": "aws",
            "docker": "docker",
            "remote": "remote",
            "entry level": "entry-level",
            "senior": "senior",
        }

        for keyword, tag in skill_keywords.items():
            if keyword in text:
                tags.append(tag)

        return tags
