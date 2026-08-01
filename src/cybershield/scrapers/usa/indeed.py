"""
Indeed Scraper

Scrapes cybersecurity jobs from Indeed.com (USA).
"""

import logging
from typing import Any, List, Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig

logger = logging.getLogger(__name__)


class IndeedScraper(BaseScraper):
    """Scraper for Indeed.com (USA)."""

    BASE_URL = "https://www.indeed.com"

    DEFAULT_KEYWORDS = [
        "cyber security",
        "information security",
        "SOC analyst",
        "security engineer",
        "penetration testing",
        "threat intelligence",
        "security analyst",
        "network security",
        "cloud security",
        "DevSecOps",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="indeed",
            base_url=self.BASE_URL,
            rate_limit=0.33,  # 1 request per 3 seconds
            max_retries=3,
        )
        super().__init__(config)

    def _build_search_url(self, keyword: str, location: str = "United States", start: int = 0) -> str:
        """Build search URL for Indeed."""
        params = {
            "q": keyword,
            "l": location,
            "start": start,
            "sort": "date",
        }
        return f"{self.BASE_URL}/jobs?{urlencode(params)}"

    def _parse_job_card(self, card: BeautifulSoup) -> Optional[ScrapedJob]:
        """Parse individual job card HTML."""
        try:
            job = ScrapedJob()

            # Title
            title_elem = card.select_one("h2.jobTitle a, a.jcs-JobTitle")
            if not title_elem:
                return None
            job.title = title_elem.get_text(strip=True)
            job.url = self._normalize_url(title_elem.get("href", ""))
            if job.url and not job.url.startswith("http"):
                job.url = self.BASE_URL + job.url

            # Company
            company_elem = card.select_one("span[data-testid='company-name'], span.companyName")
            job.company_name = company_elem.get_text(strip=True) if company_elem else ""

            # Location
            location_elem = card.select_one("div[data-testid='text-location'], div.companyLocation")
            job.location = location_elem.get_text(strip=True) if location_elem else ""
            job.country = "USA"

            # Salary
            salary_elem = card.select_one("div.salary-snippet-container, div[data-testid='attribute_snippet_testid']")
            if salary_elem:
                salary_text = salary_elem.get_text(strip=True)
                job.raw_data["salary_text"] = salary_text
                # Try to parse salary
                try:
                    salary_clean = salary_text.replace("$", "").replace(",", "").replace(" a year", "").replace(" an hour", "").strip()
                    if "a year" in salary_text:
                        job.salary_currency = "USD"
                    if "-" in salary_clean:
                        parts = salary_clean.split("-")
                        job.salary_min = float(parts[0].strip())
                        job.salary_max = float(parts[1].strip())
                    else:
                        job.salary_min = float(salary_clean)
                        job.salary_max = job.salary_min
                except (ValueError, IndexError):
                    pass

            # Job type
            job_type_elem = card.select_one("div.jobSnip")
            if job_type_elem:
                job_type_text = job_type_elem.get_text(strip=True).lower()
                if "contract" in job_type_text:
                    job.job_type = "contract"
                elif "part-time" in job_type_text:
                    job.job_type = "part_time"
                elif "internship" in job_type_text:
                    job.job_type = "internship"
                else:
                    job.job_type = "full_time"
            else:
                job.job_type = "full_time"

            # Source
            job.source = "indeed"
            job.source_id = self._extract_job_id(job.url)

            # Remote
            if job.location and "remote" in job.location.lower():
                job.is_remote = True
                job.is_onsite = False

            # Posted date
            date_elem = card.select_one("span.date")
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                # Indeed uses relative dates like "Posted 3 days ago"
                job.raw_data["posted_relative"] = date_text
                job.posting_date = self._parse_relative_date(date_text)

            # Extract skills from title and any snippet
            skills_text = f"{job.title} {job.description or ''}"
            job.required_skills = self._extract_skills(skills_text)

            return job

        except Exception as e:
            logger.error(f"Error parsing Indeed job card: {e}")
            return None

    def _extract_job_id(self, url: str) -> str:
        """Extract job ID from Indeed URL."""
        if not url:
            return ""
        # Indeed URLs typically have job IDs like /jk=abc123 or /viewjob?jk=abc123
        import re
        match = re.search(r'jk=([a-f0-9]+)', url)
        if match:
            return match.group(1)
        match = re.search(r'/viewjob\?.*?jk=([^&]+)', url)
        if match:
            return match.group(1)
        return url.split("/")[-1] if "/" in url else url

    def _parse_relative_date(self, text: str) -> Optional[Any]:
        """Parse relative date like 'Posted 3 days ago'."""
        import re
        from datetime import datetime, timedelta, timezone

        text = text.lower().replace("posted", "").strip()

        if "just posted" in text or "today" in text:
            return datetime.now(timezone.utc)
        elif "yesterday" in text:
            return datetime.now(timezone.utc) - timedelta(days=1)

        # Try to extract number of days/hours
        match = re.search(r'(\d+)\s*(hour|day|week|month)s?\s*ago', text)
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            if unit == "hour":
                return datetime.now(timezone.utc) - timedelta(hours=num)
            elif unit == "day":
                return datetime.now(timezone.utc) - timedelta(days=num)
            elif unit == "week":
                return datetime.now(timezone.utc) - timedelta(weeks=num)
            elif unit == "month":
                return datetime.now(timezone.utc) - timedelta(days=num * 30)

        return None

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        max_pages: int = 5,
        location: str = "United States",
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape jobs from Indeed."""
        keywords = keywords or self.DEFAULT_KEYWORDS
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        for keyword in keywords:
            logger.info(f"Scraping Indeed for keyword: {keyword}")

            for page in range(max_pages):
                try:
                    start = page * 10
                    url = self._build_search_url(keyword, location, start)
                    response = await self._fetch(url)

                    soup = BeautifulSoup(response.text, "html.parser")
                    cards = soup.select("div.job_seen_beacon, div.jobsearch-ResultsList div.result")

                    if not cards:
                        break

                    for card in cards:
                        job = self._parse_job_card(card)
                        if job and job.source_id and job.source_id not in seen_ids:
                            seen_ids.add(job.source_id)
                            all_jobs.append(job)

                except Exception as e:
                    logger.error(f"Error scraping Indeed page {page} for '{keyword}': {e}")
                    break

        logger.info(f"Indeed scraper found {len(all_jobs)} jobs")
        return all_jobs
