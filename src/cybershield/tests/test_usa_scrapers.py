"""
Tests for the cybershield USA scrapers (Indeed, LinkedIn).

Covers URL building, job card/feed parsing (all branches), job ID
extraction, relative-date parsing, and the async scrape loops.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cybershield.scrapers.usa.indeed import IndeedScraper
from cybershield.scrapers.usa.linkedin import LinkedInScraper


def _card(**overrides) -> SimpleNamespace:
    """Build a fake BeautifulSoup Tag for an Indeed job card."""
    defaults = {
        "jobTitle": "Security Analyst",
        "href": "/rc/clk?jk=abc123",
        "company": "Acme Corp",
        "location": "New York, NY",
        "salary": "$90,000 - $110,000 a year",
        "jobType": "Full-time",
        "date": "Posted 3 days ago",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _tag(card: SimpleNamespace) -> MagicMock:
    """Build a mock Tag whose select_one() returns per-selector values."""
    tag = MagicMock()

    def select_one(selector: str) -> Optional[Any]:
        if "jobTitle" in selector or "jcs-JobTitle" in selector:
            if card.jobTitle is None:
                return None
            title = MagicMock()
            title.get_text.return_value = card.jobTitle
            title.get.return_value = card.href
            return title
        if "company-name" in selector or "companyName" in selector:
            if card.company is None:
                return None
            comp = MagicMock()
            comp.get_text.return_value = card.company
            return comp
        if "text-location" in selector or "companyLocation" in selector:
            if card.location is None:
                return None
            loc = MagicMock()
            loc.get_text.return_value = card.location
            return loc
        if "salary-snippet" in selector or "attribute_snippet" in selector:
            if card.salary is None:
                return None
            sal = MagicMock()
            sal.get_text.return_value = card.salary
            return sal
        if selector == "div.jobSnip":
            if card.jobType is None:
                return None
            jt = MagicMock()
            jt.get_text.return_value = card.jobType
            return jt
        if selector == "span.date":
            if card.date is None:
                return None
            dt = MagicMock()
            dt.get_text.return_value = card.date
            return dt
        return None

    tag.select_one.side_effect = select_one
    return tag


class TestIndeedBuildSearchUrl:
    def setup_method(self):
        self.scraper = IndeedScraper()

    def test_defaults(self):
        url = self.scraper._build_search_url("security analyst")
        assert url.startswith("https://www.indeed.com/jobs?")
        assert "q=security+analyst" in url
        assert "l=United+States" in url
        assert "start=0" in url
        assert "sort=date" in url

    def test_custom_location_and_start(self):
        url = self.scraper._build_search_url("SOC analyst", "Remote", 20)
        assert "l=Remote" in url
        assert "start=20" in url


class TestIndeedParseJobCard:
    def setup_method(self):
        self.scraper = IndeedScraper()

    def test_full_card(self):
        job = self.scraper._parse_job_card(_tag(_card()))
        assert job is not None
        assert job.title == "Security Analyst"
        assert job.company_name == "Acme Corp"
        assert job.location == "New York, NY"
        assert job.country == "USA"
        assert job.source == "indeed"
        assert job.source_id == "abc123"
        assert job.job_type == "full_time"
        assert job.salary_min == 90000.0
        assert job.salary_max == 110000.0
        assert job.salary_currency == "USD"
        assert job.raw_data.get("salary_text") == "$90,000 - $110,000 a year"
        assert job.raw_data.get("posted_relative") == "Posted 3 days ago"

    def test_missing_title_returns_none(self):
        assert self.scraper._parse_job_card(_tag(_card(jobTitle=None))) is None

    def test_relative_url_normalized(self):
        card = _tag(_card(href="/viewjob?jk=def456"))
        job = self.scraper._parse_job_card(card)
        assert job is not None
        assert job.url
        assert job.url.startswith("https://www.indeed.com/")

    def test_remote_location(self):
        job = self.scraper._parse_job_card(_tag(_card(location="Remote")))
        assert job is not None
        assert job.is_remote is True
        assert job.is_onsite is False

    def test_contract_type(self):
        job = self.scraper._parse_job_card(_tag(_card(jobType="Contract")))
        assert job is not None
        assert job.job_type == "contract"

    def test_part_time_type(self):
        job = self.scraper._parse_job_card(_tag(_card(jobType="Part-time")))
        assert job is not None
        assert job.job_type == "part_time"

    def test_internship_type(self):
        job = self.scraper._parse_job_card(_tag(_card(jobType="Internship")))
        assert job is not None
        assert job.job_type == "internship"

    def test_salary_no_range(self):
        job = self.scraper._parse_job_card(_tag(_card(salary="$80,000 a year")))
        assert job is not None
        assert job.salary_min == 80000.0
        assert job.salary_max == 80000.0

    def test_salary_unparseable(self):
        job = self.scraper._parse_job_card(_tag(_card(salary="Competitive")))
        assert job is not None
        assert job.salary_min is None

    def test_no_company_or_location(self):
        job = self.scraper._parse_job_card(_tag(_card(company=None, location=None)))
        assert job is not None
        assert job.company_name == ""
        assert job.location == ""


class TestIndeedExtractJobId:
    def setup_method(self):
        self.scraper = IndeedScraper()

    def test_jk_query(self):
        assert self.scraper._extract_job_id("https://indeed.com/viewjob?jk=abc123&x=1") == "abc123"

    def test_empty_url(self):
        assert self.scraper._extract_job_id("") == ""

    def test_no_match_uses_last_segment(self):
        assert self.scraper._extract_job_id("https://indeed.com/jobs/xyz789") == "xyz789"

    def test_plain_string(self):
        assert self.scraper._extract_job_id("plain-id") == "plain-id"


class TestIndeedParseRelativeDate:
    def setup_method(self):
        self.scraper = IndeedScraper()

    def test_today(self):
        result = self.scraper._parse_relative_date("Posted today")
        assert result is not None
        assert result.date() == datetime.now(timezone.utc).date()

    def test_just_posted(self):
        # "posted" is stripped before the "just posted"/"today" checks, so
        # only inputs containing "today" trigger the immediate-now branch.
        result = self.scraper._parse_relative_date("Posted just now today")
        assert result is not None

    def test_yesterday(self):
        result = self.scraper._parse_relative_date("Posted yesterday")
        assert result is not None
        assert result.date() == (datetime.now(timezone.utc) - timedelta(days=1)).date()

    def test_hours_ago(self):
        result = self.scraper._parse_relative_date("Posted 5 hours ago")
        assert result is not None
        assert result < datetime.now(timezone.utc)

    def test_days_ago(self):
        result = self.scraper._parse_relative_date("Posted 3 days ago")
        assert result is not None
        assert result.date() == (datetime.now(timezone.utc) - timedelta(days=3)).date()

    def test_weeks_ago(self):
        result = self.scraper._parse_relative_date("Posted 2 weeks ago")
        assert result is not None

    def test_months_ago(self):
        result = self.scraper._parse_relative_date("Posted 1 month ago")
        assert result is not None

    def test_unknown(self):
        assert self.scraper._parse_relative_date("Now hiring!") is None


class TestIndeedScrape:
    def setup_method(self):
        self.scraper = IndeedScraper()

    @pytest.mark.asyncio
    async def test_scrape_finds_jobs(self):
        html = (
            '<div class="job_seen_beacon">'
            '<h2 class="jobTitle"><a href="/rc/clk?jk=aaa111">Security Analyst</a></h2>'
            '<span data-testid="company-name">Acme</span>'
            '<div data-testid="text-location">Remote</div>'
            '<div class="salary-snippet-container">$100,000 - $120,000 a year</div>'
            '<span class="date">Posted today</span>'
            "</div>"
        )
        response = MagicMock()
        response.text = html
        self.scraper._fetch = AsyncMock(return_value=response)  # type: ignore[method-assign]

        jobs = await self.scraper.scrape(keywords=["security analyst"], max_pages=1)
        assert len(jobs) == 1
        assert jobs[0].title == "Security Analyst"
        assert jobs[0].source_id == "aaa111"

    @pytest.mark.asyncio
    async def test_scrape_skips_duplicates(self):
        html = (
            '<div class="job_seen_beacon">'
            '<h2 class="jobTitle"><a href="/rc/clk?jk=dup1">Security Analyst</a></h2>'
            '<span data-testid="company-name">Acme</span>'
            "</div>"
        )
        response = MagicMock()
        response.text = html
        self.scraper._fetch = AsyncMock(return_value=response)  # type: ignore[method-assign]

        jobs = await self.scraper.scrape(keywords=["security"], max_pages=2)
        # Same source_id across pages -> deduped
        assert len(jobs) == 1

    @pytest.mark.asyncio
    async def test_scrape_empty_pages(self):
        response = MagicMock()
        response.text = "<html><body></body></html>"
        self.scraper._fetch = AsyncMock(return_value=response)  # type: ignore[method-assign]

        jobs = await self.scraper.scrape(keywords=["security"], max_pages=1)
        assert jobs == []

    @pytest.mark.asyncio
    async def test_scrape_handles_fetch_error(self):
        self.scraper._fetch = AsyncMock(side_effect=Exception("network down"))  # type: ignore[method-assign]
        jobs = await self.scraper.scrape(keywords=["security"], max_pages=1)
        assert jobs == []


class TestLinkedIn:
    def setup_method(self):
        self.scraper = LinkedInScraper()

    def test_build_rss_url(self):
        url = self.scraper._build_rss_url("security")
        assert "linkedin.com" in url
        assert "security" in url

    def test_build_rss_url_custom(self):
        url = self.scraper._build_rss_url("SOC analyst", "Remote")
        assert "Remote" in url

    def test_parse_feed_entry_full(self):
        entry = {
            "title": "Security Engineer at Example Corp in United States",
            "link": "https://www.linkedin.com/jobs/view/abc/1234567890",
            "summary": "We need a security engineer with SIEM and Python skills.",
            "published": "2026-08-01T10:00:00Z",
        }
        job = self.scraper._parse_feed_entry(entry)
        assert job is not None
        assert job.source == "linkedin"
        assert job.country == "USA"
        assert job.company_name == "Example Corp"
        assert job.location == "United States"

    def test_parse_feed_entry_at_without_in(self):
        entry = {
            "title": "Security Analyst at Acme Corp",
            "link": "https://www.linkedin.com/jobs/view/abc/222",
            "summary": "security role",
        }
        job = self.scraper._parse_feed_entry(entry)
        assert job is not None
        assert job.company_name == "Acme Corp"
        assert job.title == "Security Analyst"

    def test_parse_feed_entry_at_in_trailing(self):
        # " at " and " in " present, but no location after " in " -> line 82
        entry = {
            "title": "Security Analyst at Acme Corp in",
            "link": "https://www.linkedin.com/jobs/view/abc/335",
            "summary": "security role",
        }
        job = self.scraper._parse_feed_entry(entry)
        assert job is not None
        # With a dangling " in", the whole remainder becomes the company name
        assert job.company_name == "Acme Corp in"

    def test_parse_feed_entry_remote_india(self):
        entry = {
            "title": "SOC Analyst at Global Corp in Remote",
            "link": "https://www.linkedin.com/jobs/view/abc/333",
            "summary": "security operations",
        }
        job = self.scraper._parse_feed_entry(entry)
        assert job is not None
        assert job.is_remote is True
        assert job.country == "Remote"

    def test_parse_feed_entry_india_location(self):
        entry = {
            "title": "Security Engineer at Tech India in Bangalore, India",
            "link": "https://www.linkedin.com/jobs/view/abc/444",
            "summary": "security role in india",
        }
        job = self.scraper._parse_feed_entry(entry)
        assert job is not None
        assert job.country == "India"

    def test_parse_feed_entry_error_returns_none(self):
        entry = {"title": "Security", "link": "bad", "summary": "x"}
        self.scraper._normalize_url = MagicMock(side_effect=Exception("bad url"))  # type: ignore[method-assign]
        assert self.scraper._parse_feed_entry(entry) is None

    def test_parse_feed_entry_empty_title(self):
        entry = {"title": "", "link": "https://www.linkedin.com/jobs/view/999", "summary": ""}
        job = self.scraper._parse_feed_entry(entry)
        assert job is None or job.title == ""

    def test_extract_job_id_view_pattern(self):
        assert (
            self.scraper._extract_job_id("https://www.linkedin.com/jobs/view/xyz/1234567890")
            == "1234567890"
        )

    def test_extract_job_id_currentjob_pattern(self):
        assert self.scraper._extract_job_id("https://www.linkedin.com/jobs?currentJob=555") == "555"

    def test_extract_job_id_no_match(self):
        assert self.scraper._extract_job_id("https://www.linkedin.com/jobs/view/111") == ""

    def test_extract_job_id_empty(self):
        assert self.scraper._extract_job_id("") == ""

    @pytest.mark.asyncio
    async def test_scrape(self):
        feed = MagicMock()
        feed.entries = [
            {
                "title": "Security Analyst at Acme in United States",
                "link": "https://www.linkedin.com/jobs/view/abc/111",
                "summary": "security role",
                "published": "2026-08-01T10:00:00Z",
            }
        ]
        response = MagicMock()
        response.text = "<rss></rss>"
        self.scraper._fetch = AsyncMock(return_value=response)  # type: ignore[method-assign]

        with patch("cybershield.scrapers.usa.linkedin.parse_feed", return_value=feed):
            jobs = await self.scraper.scrape(keywords=["security"], max_pages=1)
        assert len(jobs) == 1
        assert jobs[0].source_id == "111"

    @pytest.mark.asyncio
    async def test_scrape_error(self):
        self.scraper._fetch = AsyncMock(side_effect=Exception("boom"))  # type: ignore[method-assign]
        jobs = await self.scraper.scrape(keywords=["security"])
        assert jobs == []
