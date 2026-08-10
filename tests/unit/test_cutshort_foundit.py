"""
Unit tests for the direct Cutshort and Foundit scrapers.

Cutshort is a Next.js app whose server page always renders a fixed
popular-jobs list (query filtering happens client-side), so the scraper
mirrors the site's own keyword behaviour — any query word in the title
keeps a card — and recovers company names from the posting slug
(``{Title}-{Location?}-{Company}-{code}``). Foundit blocks datacenter IPs
(403), so its tests cover URL building, card extraction and the graceful
empty-fetch path.
"""

from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Cutshort
# ---------------------------------------------------------------------------

_CARD = (
    '<div><div class="sc-7c1b58ff-3 lovZCt">'
    '<div class="sc-7c1b58ff-5 iEpwXd">'
    '<a href="{url}" target="_blank" class="sc-89b45c2f-0 cCGhbz">'
    '<div font-size="20" class="sc-b6704a4e-0 etmRhT">{title}</div>'
    "</a></div></div></div>"
)


def _cutshort_page(*pairs: tuple[str, str]) -> str:
    """HTML with one card per (slug, title) pair."""
    return (
        "<html><body>"
        + "".join(
            _CARD.format(url=f"https://cutshort.io/job/{slug}", title=title)
            for slug, title in pairs
        )
        + "</body></html>"
    )


class TestCutshortScraper:
    def _scraper(self):
        from interntrack.scrapers.cutshort import CutshortScraper

        return CutshortScraper()

    def test_source_name(self):
        assert self._scraper().source_name == "cutshort"

    def test_search_url(self):
        s = self._scraper()
        assert s._search_url("software engineer") == (
            "https://cutshort.io/jobs?query=software+engineer"
        )

    def test_search_url_with_city(self):
        s = self._scraper()
        url = s._search_url("soc analyst", "Bangalore")
        assert url.startswith("https://cutshort.io/jobs?query=soc+analyst")
        assert "city=bangalore" in url

    def test_company_from_slug_simple(self):
        s = self._scraper()
        assert (
            s._company_from_slug(
                "Sr-Engineering-Manager-Egnyte-koBBDTQ1",
                "sr engineering manager",
            )
            == "Egnyte"
        )

    def test_company_from_slug_with_location(self):
        s = self._scraper()
        assert (
            s._company_from_slug(
                "Senior-Software-Architect-Bengaluru-Bangalore-"
                "NeoGenCode-Technologies-Pvt-Ltd-EMFogiZR",
                "senior software architect",
            )
            == "NeoGenCode Technologies Pvt Ltd"
        )

    def test_extract_cards(self):
        s = self._scraper()
        html = _cutshort_page(
            (
                "Senior-Full-stack-Engineer-Sprinto-Rqw1mekJ",
                "senior full-stack engineer",
            ),
            ("Software-Architect-Reflektive-5Jr0Iim2", "software architect"),
        )
        cards = s._extract_cards(html)
        assert len(cards) == 2
        assert cards[0]["title"] == "senior full-stack engineer"
        assert cards[0]["company"] == "Sprinto"
        assert cards[0]["url"].endswith("Senior-Full-stack-Engineer-Sprinto-Rqw1mekJ")

    def test_card_matches_any_query_word(self):
        s = self._scraper()
        # Cutshort's own client filter keeps any card whose title contains a
        # query keyword — "engineer" keeps the full-stack card.
        assert s._card_matches("senior full-stack engineer", "software engineer")
        assert s._card_matches("software architect", "software engineer")
        # Niche queries matching nothing on the popular list drop out.
        assert not s._card_matches("senior full-stack engineer", "cybersecurity")

    @pytest.mark.asyncio
    async def test_fetch_parses_and_filters(self):
        s = self._scraper()
        html = _cutshort_page(
            (
                "Senior-Full-stack-Engineer-Sprinto-Rqw1mekJ",
                "senior full-stack engineer",
            ),
            ("Cyber-Security-Analyst-Acme-7aBcDe1F", "cyber security analyst"),
        )
        resp = AsyncMock()
        resp.status_code = 200
        resp.text = html
        with patch.object(s, "_get", new=AsyncMock(return_value=resp)):
            jobs = await s.fetch("software engineer", "Bangalore", limit=10)
        assert len(jobs) == 1
        assert jobs[0].title == "senior full-stack engineer"
        assert jobs[0].company == "Sprinto"
        assert jobs[0].source == "cutshort"
        assert jobs[0].location == "Bangalore"

    @pytest.mark.asyncio
    async def test_fetch_graceful_on_error(self):
        s = self._scraper()
        with patch.object(s, "_get", new=AsyncMock(side_effect=Exception("boom"))):
            jobs = await s.fetch("software engineer")
        assert jobs == []


# ---------------------------------------------------------------------------
# Foundit
# ---------------------------------------------------------------------------


class TestFounditScraper:
    def _scraper(self):
        from interntrack.scrapers.foundit import FounditScraper

        return FounditScraper()

    def test_source_name(self):
        assert self._scraper().source_name == "foundit"

    def test_search_url(self):
        s = self._scraper()
        assert s._search_url("cybersecurity") == (
            "https://www.foundit.in/search/?query=cybersecurity"
        )

    def test_search_url_with_location(self):
        s = self._scraper()
        assert s._search_url("cybersecurity", "Bangalore") == (
            "https://www.foundit.in/search/?query=cybersecurity&locations=Bangalore"
        )

    def test_extract_cards_anchored(self):
        s = self._scraper()
        html = (
            "<html><body>"
            '<a href="/job/cyber-security-analyst-acme-bangalore-58929969">'
            "Cyber Security Analyst</a>"
            '<a href="/job/soc-analyst-workassist-chennai-48634301">'
            "SOC Analyst</a>"
            "</body></html>"
        )
        cards = s._extract_cards(html)
        assert len(cards) == 2
        assert cards[0]["title"] == "Cyber Security Analyst"
        assert cards[0]["url"].endswith(
            "/job/cyber-security-analyst-acme-bangalore-58929969"
        )
        assert cards[1]["title"] == "SOC Analyst"

    @pytest.mark.asyncio
    async def test_fetch_empty_when_bot_gated(self):
        """Foundit 403s from datacenter IPs — must return [] quietly."""
        s = self._scraper()
        resp = AsyncMock()
        resp.status_code = 403
        resp.text = "<html>blocked</html>"
        with patch.object(s, "_get", new=AsyncMock(return_value=resp)):
            jobs = await s.fetch("cybersecurity", "Bangalore")
        assert jobs == []

    @pytest.mark.asyncio
    async def test_fetch_parses_cards_when_allowed(self):
        s = self._scraper()
        html = (
            "<html><body>"
            '<a href="/job/soc-cyber-security-analyst-tcs-bengaluru-012196">'
            "SOC Cyber Security Analyst</a>"
            "</body></html>"
        )
        resp = AsyncMock()
        resp.status_code = 200
        resp.text = html
        with patch.object(s, "_get", new=AsyncMock(return_value=resp)):
            jobs = await s.fetch("cybersecurity", "Bangalore", limit=10)
        assert len(jobs) == 1
        assert "SOC" in jobs[0].title
        assert jobs[0].source == "foundit"
        assert jobs[0].location == "Bangalore"
