"""
Indeed job scraper.

Note: Indeed has anti-scraping measures. This scraper uses their RSS feed
and API endpoints where available. Use responsibly.
"""

import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlencode

from interntrack.domain.enums import JobSource
from interntrack.scrapers.base import BaseScraper, RawJob


class IndeedScraper(BaseScraper):
    """Scraper for Indeed job postings."""

    BASE_URL = "https://www.indeed.com"

    def __init__(self):
        super().__init__()

    @property
    def source_name(self) -> str:
        return JobSource.INDEED.value

    @property
    def rate_limit(self) -> int:
        return 15  # Conservative rate limit

    async def fetch(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 25,
    ) -> List[RawJob]:
        """Fetch jobs from Indeed."""
        jobs = []

        try:
            # Indeed job search URL
            params = {
                "q": query,
                "sort": "date",
            }
            if location:
                params["l"] = location

            url = f"{self.BASE_URL}/jobs?{urlencode(params)}"
            response = await self._get(url)

            if response.status_code == 200:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")

                # Find job cards
                job_cards = soup.find_all("div", class_="job_seen_beacon")

                for card in job_cards[:limit]:
                    job = self._parse_job_card(card)
                    if job:
                        jobs.append(job)

        except Exception as e:
            print(f"Error fetching from Indeed: {e}")

        return jobs

    def _parse_job_card(self, card) -> Optional[RawJob]:
        """Parse a job card from Indeed HTML."""
        try:
            # Extract title
            title_elem = card.find("h2", class_="jobTitle")
            if not title_elem:
                title_elem = card.find("a", {"data-jk": True})
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract company
            company_elem = card.find("span", "companyName")
            if not company_elem:
                company_elem = card.find("span", class_="company")
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Extract URL
            link_elem = card.find("a", id=lambda x: x and "job_" in str(x))
            if not link_elem:
                link_elem = card.find("a", href=lambda x: x and "/rc/clk" in str(x))
            url = None
            if link_elem:
                href = link_elem.get("href", "")
                url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

            # Extract location
            location_elem = card.find("div", class_="companyLocation")
            location = location_elem.get_text(strip=True) if location_elem else None

            # Extract salary
            salary_elem = card.find("span", class_="salaryText")
            salary_min, salary_max = None, None
            if salary_elem:
                salary_min, salary_max = self._parse_salary(
                    salary_elem.get_text(strip=True)
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
        elif len(numbers) == 1:
            val = int(numbers[0].replace(",", ""))
            return (val, val)
        return (None, None)

    def _extract_tags(self, title: str, description: Optional[str]) -> List[str]:
        """Extract skill tags from job data."""
        tags = []
        text = f"{title} {description or ''}".lower()

        skill_keywords = {
            "python": "python",
            "javascript": "javascript",
            "react": "react",
            "java": "java",
            "sql": "sql",
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
