"""
LinkedIn job scraper.

Note: LinkedIn has strict anti-scraping measures. This scraper uses their
public job search page and extracts data from the HTML. Use responsibly
and respect robots.txt.
"""

import re
from datetime import datetime
from typing import List, Optional

from interntrack.domain.enums import JobSource
from interntrack.scrapers.base import BaseScraper, RawJob


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn job postings."""

    BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def __init__(self):
        super().__init__()

    @property
    def source_name(self) -> str:
        return JobSource.LINKEDIN.value

    @property
    def rate_limit(self) -> int:
        return 10  # Very conservative rate limit

    async def fetch(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 25,
    ) -> List[RawJob]:
        """Fetch jobs from LinkedIn."""
        jobs = []

        try:
            params = {
                "keywords": query,
                "start": 0,
                "sortBy": "DD",  # Sort by date
            }
            if location:
                params["location"] = location

            response = await self._get(self.BASE_URL, params=params)

            if response.status_code == 200:
                # Parse the HTML response
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")
                job_cards = soup.find_all("li", class_="result-card")

                for card in job_cards[:limit]:
                    job = self._parse_job_card(card)
                    if job:
                        jobs.append(job)

        except Exception as e:
            print(f"Error fetching from LinkedIn: {e}")

        return jobs

    def _parse_job_card(self, card) -> Optional[RawJob]:
        """Parse a job card from LinkedIn HTML."""
        try:
            # Extract title
            title_elem = card.find("h3", class_="result-card__title")
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract company
            company_elem = card.find("h4", class_="result-card__company-name")
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Extract URL
            link_elem = card.find("a", class_="result-card__full-card-link")
            url = link_elem["href"] if link_elem else None

            # Extract location
            location_elem = card.find("span", class_="job-result__location")
            location = location_elem.get_text(strip=True) if location_elem else None

            # Extract date
            date_elem = card.find("time", class_="result-card__listed-date")
            posted_at = None
            if date_elem and date_elem.get("datetime"):
                posted_at = datetime.fromisoformat(
                    date_elem["datetime"].replace("Z", "+00:00")
                )

            # Extract description
            desc_elem = card.find("p", class_="result-card__snippet")
            description = desc_elem.get_text(strip=True) if desc_elem else None

            if not title or not url:
                return None

            return RawJob(
                title=title,
                company=company,
                url=url,
                description=description,
                location=location,
                posted_at=posted_at,
                source=self.source_name,
                tags=self._extract_tags(title, description),
            )

        except Exception:
            return None

    def _extract_tags(self, title: str, description: Optional[str]) -> List[str]:
        """Extract skill tags from job data."""
        tags = []
        text = f"{title} {description or ''}".lower()

        skill_keywords = {
            "python": "python",
            "javascript": "javascript",
            "react": "react",
            "node": "nodejs",
            "java": "java",
            "sql": "sql",
            "aws": "aws",
            "docker": "docker",
            "kubernetes": "kubernetes",
            "remote": "remote",
        }

        for keyword, tag in skill_keywords.items():
            if keyword in text:
                tags.append(tag)

        return tags
