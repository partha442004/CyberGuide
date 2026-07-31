"""
CrowdStrike Careers Scraper

Scrapes cybersecurity jobs from CrowdStrike's Workday-powered career page.
"""

from typing import List, Optional

from cybershield.scrapers.base import ScrapedJob, ScraperConfig
from cybershield.scrapers.companies.base_workday import BaseWorkdayScraper


__all__ = ["CrowdStrikeScraper"]


class CrowdStrikeScraper(BaseWorkdayScraper):
    """Scraper for CrowdStrike Careers (Workday ATS)."""

    CAREER_URL = "https://crowdstrike.wd1.myworkdayjobs.com/CrowdStrike"
    API_URL = "https://crowdstrike.wd1.myworkdayjobs.com/wday/cxs/crowdstrike/CrowdStrike/jobs"
    COMPANY_SLUG = "CrowdStrike"

    DEFAULT_KEYWORDS = [
        "security engineer",
        "security analyst",
        "cybersecurity",
        "information security",
        "threat intelligence",
        "incident response",
        "malware analysis",
        "threat hunting",
        "cloud security",
        "SOC",
        "penetration testing",
        "vulnerability",
        "forensics",
        "detection engineering",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="company_crowdstrike",
            base_url=self.CAREER_URL,
            rate_limit=0.33,
            max_retries=3,
        )
        super().__init__(
            company_name="CrowdStrike",
            career_url=self.CAREER_URL,
            config=config,
        )
