"""
Google Jobs scraper for broader job coverage.

Scrapes job listings from Google Search results for cybersecurity positions.
"""

import logging
import re
from typing import Any
from urllib.parse import urlencode

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

logger = logging.getLogger(__name__)


class GoogleJobsScraper(BaseScraper):
    """Scraper for Google Jobs (via search results)."""

    BASE_URL = "https://www.google.com/search"
    
    # Cybersecurity keywords for Google Jobs
    DEFAULT_KEYWORDS = [
        "cybersecurity jobs Bangalore",
        "information security jobs India",
        "SOC analyst jobs Bangalore",
        "penetration testing jobs India",
        "VAPT jobs Bangalore",
        "ethical hacking jobs India",
        "security engineer jobs Bangalore",
    ]

    @property
    def source_name(self) -> str:
        return "google_jobs"

    @property
    def rate_limit(self) -> int:
        return 30  # More conservative rate limit for Google

    async def fetch(
        self,
        query: str,
        location: str | None = None,
        limit: int = 100,
    ) -> list[RawJob]:
        """Fetch jobs from Google Search results."""
        jobs = []
        
        # Build search query with location
        search_query = query
        if location and location.lower() not in query.lower():
            search_query = f"{query} {location}"
        
        try:
            # Use Google Jobs API (via SerpAPI-style approach)
            # For now, we'll parse search results
            params = {
                "q": search_query,
                "ibp": "htl;jobs",  # Google Jobs tab
                "htichips": "date_posted:today",  # Today's jobs
            }
            
            url = f"{self.BASE_URL}?{urlencode(params)}"
            response = await self._get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            })
            
            # Parse job listings from HTML
            jobs = self._parse_search_results(response.text, query)
            
        except Exception as e:
            logger.error(f"Error fetching Google Jobs: {e}")
        
        return jobs[:limit]

    def _parse_search_results(self, html: str, query: str) -> list[RawJob]:
        """Parse job listings from Google search results HTML."""
        jobs = []
        
        # Extract job cards from Google Jobs
        # Pattern for job listings
        job_pattern = r'<div[^>]*data-ved="[^"]*"[^>]*>.*?<h3[^>]*>(.*?)</h3>.*?</div>'
        
        # Extract job titles and companies
        title_pattern = r'<h3[^>]*class="[^"]*"[^>]*>(.*?)</h3>'
        company_pattern = r'<div[^>]*class="[^"]*company[^"]*"[^>]*>(.*?)</div>'
        location_pattern = r'<div[^>]*class="[^"]*location[^"]*"[^>]*>(.*?)</div>'
        link_pattern = r'<a[^>]*href="(/url\?q=([^&"]+))[^"]*"'
        
        # Find all job-like elements
        titles = re.findall(title_pattern, html, re.DOTALL)
        companies = re.findall(company_pattern, html, re.DOTALL)
        locations = re.findall(location_pattern, html, re.DOTALL)
        links = re.findall(link_pattern, html, re.DOTALL)
        
        # Clean HTML tags
        def clean_html(text: str) -> str:
            return re.sub(r'<[^>]+>', '', text).strip()
        
        # Match titles with companies and locations
        for i, title in enumerate(titles[:20]):  # Limit to 20 jobs
            cleaned_title = clean_html(title)
            if not cleaned_title or len(cleaned_title) < 5:
                continue
            
            # Skip non-job results
            if any(skip in cleaned_title.lower() for skip in ['people also ask', 'related searches', 'recipes', 'news']):
                continue
            
            company = clean_html(companies[i]) if i < len(companies) else "Unknown"
            location = clean_html(locations[i]) if i < len(locations) else "Remote"
            url = links[i][1] if i < len(links) else ""
            
            # Decode Google redirect URL
            if url.startswith('/url?q='):
                url = url[7:].split('&')[0]
            
            if matches_query(cleaned_title, query, title=cleaned_title):
                jobs.append(RawJob(
                    title=cleaned_title,
                    company=company or "Unknown",
                    url=url,
                    location=location,
                    source="google_jobs",
                    tags=self._extract_tags(cleaned_title),
                ))
        
        return jobs

    def _extract_tags(self, text: str) -> list[str]:
        """Extract relevant tags from job title."""
        tags = []
        text_lower = text.lower()
        
        tag_keywords = {
            "cybersecurity": ["security", "cyber", "soc", "pentest", "vapt"],
            "engineering": ["engineer", "developer", "architect"],
            "management": ["manager", "lead", "director"],
            "analysis": ["analyst", "analysis", "researcher"],
        }
        
        for tag, keywords in tag_keywords.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(tag)
        
        return tags
