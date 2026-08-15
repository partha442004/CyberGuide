"""
Unit tests for the Freshersworld scraper.

Covers the pieces that make it reliable in production:
- city slug resolution from free-text locations (Bengaluru -> bangalore);
- salary parsing from the '15000 Monthly' / '3.5 LPA' qualification spans;
- posted-date parsing from the '15 August 2026' description prefix;
- card extraction from the real job-container markup (job_display_url,
  wrap-title, company-name, job-location, experience, qualifications);
- relevance filtering: only cards matching the discovery query survive;
- non-200 responses degrade to an empty list instead of raising.
"""

from unittest.mock import AsyncMock, patch

import pytest


def _card(
    title: str,
    company: str = "Acme Pvt Ltd",
    location: str = "Bangalore",
    experience: str = "0 to 2 Years",
    salary: str = "15000 Monthly",
    posted: str = "15 August 2026",
    url: str = "https://www.freshersworld.com/jobs/test-role-12345",
) -> str:
    """One realistic job-container card from the city listing page."""
    return (
        '<div class="col-md-12 col-lg-12 col-xs-12 padding-none job-container '
        f'jobs-on-hover top_space" job_id="12345" job_display_url="{url}" '
        'id="all-jobs-append">'
        '<div class="col-md-12  col-xs-12  col-lg-12 job_listing_alignment">'
        "<div>"
        '<div class="job-new-title">'
        f'<span class="wrap-title seo_title">{title}<span class="title_less" '
        'style="display:none;">Less</span></span>'
        "</div>"
        f'<h3 class="latest-jobs-title font-16 margin-none inline-block company-name">'
        f"{company}</h3>"
        '<span class="job-location display-block modal-open job-details-span">'
        f"<span class='bold_elig'>{location}</span></span>"
        f'<span class="experience job-details-span" style="padding-left: 6px;">'
        f"{experience}</span>"
        '<span class="qualifications display-block modal-open pull-left '
        f'job-details-span">{salary}</span>'
        f'<span class="desc">{posted}  Apply for the latest {title[:20]}...</span>'
        "</div></div></div>"
    )


def _page(*cards: str) -> str:
    return "<html><body>" + "".join(cards) + "</body></html>"


class TestCitySlug:
    def test_known_metro(self):
        from interntrack.scrapers.freshersworld import _city_slug

        assert _city_slug("Bangalore") == "bangalore"
        assert _city_slug("Bengaluru, Karnataka") == "bangalore"
        assert _city_slug("Pune") == "pune"
        assert _city_slug("New Delhi") == "delhi"

    def test_unknown_city_is_none(self):
        from interntrack.scrapers.freshersworld import _city_slug

        assert _city_slug("Villupuram") is None
        assert _city_slug(None) is None


class TestParsers:
    def test_salary_monthly_is_annualised(self):
        from interntrack.scrapers.freshersworld import _parse_salary

        assert _parse_salary("15000 Monthly") == (180000, 180000)
        assert _parse_salary("3.5 LPA") == (350000, 350000)
        assert _parse_salary("Not Disclosed") == (None, None)

    def test_posted_date(self):
        from interntrack.scrapers.freshersworld import _parse_posted

        dt = _parse_posted("15 August 2026")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 8
        assert dt.day == 15
        assert _parse_posted("Apply now") is None


class TestFreshersworldScraper:
    def _scraper(self):
        from interntrack.scrapers.freshersworld import FreshersworldScraper

        return FreshersworldScraper()

    def test_source_name(self):
        assert self._scraper().source_name == "freshersworld"

    def test_search_url_uses_city_page_for_known_metro(self):
        s = self._scraper()
        assert (
            s._search_url("Bangalore")
            == "https://www.freshersworld.com/jobs-in-bangalore/9999016065"
        )

    def test_search_url_falls_back_to_general_jobs_page(self):
        s = self._scraper()
        assert s._search_url(None) == "https://www.freshersworld.com/jobs"

    def test_extract_cards_parses_real_fields(self):
        s = self._scraper()
        page = _page(
            _card("Cyber Security Analyst Jobs Opening in Acme at Bangalore"),
            _card(
                "Telecaller Jobs Opening in Other Corp at Indore",
                url="https://www.freshersworld.com/jobs/telecaller-67890",
            ),
        )
        cards = s._extract_cards(page)
        assert len(cards) == 2
        first = cards[0]
        assert first["title"].startswith("Cyber Security Analyst")
        assert first["company"] == "Acme Pvt Ltd"
        assert first["location"] == "Bangalore"
        assert first["experience"] == "0 to 2 Years"
        assert first["salary"] == "15000 Monthly"
        assert first["posted_at"] is not None

    def test_extract_cards_skips_cards_without_display_url(self):
        s = self._scraper()
        broken = (
            '<div class="job-container jobs-on-hover">'
            '<div class="job-new-title"><span class="wrap-title seo_title">'
            'No Link Here<span class="title_less">Less</span></span></div>'
            "</div>"
        )
        cards = s._extract_cards(_page(broken))
        assert cards == []

    @pytest.mark.asyncio
    async def test_fetch_filters_by_query(self):
        s = self._scraper()
        page = _page(
            _card("Cyber Security Analyst Jobs Opening in Acme at Bangalore"),
            _card("Telecaller Jobs Opening in Other Corp at Indore"),
        )
        with patch("httpx.AsyncClient") as mock_client:
            resp = AsyncMock()
            resp.status_code = 200
            resp.text = page
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=resp
            )
            jobs = await s.fetch("cyber security", "Bangalore", limit=10)

        assert len(jobs) == 1
        job = jobs[0]
        assert job.source == "freshersworld"
        assert job.salary_currency == "INR"
        assert job.salary_min == 180000
        assert job.tags == ["fresher"]
        assert job.url.startswith("https://www.freshersworld.com/jobs/")

    @pytest.mark.asyncio
    async def test_fetch_degrades_on_non_200(self):
        s = self._scraper()
        with patch("httpx.AsyncClient") as mock_client:
            resp = AsyncMock()
            resp.status_code = 403
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=resp
            )
            jobs = await s.fetch("cyber security", "Bangalore")
        assert jobs == []
