"""
Glassdoor India scraper for Indian job market.

Scrapes cybersecurity jobs from Glassdoor India (glassdoor.co.in).
"""

import logging
import re
from urllib.parse import urlencode

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

logger = logging.getLogger(__name__)


class GlassdoorIndiaScraper(BaseScraper):
    """Scraper for Glassdoor India job postings."""

    BASE_URL = "https://www.glassdoor.co.in"

    @property
    def source_name(self) -> str:
        return "glassdoor_india"

    @property
    def rate_limit(self) -> int:
        return 10  # Very conservative rate limit

    async def fetch(
        self,
        query: str,
        location: str | None = None,
        limit: int = 25,
    ) -> list[RawJob]:
        """Fetch jobs from Glassdoor India."""
        jobs = []

        try:
            # Build search query with India location
            search_query = query
            if location and location.lower() not in query.lower():
                search_query = f"{query} {location}"
            elif "india" not in search_query.lower():
                search_query = f"{query} India"

            params = {
                "sc.keyword": search_query,
                "sortBy.date_desc": "true",
                "locT": "",
                "locId": "",
                "locKeyword": location or "India",
            }

            url = f"{self.BASE_URL}/Job/jobs.htm?{urlencode(params)}"
            response = await self._get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-IN,en;q=0.9",
            })

            if response.status_code == 200:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")

                # Find job cards
                job_cards = soup.find_all("li", class_="JobsList_jobListItem__wjTHv")

                for card in job_cards[:limit]:
                    job = self._parse_job_card(card)
                    if job and matches_query(job.title, query, title=job.title):
                        jobs.append(job)

        except Exception as e:
            logger.error(f"Error fetching from Glassdoor India: {e}")

        return jobs

    def _parse_job_card(self, card) -> RawJob | None:
        """Parse a job card from Glassdoor India HTML."""
        try:
            # Extract title
            title_elem = card.find("a", class_="JobCard_jobTitle__GLyJ1")
            if not title_elem:
                title_elem = card.find("h2", class_="JobCard_jobTitle__GLyJ1")
            title = title_elem.get_text(strip=True) if title_elem else None

            # Extract company
            company_elem = card.find("span", class_="EmployerProfile_compactEmployerName__LE242")
            if not company_elem:
                company_elem = card.find("div", class_="EmployerProfile_employerInfo__GaPbq")
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Extract URL
            link_elem = card.find("a", href=True)
            url = None
            if link_elem:
                href = link_elem.get("href", "")
                url = href if href.startswith("http") else f"https://www.glassdoor.co.in{href}"

            # Extract location
            location_elem = card.find("div", class_="JobCard_jobLocation__bq6iT")
            location = location_elem.get_text(strip=True) if location_elem else "India"

            # Extract salary
            salary_elem = card.find("div", class_="JobCard_salaryEstimate__arV5J")
            salary_min, salary_max = None, None
            if salary_elem:
                salary_min, salary_max = self._parse_salary(salary_elem.get_text(strip=True))

            # Extract rating
            rating_elem = card.find("div", class_="EmployerProfile_rating__o_dhJ")
            rating = None
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                try:
                    rating = float(rating_text.replace("/5", "").strip())
                except ValueError:
                    pass

            if not title:
                return None

            return RawJob(
                title=title,
                company=company,
                url=url or f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={title}",
                location=location,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency="INR",
                source=self.source_name,
                tags=self._extract_tags(title),
                raw_data={"rating": rating},
            )

        except Exception:
            return None

    def _parse_salary(self, text: str) -> tuple:
        """Parse salary from text (INR format)."""
        # Look for salary patterns like "₹3,00,000 - ₹6,00,000"
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
