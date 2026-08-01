"""
Trend Micro Careers Scraper

Scrapes cybersecurity jobs from Trend Micro's Workday-powered career page.
Trend Micro uses the wd3 datacenter cluster for their Workday ATS.
"""

from typing import Optional

from cybershield.scrapers.base import ScraperConfig
from cybershield.scrapers.companies.base_workday import BaseWorkdayScraper

__all__ = ["TrendMicroScraper"]


class TrendMicroScraper(BaseWorkdayScraper):
    """Scraper for Trend Micro Careers (Workday ATS)."""

    CAREER_URL = "https://trendmicro.wd3.myworkdayjobs.com/External"
    API_URL = "https://trendmicro.wd3.myworkdayjobs.com/wday/cxs/trendmicro/External/jobs"
    COMPANY_SLUG = "External"

    DEFAULT_KEYWORDS = [
        "security engineer",
        "security analyst",
        "cybersecurity",
        "information security",
        "cloud security",
        "network security",
        "SOC",
        "threat intelligence",
        "incident response",
        "penetration testing",
        "vulnerability",
        "XDR",
        "Apex One",
        "Deep Security",
        "SIEM",
    ]

    def __init__(self, config: Optional[ScraperConfig] = None):
        config = config or ScraperConfig(
            name="company_trendmicro",
            base_url=self.CAREER_URL,
            rate_limit=0.33,
            max_retries=3,
        )
        super().__init__(
            company_name="Trend Micro",
            career_url=self.CAREER_URL,
            config=config,
        )
