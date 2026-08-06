"""
TimesJobs scraper for Indian job market.

Scrapes cybersecurity jobs from TimesJobs.com (India's leading job portal).
"""

import logging
import re
from urllib.parse import urlencode

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

logger = logging.getLogger(__name__)


class TimesJobsScraper(BaseScraper):
    """Scraper for TimesJobs.com job postings."""

    BASE_URL = "https://www.timesjobs.com"

    @property
    def source_name(self) -> str:
        return "timesjobs"

    @property
    def rate_limit(self) -> int:
        return 20  # Conservative rate limit

    async def fetch(
        self,
        query: str,
        location: str | None = None,
        limit: int = 25,
    ) -> list[RawJob]:
        """Fetch jobs from TimesJobs."""
        jobs = []

        try:
            # Build search query with location
            search_query = query
            if location and location.lower() not in query.lower():
                search_query = f"{query} {location}"

            params = {
                "searchType": "personal",
                "keyword": search_query,
                "sort": "date",
                "fromAge": "7",  # Last 7 days
            }
            if location:
                params["location"] = location

            url = f"{self.BASE_URL}/job/search?{urlencode(params)}"
            response = await self._get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    ),
                    "Accept-Language": "en-IN,en;q=0.9",
                },
            )

            if response.status_code == 200:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")

                # Find job cards
                job_cards = soup.find_all("li", class_="clearfix job-bx wht-shd-bx")

                for card in job_cards[:limit]:
                    job = self._parse_job_card(card)
                    if job and matches_query(job.title, query, title=job.title):
                        jobs.append(job)

        except Exception as e:
            logger.error(f"Error fetching from TimesJobs: {e}")

        return jobs

    def _parse_job_card(self, card) -> RawJob | None:
        """Parse a job card from TimesJobs HTML."""
        try:
            # Extract title
            title_elem = card.find("h2", class_="top-heading")
            if not title_elem:
                title_elem = card.find("a", class_="top-heading")
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract company
            company_elem = card.find("h3", class_="top-comp-name")
            if not company_elem:
                company_elem = card.find("span", class_="top-comp-name")
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Extract URL
            link_elem = card.find("a", href=True)
            url = None
            if link_elem:
                href = link_elem.get("href", "")
                url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

            # Extract location
            location_elem = card.find("span", class_="top-job-icons")
            location = None
            if location_elem:
                location_text = location_elem.get_text(strip=True)
                # Extract location from icons text
                location_match = re.search(
                    r"location:?\s*([^·]+)", location_text, re.IGNORECASE
                )
                if location_match:
                    location = location_match.group(1).strip()

            # Extract experience
            experience_elem = card.find("span", class_="top-job-icons")
            if experience_elem:
                exp_text = experience_elem.get_text(strip=True)
                exp_match = re.search(
                    r"experience:?\s*([^·]+)", exp_text, re.IGNORECASE
                )
                if exp_match:
                    exp_match.group(1).strip()

            # Extract salary
            salary_elem = card.find("span", class_="top-job-icons")
            salary_min, salary_max = None, None
            if salary_elem:
                salary_text = salary_elem.get_text(strip=True)
                salary_min, salary_max = self._parse_salary(salary_text)

            # Extract description
            desc_elem = card.find("div", class_="job-desc")
            description = desc_elem.get_text(strip=True) if desc_elem else None

            # Extract posted date
            posted_elem = card.find("span", class_="top-job-icons")
            if posted_elem:
                posted_text = posted_elem.get_text(strip=True)
                posted_match = re.search(
                    r"posted:?\s*([^·]+)", posted_text, re.IGNORECASE
                )
                if posted_match:
                    posted_match.group(1).strip()

            if not title:
                return None

            return RawJob(
                title=title,
                company=company,
                url=url or f"{self.BASE_URL}/job/search?keyword={title}",
                description=description,
                location=location or "India",
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency="INR",
                source=self.source_name,
                tags=self._extract_tags(title, description),
            )

        except Exception:
            return None

    def _parse_salary(self, text: str) -> tuple:
        """Parse salary from text (INR format)."""
        # Look for salary patterns like "₹3,00,000 - ₹6,00,000 PA"
        salary_match = re.search(r"₹([\d,]+)\s*-\s*₹([\d,]+)", text)
        if salary_match:
            min_sal = int(salary_match.group(1).replace(",", ""))
            max_sal = int(salary_match.group(2).replace(",", ""))
            return (min_sal, max_sal)

        # Look for single salary
        single_match = re.search(r"₹([\d,]+)", text)
        if single_match:
            sal = int(single_match.group(1).replace(",", ""))
            return (sal, sal)

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
