"""
McAfee Careers Scraper

Scrapes cybersecurity jobs from McAfee's Workday-powered career page.
"""

from typing import List, Optional

from cybershield.scrapers.base import ScrapedJob, ScraperConfig
from cybershield.scrapers.companies.base_workday import BaseWorkdayScraper


__all__ = ["McAfeeScraper"]


class McAfeeScraper(BaseWorkdayScraper):
    """Scraper for McAfee Careers (Workday ATS)."""

    CAREER_URL = "https://mcafee.wd1.myworkdayjobs.com/External"
    API_URL = "https://mcafee.wd1.myworkdayjobs.com/wday/cxs/mcafee/External/jobs"
    COMPANY_SLUG = "External"

    DEFAULT_KEYWORDS = [
        "security engineer",
        "security analyst",
        "cybersecurity",
        "information security",
        "endpoint security",
        "threat intelligence",
        "incident response",
        "malware analysis",
        "SOC",
        "penetration testing",
        "vulnerability",
        "firewall",
        "cloud security",
        "SIEM",
        "network security",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="company_mcafee",
            base_url=self.CAREER_URL,
            rate_limit=0.33,
            max_retries=3,
        )
        super().__init__(
            company_name="McAfee",
            career_url=self.CAREER_URL,
            config=config,
        )
