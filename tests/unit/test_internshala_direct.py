"""
Unit tests for the direct Internshala scraper.

Covers the two regressions that made Internshala useless in production:
- keyword/city search URLs redirect to the generic internships page, so the
  scraper now uses the stable ``{query}-internship`` category page;
- posting URLs are read from the card's ``data-href`` (direct
  ``/internship/detail/...`` link) instead of guessing, so saved jobs never
  point at a search page.
"""

from unittest.mock import patch

import pytest


def _card(title: str, company: str, detail_slug: str) -> str:
    """One realistic individual_internship card."""
    return (
        '<div class="container-fluid individual_internship visibilityTrackerItem " '
        f"id='individual_internship_123' data-href='{detail_slug}'>"
        '<div class="internship-heading-container">'
        '<div class="company generic_company">'
        '<h2 class="job-internship-name">'
        f'<a class="job-title-href" id="job_title" href="{detail_slug}" '
        'target="_blank">' + title + "</a></h2>"
        '<p class="company-name">' + company + "</p>"
        "</div></div>"
        "<div>stipend content</div>"
        "</div></div></div>"
    )


def _page(*cards: str) -> str:
    return "<html><body>" + "".join(cards) + "</body></html>"


class TestInternshalaScraper:
    """URL building and card extraction."""

    def _scraper(self):
        from interntrack.scrapers.internshala_direct import InternshalaDirectScraper

        return InternshalaDirectScraper()

    def test_source_name(self):
        assert self._scraper().source_name == "internshala"

    def test_search_url_category_format(self):
        s = self._scraper()
        assert s._search_url("Cyber Security") == (
            "https://internshala.com/internships/cyber-security-internship/"
        )

    def test_search_url_with_city(self):
        s = self._scraper()
        assert s._search_url("Cyber Security", "Bangalore") == (
            "https://internshala.com/internships/"
            "cyber-security-internship-in-bangalore/"
        )

    def test_extract_cards_uses_data_href_detail_links(self):
        s = self._scraper()
        html = _page(
            _card(
                "Cyber Security",
                "Optimasys",
                "/internship/detail/work-from-home-cyber-security-internship-"
                "at-optimasys1785560912",
            ),
            _card(
                "SOC Analyst",
                "Gateway Software Solutions",
                "/internship/detail/soc-analyst-internship-in-tamil-nadu-"
                "at-gateway-software-solutions1784784921",
            ),
        )
        cards = s._extract_cards(html)

        assert len(cards) == 2
        assert cards[0]["title"] == "Cyber Security"
        assert cards[0]["company"] == "Optimasys"
        assert cards[0]["url"] == (
            "https://internshala.com/internship/detail/work-from-home-"
            "cyber-security-internship-at-optimasys1785560912"
        )
        assert cards[1]["title"] == "SOC Analyst"

    def test_extract_cards_skips_non_detail_links(self):
        """A card without a direct detail link is dropped, never a search page."""
        s = self._scraper()
        html = _page(
            "<div class=\"individual_internship\" data-href='/internships/'>"
            '<a class="job-title-href" href="/internships/">Generic</a></div>',
            _card("Ethical Hacker", "Emoolar", "/internship/detail/ethical-hacker-1"),
        )
        cards = s._extract_cards(html)

        assert len(cards) == 1
        assert cards[0]["title"] == "Ethical Hacker"

    def test_extract_cards_dedupes_urls(self):
        s = self._scraper()
        html = _page(
            _card("A", "Co", "/internship/detail/a-1"),
            _card("A again", "Co", "/internship/detail/a-1"),
        )
        cards = s._extract_cards(html)
        assert len(cards) == 1

    def test_fallback_detail_anchors(self):
        """When no cards parse, direct title anchors are used as fallback."""
        s = self._scraper()
        html = (
            '<a class="job-title-href" href="/internship/detail/'
            'malware-analyst-1784784921">Malware Analyst</a>'
        )
        cards = s._extract_detail_anchors(html)

        assert len(cards) == 1
        assert cards[0]["title"] == "Malware Analyst"
        assert "/internship/detail/malware-analyst-1784784921" in cards[0]["url"]

    @pytest.mark.asyncio
    async def test_fetch_returns_direct_links(self):
        from interntrack.scrapers.internshala_direct import InternshalaDirectScraper

        s = InternshalaDirectScraper()
        page = _page(
            _card(
                "Cyber Security",
                "Optimasys",
                "/internship/detail/work-from-home-cyber-security-internship-"
                "at-optimasys1785560912",
            ),
            _card(
                "SOC Analyst",
                "Gateway",
                "/internship/detail/soc-analyst-internship-in-tamil-nadu-"
                "at-gateway-software-solutions1784784921",
            ),
        )

        class FakeResponse:
            status_code = 200
            text = page
            url = "https://internshala.com/internships/cyber-security-internship/"

        class FakeClient:
            def __init__(self):
                self.responses = [FakeResponse()]

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def get(self, *args, **kwargs):
                return self.responses.pop(0)

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            jobs = await s.fetch("cybersecurity")

        assert len(jobs) == 2
        assert all("/internship/detail/" in j.url for j in jobs)
        assert jobs[0].title == "Cyber Security"
        assert jobs[0].company == "Optimasys"
        assert jobs[0].source == "internshala"

    @pytest.mark.asyncio
    async def test_fetch_trusts_canonical_redirect(self):
        """A redirect to a category page is trusted (Internshala canonicalizes
        slugs) — no ?q= fallback, cards from the final page are used."""
        from interntrack.scrapers.internshala_direct import InternshalaDirectScraper

        s = InternshalaDirectScraper()
        page = _page(
            _card(
                "Cyber Security",
                "Optimasys",
                "/internship/detail/cyber-security-internship-at-optimasys-1",
            )
        )

        class CanonicalResponse:
            status_code = 200
            text = page
            # requested cybersecurity-internship, served cyber-security-internship
            url = "https://internshala.com/internships/cyber-security-internship/"

        class FakeClient:
            def __init__(self):
                self.responses = [CanonicalResponse()]

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def get(self, *args, **kwargs):
                return self.responses.pop(0)

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            jobs = await s.fetch("cybersecurity")

        assert len(jobs) == 1
        assert jobs[0].title == "Cyber Security"

    @pytest.mark.asyncio
    async def test_fetch_falls_back_when_slug_unknown_and_filters_junk(self):
        """An unknown slug redirects to bare /internships/; the ?q= page is
        retried and only titles matching the query survive."""
        from interntrack.scrapers.internshala_direct import InternshalaDirectScraper

        s = InternshalaDirectScraper()
        junk = _page(
            _card(
                "Sales and Marketing",
                "Some Co",
                "/internship/detail/sales-marketing-1",
            ),
            _card(
                "Cyber Security",
                "Optimasys",
                "/internship/detail/cyber-security-at-optimasys-2",
            ),
        )

        class BareResponse:
            status_code = 200
            text = junk
            url = "https://internshala.com/internships/"  # unknown slug redirected

        class QueryResponse:
            status_code = 200
            text = junk
            url = "https://internshala.com/internships/?q=cybersecurity"

        class FakeClient:
            def __init__(self):
                self.responses = [BareResponse(), QueryResponse()]

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def get(self, *args, **kwargs):
                return self.responses.pop(0)

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            jobs = await s.fetch("cybersecurity")

        assert len(jobs) == 1
        assert jobs[0].title == "Cyber Security"
        assert jobs[0].company == "Optimasys"

    @pytest.mark.asyncio
    async def test_fetch_location_falls_back_to_category_page(self):
        """A city page whose cards don't match the query falls back to the
        plain category page instead of returning nothing."""
        from interntrack.scrapers.internshala_direct import InternshalaDirectScraper

        s = InternshalaDirectScraper()
        city_junk = _page(
            _card(
                "Sales and Marketing",
                "Some Co",
                "/internship/detail/sales-marketing-1",
            ),
        )
        real = _page(
            _card(
                "Cyber Security",
                "Optimasys",
                "/internship/detail/cyber-security-at-optimasys-2",
            ),
        )

        class CityResponse:
            status_code = 200
            text = city_junk
            url = (
                "https://internshala.com/internships/cybersecurity-internship-"
                "in-bangalore/"
            )

        class PlainResponse:
            status_code = 200
            text = real
            url = "https://internshala.com/internships/cyber-security-internship/"

        class FakeClient:
            def __init__(self):
                self.responses = [CityResponse(), PlainResponse()]

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def get(self, *args, **kwargs):
                return self.responses.pop(0)

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            jobs = await s.fetch("cybersecurity", location="Bangalore")

        assert len(jobs) == 1
        assert jobs[0].title == "Cyber Security"
        assert jobs[0].company == "Optimasys"
