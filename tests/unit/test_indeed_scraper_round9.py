"""
Unit tests for the interntrack IndeedScraper.fetch() success path.

Covers the previously-uncovered branches: the ``location`` parameter being
added to the query, parsing of a 200 response's HTML into job cards, and the
``limit`` slice.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from interntrack.scrapers.indeed import IndeedScraper

HTML_TWO_CARDS = """
<html><body>
  <div class="job_seen_beacon">
    <h2 class="jobTitle"><a>Security Engineer</a></h2>
    <span class="companyName">Acme Corp</span>
    <div class="companyLocation">Pune, MH</div>
    <span class="salaryText">$80,000 - $100,000</span>
    <div class="job-snippet">Python and AWS experience</div>
  </div>
  <div class="job_seen_beacon">
    <h2 class="jobTitle"><a>DevOps Engineer</a></h2>
    <span class="companyName">Beta Ltd</span>
    <div class="companyLocation">Remote</div>
    <div class="job-snippet">Kubernetes</div>
  </div>
</body></html>
"""


@pytest.fixture
def scraper() -> IndeedScraper:
    return IndeedScraper()


@pytest.mark.asyncio
async def test_fetch_adds_location_param(scraper):
    """fetch() must include the location in the query params."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body></body></html>"
    scraper._get = AsyncMock(return_value=mock_response)

    await scraper.fetch("python", location="Pune")

    called_url = scraper._get.await_args.args[0]
    assert "l=Pune" in called_url


@pytest.mark.asyncio
async def test_fetch_parses_job_cards_from_html(scraper):
    """A 200 response with job cards yields parsed RawJobs."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = HTML_TWO_CARDS
    scraper._get = AsyncMock(return_value=mock_response)

    jobs = await scraper.fetch("security")

    assert len(jobs) == 2
    assert jobs[0].title == "Security Engineer"
    assert jobs[0].company == "Acme Corp"
    assert jobs[0].location == "Pune, MH"
    assert jobs[0].salary_min == 80000
    assert jobs[0].salary_max == 100000
    assert jobs[1].title == "DevOps Engineer"


@pytest.mark.asyncio
async def test_fetch_respects_limit(scraper):
    """fetch() must not return more cards than the requested limit."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = HTML_TWO_CARDS
    scraper._get = AsyncMock(return_value=mock_response)

    jobs = await scraper.fetch("security", limit=1)

    assert len(jobs) == 1


@pytest.mark.asyncio
async def test_fetch_no_cards_returns_empty(scraper):
    """A 200 response without job cards yields an empty list."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><p>No results</p></body></html>"
    scraper._get = AsyncMock(return_value=mock_response)

    jobs = await scraper.fetch("security")

    assert jobs == []
