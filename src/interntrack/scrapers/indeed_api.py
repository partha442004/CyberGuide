"""
Indeed API integration.

Uses Indeed's public job search for fetching jobs.
Note: Indeed has anti-scraping measures. This uses their search page.
"""

import logging
import re
from urllib.parse import urlencode

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

logger = logging.getLogger(__name__)


class IndeedAPIScraper(BaseScraper):
    """Scraper for Indeed Jobs using public search."""

    BASE_URL = "https://www.indeed.com"

    @property
    def source_name(self) -> str:
        return "indeed_api"

    @property
    def rate_limit(self) -> int:
        return 15  # Conservative rate limit

    async def fetch(
        self,
        query: str,
        location: str | None = None,
        limit: int = 25,
    ) -> list[RawJob]:
        """Fetch jobs from Indeed API."""
        jobs = []

        try:
            # Build search query
            search_query = query
            if location and location.lower() not in query.lower():
                search_query = f"{query} {location}"

            params = {
                "q": search_query,
                "sort": "date",
                "fromage": "7",  # Last 7 days
            }

            if location:
                params["l"] = location

            url = f"{self.BASE_URL}/jobs?{urlencode(params)}"
            response = await self._get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            })

            if response.status_code == 200:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")

                # Find job cards
                job_cards = soup.find_all("div", class_="job_seen_beacon")

                for card in job_cards[:limit]:
                    job = self._parse_job_card(card)
                    if job and matches_query(job.title, query, title=job.title):
                        jobs.append(job)

        except Exception as e:
            logger.error(f"Error fetching from Indeed API: {e}")

        return jobs

    def _parse_job_card(self, card) -> RawJob | None:
        """Parse a job card from Indeed HTML."""
        try:
            # Extract title
            title_elem = card.find("h2", class_="jobTitle")
            if not title_elem:
                title_elem = card.find("a", {"data-jk": True})
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract company
            company_elem = card.find("span", "companyName")
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Extract URL
            link_elem = card.find("a", id=lambda x: x and "job_" in str(x))
            url = None
            if link_elem:
                href = link_elem.get("href", "")
                url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

            # Extract location
            location_elem = card.find("div", class_="companyLocation")
            location = location_elem.get_text(strip=True) if location_elem else "Remote"

            # Extract salary
            salary_elem = card.find("span", class_="salaryText")
            salary_min, salary_max = None, None
            if salary_elem:
                salary_min, salary_max = self._parse_salary(
                    salary_elem.get_text(strip=True),
                )

            # Extract snippet/description
            snippet_elem = card.find("div", class_="job-snippet")
            description = snippet_elem.get_text(strip=True) if snippet_elem else None

            if not title:
                return None

            return RawJob(
                title=title,
                company=company,
                url=url or f"{self.BASE_URL}/jobs?q={title}",
                description=description,
                location=location,
                salary_min=salary_min,
                salary_max=salary_max,
                source=self.source_name,
                tags=self._extract_tags(title, description),
            )

        except Exception:
            return None

    def _parse_salary(self, salary_text: str) -> tuple:
        """Parse salary from text."""
        numbers = re.findall(r"[\d,]+", salary_text)
        if len(numbers) >= 2:
            return (
                int(numbers[0].replace(",", "")),
                int(numbers[1].replace(",", "")),
            )
        if len(numbers) == 1:
            val = int(numbers[0].replace(",", ""))
            return (val, val)
        return (None, None)

    def _extract_tags(self, title: str, description: str | None) -> list[str]:
        """Extract skill tags from job data."""
        tags = []
        text = f"{title} {description or ''}".lower()

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
