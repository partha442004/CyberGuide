"""
Base Workday Scraper

Shared base class for companies using Workday ATS.
Workday uses a POST JSON API endpoint for job search.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from cybershield.scrapers.base import ScrapedJob
from cybershield.scrapers.companies.base_company import BaseCompanyScraper

logger = logging.getLogger(__name__)


class BaseWorkdayScraper(BaseCompanyScraper):
    """
    Base class for Workday ATS-based company scrapers.

    Subclasses only need to define:
    - CAREER_URL: Career page URL
    - API_URL: Workday API endpoint
    - DEFAULT_KEYWORDS: List of search keywords
    """

    CAREER_URL: str = ""
    API_URL: str = ""
    COMPANY_SLUG: str = ""  # Company slug in Workday URL, e.g., "CrowdStrike", "Careers"
    DEFAULT_KEYWORDS: List[str] = []

    def _build_search_payload(self, keyword: str, page: int = 0, limit: int = 20) -> Dict[str, Any]:
        """Build Workday search payload."""
        return {
            "appliedFacets": {},
            "limit": limit,
            "offset": page * limit,
            "searchText": keyword,
        }

    def _parse_job_data(self, job_data: Dict[str, Any]) -> ScrapedJob:
        """Parse job data from Workday API response."""
        job = ScrapedJob()

        job.title = job_data.get("title", "").strip()
        job.company_name = self.company_name
        job.source = f"company_{self.company_name.lower().replace(' ', '_')}"

        # Workday uses externalPath for job ID
        external_path = job_data.get("externalPath", "")
        job.source_id = (
            external_path.split("/")[-1] if external_path else str(job_data.get("postedOn", ""))
        )

        # URL
        if external_path:
            hostname = self.CAREER_URL.split("//")[1].split("/")[0]
            slug = self.COMPANY_SLUG or self.company_name
            job.url = f"https://{hostname}/en-US/{slug}{external_path}"
        else:
            job.url = self.career_url

        # Location
        locations_text = job_data.get("locationsText", "")
        if locations_text:
            job.location = locations_text.strip()
            self._detect_country(job, locations_text)
        else:
            job.country = "Remote"

        # Job type
        time_type = job_data.get("timeType", "")
        job.job_type = "part_time" if "part" in time_type.lower() else "full_time"

        # Experience level
        job.experience_level = "mid"

        # Posting date
        posted = job_data.get("postedOn", "")
        job.posting_date = self._parse_date(posted)

        # Description
        job.description = job_data.get("jobDescription", "")

        # Skills - extract from title and description
        all_text = f"{job.title} {job.description}"
        job.required_skills = self._extract_skills(all_text)

        job = self._tag_job(job)
        return job

    def _detect_country(self, job: ScrapedJob, locations_text: str) -> None:
        """Detect country from location text. Override for company-specific locations."""
        loc_lower = locations_text.lower()
        if (
            "united states" in loc_lower
            or "usa" in loc_lower
            or "(us)" in loc_lower
            or "us)" in loc_lower
        ):
            job.country = "USA"
        elif "india" in loc_lower or "bangalore" in loc_lower or "hyderabad" in loc_lower:
            job.country = "India"
        elif "remote" in loc_lower:
            job.is_remote = True
            job.country = "Remote"
        elif "uk" in loc_lower or "london" in loc_lower:
            job.country = "UK"
        elif "germany" in loc_lower or "berlin" in loc_lower:
            job.country = "Germany"
        elif "israel" in loc_lower or "tel aviv" in loc_lower:
            job.country = "Israel"
        elif "singapore" in loc_lower:
            job.country = "Singapore"
        elif "australia" in loc_lower or "sydney" in loc_lower:
            job.country = "Australia"
        elif "canada" in loc_lower or "toronto" in loc_lower or "vancouver" in loc_lower:
            job.country = "Canada"
        else:
            job.country = "Global"

    async def _fetch_workday(
        self, keyword: str, page: int = 0, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Fetch jobs from Workday API for a single keyword and page."""
        payload = self._build_search_payload(keyword, page, limit)
        await self._rate_limit_wait()
        merged_headers = {
            **self.config.headers,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(
            timeout=self.config.timeout,
            follow_redirects=True,
        ) as client:
            response = await client.post(
                self.API_URL,
                json=payload,
                headers=merged_headers,
            )
            response.raise_for_status()
            self._request_count += 1
        data = response.json()
        postings = data.get("jobPostings", [])
        return [p for p in postings if isinstance(p, dict)]

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        max_pages: int = 3,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape security jobs from Workday ATS."""
        keywords = keywords or self.DEFAULT_KEYWORDS
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        for keyword in keywords:
            logger.info(f"Scraping {self.company_name} for: {keyword}")

            for page in range(max_pages):
                try:
                    job_postings = await self._fetch_workday(keyword, page)
                    if not job_postings:
                        break

                    for job_data in job_postings:
                        job = self._parse_job_data(job_data)
                        if job.source_id and job.source_id not in seen_ids:
                            if self._is_security_role(job):
                                seen_ids.add(job.source_id)
                                all_jobs.append(job)

                except Exception as e:
                    logger.error(f"Error scraping {self.company_name} for '{keyword}': {e}")
                    break

        logger.info(f"{self.company_name} scraper found {len(all_jobs)} security jobs")
        return all_jobs
