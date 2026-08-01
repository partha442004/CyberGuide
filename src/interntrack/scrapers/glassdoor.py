"""
Glassdoor job scraper.

Note: Glassdoor has strict anti-scraping measures. This scraper uses their
public job search functionality. Use responsibly and respect their ToS.
"""

import contextlib
import re
from urllib.parse import urlencode

from interntrack.domain.enums import JobSource
from interntrack.scrapers.base import BaseScraper, RawJob


class GlassdoorScraper(BaseScraper):
    """Scraper for Glassdoor job postings."""

    BASE_URL = "https://www.glassdoor.com"

    def __init__(self):
        super().__init__()

    @property
    def source_name(self) -> str:
        return JobSource.GLASSDOOR.value

    @property
    def rate_limit(self) -> int:
        return 10  # Very conservative rate limit

    async def fetch(
        self,
        query: str,
        location: str | None = None,
        limit: int = 25,
    ) -> list[RawJob]:
        """Fetch jobs from Glassdoor."""
        jobs = []

        try:
            params = {
                "sc.keyword": query,
                "sortBy.date_desc": "true",
            }
            if location:
                params["locT"] = ""
                params["locId"] = ""
                params["locKeyword"] = location

            url = f"{self.BASE_URL}/Job/jobs.htm?{urlencode(params)}"
            response = await self._get(url)

            if response.status_code == 200:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")

                # Find job cards
                job_cards = soup.find_all("li", class_="jobListing")

                for card in job_cards[:limit]:
                    job = self._parse_job_card(card)
                    if job:
                        jobs.append(job)

        except Exception as e:
            print(f"Error fetching from Glassdoor: {e}")

        return jobs

    def _parse_job_card(self, card) -> RawJob | None:
        """Parse a job card from Glassdoor HTML."""
        try:
            # Extract title
            title_elem = card.find("a", class_="jobCard")
            if not title_elem:
                title_elem = card.find("a", {"data-test": "job-title"})
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract company
            company_elem = card.find("div", class_="d-flex")
            if not company_elem:
                company_elem = card.find("a", {"data-test": "employer-name"})
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Extract URL
            link_elem = card.find("a", href=lambda x: x and "/job-listing/" in str(x))
            url = None
            if link_elem:
                href = link_elem.get("href", "")
                url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

            # Extract location
            location_elem = card.find("div", class_="loc")
            location = location_elem.get_text(strip=True) if location_elem else None

            # Extract salary
            salary_elem = card.find("div", class_="salary")
            salary_min, salary_max = None, None
            if salary_elem:
                salary_min, salary_max = self._parse_salary(
                    salary_elem.get_text(strip=True),
                )

            # Extract rating
            rating_elem = card.find("span", class_="rating")
            rating = None
            if rating_elem:
                with contextlib.suppress(ValueError):
                    rating = float(rating_elem.get_text(strip=True))

            # Extract snippet
            snippet_elem = card.find("div", class_="jobSnippet")
            description = snippet_elem.get_text(strip=True) if snippet_elem else None

            if not title:
                return None

            return RawJob(
                title=title,
                company=company,
                url=url or f"{self.BASE_URL}/jobs/search?q={title}",
                description=description,
                location=location,
                salary_min=salary_min,
                salary_max=salary_max,
                source=self.source_name,
                tags=self._extract_tags(title, description),
                raw_data={"rating": rating},
            )

        except Exception:
            return None

    def _parse_salary(self, salary_text: str) -> tuple:
        """Parse salary from text."""
        # Handle formats like "$80K - $120K" or "$80,000 - $120,000"
        salary_text = salary_text.replace(",", "")

        numbers = re.findall(r"[\d]+", salary_text)
        if len(numbers) >= 2:
            min_val = int(numbers[0])
            max_val = int(numbers[1])

            # Handle K notation
            if "K" in salary_text.upper():
                min_val *= 1000
                max_val *= 1000

            return (min_val, max_val)
        if len(numbers) == 1:
            val = int(numbers[0])
            if "K" in salary_text.upper():
                val *= 1000
            return (val, val)

        return (None, None)

    def _extract_tags(self, title: str, description: str | None) -> list[str]:
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
            "machine learning": "ml",
            "data science": "data-science",
            "remote": "remote",
        }

        for keyword, tag in skill_keywords.items():
            if keyword in text:
                tags.append(tag)

        return tags
