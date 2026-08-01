"""
Fortinet Careers Scraper

Scrapes cybersecurity jobs from Fortinet's Workday-powered career page.
"""

from typing import Optional

from cybershield.scrapers.base import ScraperConfig
from cybershield.scrapers.companies.base_workday import BaseWorkdayScraper

__all__ = ["FortinetScraper"]


class FortinetScraper(BaseWorkdayScraper):
    """Scraper for Fortinet Careers (Workday ATS)."""

    CAREER_URL = "https://www.fortinet.com/careers"
    API_URL = "https://fortinet.wd1.myworkdayjobs.com/wday/cxs/fortinet/Fortinet/jobs"
    COMPANY_SLUG = "Fortinet"

    DEFAULT_KEYWORDS = [
        "security engineer",
        "security analyst",
        "cybersecurity",
        "information security",
        "network security",
        "cloud security",
        "SOC",
        "threat intelligence",
        "incident response",
        "penetration testing",
        "vulnerability",
        "FortiGate",
        "FortiGuard",
        "SIEM",
        "firewall",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="company_fortinet",
            base_url=self.CAREER_URL,
            rate_limit=0.33,
            max_retries=3,
        )
        super().__init__(
            company_name="Fortinet",
            career_url=self.CAREER_URL,
            config=config,
        )
