"""
AngelList (Wellfound) scraper for startup jobs.

Scrapes cybersecurity jobs from AngelList/Wellfound (startup job platform).
"""

import logging
import re
from urllib.parse import urlencode

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

logger = logging.getLogger(__name__)


class AngelListScraper(BaseScraper):
    """Scraper for AngelList/Wellfound job postings."""

    BASE_URL = "https://wellfound.com"

    @property
    def source_name(self) -> str:
        return "angellist"

    @property
    def rate_limit(self) -> int:
        return 15  # Conservative rate limit

    async def fetch(
        self,
        query: str,
        location: str | None = None,
        limit: int = 25,
    ) -> list[RawJob]:
        """Fetch jobs from AngelList/Wellfound."""
        jobs = []

        try:
            # Build search query with location
            search_query = query
            if location and location.lower() not in query.lower():
                search_query = f"{query} {location}"

            params = {
                "q": search_query,
                "sort": "date",
            }
            if location:
                params["location"] = location

            url = f"{self.BASE_URL}/jobs?{urlencode(params)}"
            response = await self._get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )

            if response.status_code == 200:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")

                # Find job cards
                job_cards = soup.find_all("div", class_="job-listing")

                for card in job_cards[:limit]:
                    job = self._parse_job_card(card)
                    if job and matches_query(job.title, query, title=job.title):
                        jobs.append(job)

        except Exception as e:
            logger.error(f"Error fetching from AngelList: {e}")

        return jobs

    def _parse_job_card(self, card) -> RawJob | None:
        """Parse a job card from AngelList HTML."""
        try:
            # Extract title
            title_elem = card.find("h2", class_="job-title")
            if not title_elem:
                title_elem = card.find("a", class_="job-link")
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract company
            company_elem = card.find("span", class_="company-name")
            if not company_elem:
                company_elem = card.find("div", class_="company")
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Extract URL
            link_elem = card.find("a", href=True)
            url = None
            if link_elem:
                href = link_elem.get("href", "")
                url = (
                    href if href.startswith("http") else f"https://wellfound.com{href}"
                )

            # Extract location
            location_elem = card.find("span", class_="location")
            location = location_elem.get_text(strip=True) if location_elem else "Remote"

            # Extract salary
            salary_elem = card.find("span", class_="salary")
            salary_min, salary_max = None, None
            if salary_elem:
                salary_min, salary_max = self._parse_salary(
                    salary_elem.get_text(strip=True)
                )

            # Extract skills
            skills_elem = card.find_all("span", class_="skill")
            skills = (
                [s.get_text(strip=True) for s in skills_elem] if skills_elem else []
            )

            # Extract company size
            size_elem = card.find("span", class_="company-size")
            company_size = size_elem.get_text(strip=True) if size_elem else None

            if not title:
                return None

            return RawJob(
                title=title,
                company=company,
                url=url or f"https://wellfound.com/jobs?q={title}",
                location=location,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency="USD",
                source=self.source_name,
                tags=skills[:10],
                raw_data={"company_size": company_size},
            )

        except Exception:
            return None

    def _parse_salary(self, text: str) -> tuple:
        """Parse salary from text."""
        # Remove currency symbols and parse
        numbers = re.findall(r"[\d,]+", text.replace("$", "").replace("k", "000"))
        if len(numbers) >= 2:
            return (
                int(numbers[0].replace(",", "")),
                int(numbers[1].replace(",", "")),
            )
        if len(numbers) == 1:
            val = int(numbers[0].replace(",", ""))
            return (val, val)
        return (None, None)
