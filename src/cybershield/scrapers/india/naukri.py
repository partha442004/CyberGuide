"""
Naukri Scraper

Scrapes cybersecurity jobs from Naukri.com (India's largest job portal).
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig

logger = logging.getLogger(__name__)


class NaukriScraper(BaseScraper):
    """Scraper for Naukri.com."""

    BASE_URL = "https://www.naukri.com"
    API_URL = "https://www.naukri.com/jobapi/v3/search"

    # Cybersecurity keywords for Naukri
    DEFAULT_KEYWORDS = [
        "cyber security",
        "information security",
        "SOC analyst",
        "security engineer",
        "penetration testing",
        "VAPT",
        "ethical hacking",
        "threat intelligence",
        "security analyst",
        "network security",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="naukri",
            base_url=self.BASE_URL,
            rate_limit=0.5,  # 1 request per 2 seconds
            max_retries=3,
            timeout=30.0,
        )
        super().__init__(config)

    def _build_search_url(self, keyword: str, page: int = 1) -> str:
        """Build search URL for Naukri API."""
        params = {
            "noOfResults": 100,
            "urlType": "search_by_key_loc",
            "searchType": "adv",
            "keyword": keyword,
            "location": "India",
            "pageNum": page,
            "sort": "date",  # Sort by date
        }
        return f"{self.API_URL}?{urlencode(params)}"

    def _parse_job_data(self, job_data: Dict[str, Any]) -> ScrapedJob:
        """Parse individual job data from Naukri API response."""
        job = ScrapedJob()

        # Basic info
        job.title = job_data.get("title", "").strip()
        job.company_name = job_data.get("companyName", "").strip()
        job.url = job_data.get("jobUrl", "")
        job.source = "naukri"
        job.source_id = str(job_data.get("jobId", ""))

        # Location
        location_parts = job_data.get("placeholders", [])
        for part in location_parts:
            if part.get("type") == "location":
                job.location = part.get("label", "")
                break

        if job.location:
            job.country = "India"
            # Try to extract city from location
            location_lower = job.location.lower()
            major_cities = [
                "mumbai",
                "delhi",
                "bangalore",
                "hyderabad",
                "pune",
                "chennai",
                "kolkata",
                "ahmedabad",
                "jaipur",
                "lucknow",
            ]
            for city in major_cities:
                if city in location_lower:
                    job.city = city.title()
                    break

        # Salary
        salary_info = job_data.get("salaryDetails", {})
        if salary_info:
            salary_text = salary_info.get("label", "")
            # Parse salary text (e.g., "₹3,00,000 - ₹6,00,000 PA")
            try:
                # Remove currency symbols and parse
                salary_text = (
                    salary_text.replace("₹", "").replace(",", "").replace("PA", "").strip()
                )
                if "-" in salary_text:
                    parts = salary_text.split("-")
                    if len(parts) == 2:
                        job.salary_min = float(parts[0].strip())
                        job.salary_max = float(parts[1].strip())
                        job.salary_currency = "INR"
            except (ValueError, IndexError):
                pass

        # Experience
        experience_info = job_data.get("experienceDetails", {})
        if experience_info:
            exp_label = experience_info.get("label", "")
            job.experience_level = self._parse_experience_level(exp_label)

        # Skills
        skills = job_data.get("tagsAndSkills", [])
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",")]
        job.required_skills = skills

        # Job type
        job_type = job_data.get("jobType", "")
        job.job_type = self._parse_job_type(job_type)

        # Remote work
        work_mode = job_data.get("workMode", "")
        if "remote" in work_mode.lower():
            job.is_remote = True
            job.is_onsite = False
        elif "hybrid" in work_mode.lower():
            job.is_hybrid = True

        # Posting date
        posted_date = job_data.get("postedDate", "")
        job.posting_date = self._parse_date(posted_date)

        # Description
        job.description = job_data.get("jobDescription", "")

        # Skills from description
        if job.description:
            desc_skills = self._extract_skills(job.description)
            job.required_skills = list(set(job.required_skills + desc_skills))

        return job

    def _parse_experience_level(self, exp_text: str) -> str:
        """Parse experience level from text."""
        exp_lower = exp_text.lower()
        if "fresher" in exp_lower:
            return "fresher"
        elif "intern" in exp_lower:
            return "intern"
        elif "junior" in exp_lower or "0-2" in exp_lower:
            return "junior"
        elif "mid" in exp_lower or "3-5" in exp_lower:
            return "mid"
        elif "senior" in exp_lower or "5+" in exp_lower:
            return "senior"
        elif "0" in exp_lower:
            return "fresher"
        return "entry"

    def _parse_job_type(self, job_type: str) -> str:
        """Parse job type from text."""
        job_type_lower = job_type.lower()
        if "intern" in job_type_lower:
            return "internship"
        elif "contract" in job_type_lower:
            return "contract"
        elif "part time" in job_type_lower:
            return "part_time"
        return "full_time"

    async def scrape(
        self,
        keywords: Optional[List[str]] = None,
        max_pages: int = 5,
        **kwargs,
    ) -> List[ScrapedJob]:
        """Scrape jobs from Naukri."""
        keywords = keywords or self.DEFAULT_KEYWORDS
        all_jobs: List[ScrapedJob] = []
        seen_ids = set()

        for keyword in keywords:
            logger.info(f"Scraping Naukri for keyword: {keyword}")

            for page in range(1, max_pages + 1):
                try:
                    url = self._build_search_url(keyword, page)
                    response = await self._fetch(url)
                    data = response.json()

                    jobs_data = data.get("jobData", [])
                    if not jobs_data:
                        break

                    for job_data in jobs_data:
                        job = self._parse_job_data(job_data)
                        if job.source_id and job.source_id not in seen_ids:
                            seen_ids.add(job.source_id)
                            all_jobs.append(job)

                    # Check if there are more pages
                    total_results = data.get("totalCount", 0)
                    if page * 100 >= total_results:
                        break

                except Exception as e:
                    logger.error(f"Error scraping Naukri page {page} for '{keyword}': {e}")
                    break

        logger.info(f"Naukri scraper found {len(all_jobs)} jobs")
        return all_jobs
