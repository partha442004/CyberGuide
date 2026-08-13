"""
Unit tests for the direct JobDexo scraper.

JobDexo ("India's first job index for freshers") renders fresher /
off-campus job cards server-side; the scraper parses the card blocks and
keeps direct ``/job/{code}/{slug}`` posting links. These tests lock the
card extraction, salary/deadline parsing and the relevance filter.
"""

from datetime import datetime
from unittest.mock import patch

import pytest


def _card(
    title: str,
    company: str,
    slug: str,
    location: str = "Hyderabad, India",
    salary: str = "3.5 LPA",
    badge: str = "Fulltime",
    deadline: str = "31 Dec 2026",
    desc: str = "A global company offers enhanced threat detection.",
) -> str:
    """One realistic JobDexo ``article.job-card`` block."""
    return (
        '<article class="job-card">'
        '<div class="job-card-header"><div>'
        f'<div class="job-company">{company}</div>'
        '<h3 class="job-title">'
        f'<a href="/job/{slug}">{title}</a>'
        "</h3></div>"
        f'<span class="job-badge badge-fulltime">{badge}</span>'
        "</div>"
        '<div class="job-meta">'
        '<span class="job-meta-item"><svg viewBox="0 0 24 24"><path d="M21 10"/></svg>'
        f"{location}      </span>"
        '<span class="job-meta-item"><svg viewBox="0 0 24 24"><path d="M17 5"/></svg>'
        f"{salary}      </span>"
        "</div>"
        f'<p style="font-size:.85rem; color:var(--text-muted);">{desc}</p>'
        '<div class="job-card-footer">'
        f'<span class="job-deadline ">⏳ Deadline: {deadline}</span>'
        f'<a href="/job/{slug}" class="btn">View &amp; Apply →</a>'
        "</div></article>"
    )


def _page(*cards: str) -> str:
    return "<html><body>" + "".join(cards) + "</body></html>"


class TestJobDexoScraper:
    def _scraper(self):
        from interntrack.scrapers.jobdexo import JobDexoScraper

        return JobDexoScraper()

    def test_source_name(self):
        assert self._scraper().source_name == "jobdexo"

    def test_search_url_plain_query(self):
        assert self._scraper()._search_url("cyber security") == (
            "https://jobdexo.com/?q=cyber+security"
        )

    def test_search_url_internship_type(self):
        url = self._scraper()._search_url("cybersecurity intern")
        assert "q=cybersecurity+intern" in url
        assert "type=internship" in url

    def test_search_url_remote_type(self):
        url = self._scraper()._search_url("remote developer")
        assert "type=remote" in url

    def test_extract_cards_full_fields(self):
        s = self._scraper()
        html = _page(
            _card(
                "Security Analyst I",
                "Fortuna Cysec",
                "C027-J076/security-analyst-i-fortuna-cysec-2026",
            ),
            _card(
                "Front Desk Receptionist",
                "Lobby Co",
                "C027-J077/front-desk-receptionist-lobby-co-2026",
                location="Mumbai, India",
                salary="₹ 6,500 - 10,000",
                deadline="15 Sep 2026",
            ),
        )
        cards = s._extract_cards(html)

        assert len(cards) == 2
        assert cards[0]["title"] == "Security Analyst I"
        assert cards[0]["company"] == "Fortuna Cysec"
        assert cards[0]["url"] == (
            "https://jobdexo.com/job/C027-J076/security-analyst-i-fortuna-cysec-2026"
        )
        assert cards[0]["location"] == "Hyderabad, India"
        assert cards[0]["salary_text"] == "3.5 LPA"
        assert cards[0]["job_type"] == "Fulltime"
        assert cards[0]["deadline"] == datetime(2026, 12, 31)
        assert "threat detection" in (cards[0]["description"] or "")
        assert cards[1]["location"] == "Mumbai, India"

    def test_extract_cards_unescapes_double_entities(self):
        """JobDexo sometimes double-escapes (&amp;amp;) — decode to plain text."""
        s = self._scraper()
        html = _page(
            _card(
                "Associate Security Analytics &amp;amp; Operations",
                "Charles Schwab",
                "C027-J074/associate-security-analytics-charles-schwab-2026",
            )
        )
        cards = s._extract_cards(html)
        assert cards[0]["title"] == "Associate Security Analytics & Operations"

    def test_extract_cards_dedupes_urls(self):
        s = self._scraper()
        html = _page(
            _card("A", "Co", "C1/a-2026"),
            _card("A again", "Co", "C1/a-2026"),
        )
        cards = s._extract_cards(html)
        assert len(cards) == 1

    def test_extract_cards_skips_broken_blocks(self):
        s = self._scraper()
        html = _page("<article class='job-card'>no anchor here</article>")
        assert s._extract_cards(html) == []

    def test_parse_salary_lpa_single(self):
        assert self._scraper()._parse_salary("3.5 LPA") == (350000, 350000)

    def test_parse_salary_lpa_range(self):
        assert self._scraper()._parse_salary("3 - 5 LPA") == (300000, 500000)

    def test_parse_salary_rupee_range(self):
        assert self._scraper()._parse_salary("₹ 6,500 - 10,000") == (6500, 10000)

    def test_parse_salary_empty(self):
        assert self._scraper()._parse_salary("") == (None, None)

    def test_parse_deadline(self):
        assert self._scraper()._parse_deadline("31 Dec 2026") == datetime(2026, 12, 31)

    def test_parse_deadline_garbage(self):
        assert self._scraper()._parse_deadline("Rolling") is None

    @pytest.mark.asyncio
    async def test_fetch_filters_and_builds_raw_jobs(self):
        from interntrack.scrapers.jobdexo import JobDexoScraper

        s = JobDexoScraper()
        page = _page(
            _card(
                "Security Analyst I",
                "Fortuna Cysec",
                "C027-J076/security-analyst-i-fortuna-cysec-2026",
            ),
            _card(
                "Front Desk Receptionist",
                "Lobby Co",
                "C027-J077/front-desk-receptionist-lobby-co-2026",
            ),
            _card(
                "SOC Analyst L2",
                "Gateway",
                "C027-J078/soc-analyst-l2-gateway-2026",
                location="Remote, India",
                salary="6 LPA",
            ),
        )

        class FakeResponse:
            status_code = 200
            text = page
            url = "https://jobdexo.com/?q=cybersecurity"

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def get(self, *args, **kwargs):
                return FakeResponse()

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            jobs = await s.fetch("cybersecurity")

        # "Front Desk Receptionist" fails the security-family filter.
        assert len(jobs) == 2
        assert jobs[0].title == "Security Analyst I"
        assert jobs[0].company == "Fortuna Cysec"
        assert jobs[0].source == "jobdexo"
        assert "/job/" in jobs[0].url
        assert jobs[0].salary_min == 350000
        assert jobs[0].salary_currency == "INR"
        assert jobs[0].expires_at == datetime(2026, 12, 31)
        assert jobs[1].title == "SOC Analyst L2"
        assert jobs[1].is_remote is True
        assert jobs[1].tags == ["fresher", "off-campus"]

    @pytest.mark.asyncio
    async def test_fetch_http_error_returns_empty(self):
        from interntrack.scrapers.jobdexo import JobDexoScraper

        s = JobDexoScraper()

        class FakeResponse:
            status_code = 403
            text = "<html></html>"
            url = "https://jobdexo.com/"

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def get(self, *args, **kwargs):
                return FakeResponse()

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            assert await s.fetch("cybersecurity") == []
