"""Unit tests for scrapers/linkedin.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestLinkedInScraper:
    """Tests for LinkedInScraper class."""

    def test_source_name(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        assert scraper.source_name == "linkedin"

    def test_rate_limit(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        assert scraper.rate_limit == 10

    def test_extract_tags_python(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        title = "Python Developer"
        description = "We need Python and Django experience"
        tags = scraper._extract_tags(title, description)
        assert "python" in tags

    def test_extract_tags_javascript(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        title = "JavaScript Engineer"
        description = "React and Node.js experience required"
        tags = scraper._extract_tags(title, description)
        assert "javascript" in tags
        assert "react" in tags
        assert "nodejs" in tags

    def test_extract_tags_java(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        title = "Java Developer"
        description = "Java and Spring Boot"
        tags = scraper._extract_tags(title, description)
        assert "java" in tags

    def test_extract_tags_cloud(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        title = "Cloud Engineer"
        description = "AWS and Docker experience"
        tags = scraper._extract_tags(title, description)
        assert "aws" in tags
        assert "docker" in tags

    def test_extract_tags_remote(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        title = "Remote Developer"
        description = "Work from anywhere"
        tags = scraper._extract_tags(title, description)
        assert "remote" in tags

    def test_extract_tags_empty(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        title = "Developer"
        description = "Some generic description"
        tags = scraper._extract_tags(title, description)
        assert len(tags) == 0

    def test_parse_job_card_returns_none_for_no_title(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        card = MagicMock()
        card.find.return_value = None

        result = scraper._parse_job_card(card)
        assert result is None

    def test_parse_job_card_returns_none_for_no_url(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        card = MagicMock()

        # Title found but no URL
        title_elem = MagicMock()
        title_elem.get_text.return_value = "Python Developer"

        link_elem = MagicMock()
        link_elem.__getitem__ = MagicMock(side_effect=KeyError)

        def find_side_effect(tag, class_=None):
            if class_ == "result-card__title":
                return title_elem
            if class_ == "result-card__full-card-link":
                return link_elem
            return MagicMock(get_text=MagicMock(return_value="Unknown"))

        card.find.side_effect = find_side_effect

        result = scraper._parse_job_card(card)
        assert result is None

    def test_parse_job_card_returns_job_for_valid_card(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        card = MagicMock()

        title_elem = MagicMock()
        title_elem.get_text.return_value = "Python Developer"

        company_elem = MagicMock()
        company_elem.get_text.return_value = "TechCorp"

        link_elem = MagicMock()
        link_elem.__getitem__ = MagicMock(return_value="https://linkedin.com/jobs/123")

        location_elem = MagicMock()
        location_elem.get_text.return_value = "Remote"

        date_elem = MagicMock()
        date_elem.__getitem__ = MagicMock(return_value="2026-07-30T00:00:00Z")

        desc_elem = MagicMock()
        desc_elem.get_text.return_value = "Python and Django experience required"

        def find_side_effect(tag, class_=None):
            if class_ == "result-card__title":
                return title_elem
            if class_ == "result-card__company-name":
                return company_elem
            if class_ == "result-card__full-card-link":
                return link_elem
            if class_ == "job-result__location":
                return location_elem
            if class_ == "result-card__listed-date":
                return date_elem
            if class_ == "result-card__snippet":
                return desc_elem
            return None

        card.find.side_effect = find_side_effect

        result = scraper._parse_job_card(card)
        assert result is not None
        assert result.title == "Python Developer"
        assert result.company == "TechCorp"
        assert result.url == "https://linkedin.com/jobs/123"
        assert result.location == "Remote"
        assert "python" in result.tags

    def test_parse_job_card_exception_handling(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        card = MagicMock()
        card.find.side_effect = Exception("Parse error")

        result = scraper._parse_job_card(card)
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_returns_empty_on_error(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        scraper._get = AsyncMock(side_effect=Exception("Network error"))

        result = await scraper.fetch("python developer")
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_returns_empty_on_non_200(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        mock_response = MagicMock()
        mock_response.status_code = 403
        scraper._get = AsyncMock(return_value=mock_response)

        result = await scraper.fetch("python developer")
        assert result == []


# Real guest-API markup observed live (2026-08): legacy ``result-card``
# classes are gone and the search cards use ``job-search-card``.
_NEW_MARKUP = """
<!DOCTYPE html>
<li>
  <div class="base-card relative w-full hover:no-underline focus:no-underline
    base-card--link base-search-card base-search-card--link job-search-card"
    data-entity-urn="urn:li:jobPosting:4447606116">
    <a class="base-card__full-link absolute top-0 right-0 bottom-0 left-0"
       href="https://www.linkedin.com/jobs/view/cybersecurity-ai-trainer-4447606116"></a>
    <div class="base-search-card__info">
      <h3 class="base-search-card__title">
        Cybersecurity AI Trainer, $125–$150/hour
      </h3>
      <h4 class="base-search-card__subtitle">
        <a class="hidden-nested-link" href="https://www.linkedin.com/company/linkedin">
          LinkedIn
        </a>
      </h4>
      <div class="base-search-card__metadata">
        <span class="job-search-card__location">United States</span>
        <time class="job-search-card__listdate" datetime="2026-08-01">3 days ago</time>
      </div>
    </div>
  </div>
</li>
"""


class TestLinkedInScraperNewMarkup:
    """Tests for the current job-search-card markup."""

    @pytest.mark.asyncio
    async def test_fetch_parses_current_markup(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = _NEW_MARKUP
        scraper._get = AsyncMock(return_value=mock_response)

        jobs = await scraper.fetch("cybersecurity")
        assert len(jobs) == 1
        job = jobs[0]
        assert job.title == "Cybersecurity AI Trainer, $125–$150/hour"
        assert job.company == "LinkedIn"
        assert (
            job.url
            == "https://www.linkedin.com/jobs/view/cybersecurity-ai-trainer-4447606116"
        )
        assert job.location == "United States"
        assert job.posted_at is not None
        assert job.posted_at.date().isoformat() == "2026-08-01"
        assert job.source == "linkedin"
        assert job.raw_data == {"job_id": "4447606116"}

    @pytest.mark.asyncio
    async def test_fetch_skips_auth_wall(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        scraper = LinkedInScraper()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            "<html><body>authwall <p>Join now to see who viewed this</p></body></html>"
        )
        scraper._get = AsyncMock(return_value=mock_response)

        jobs = await scraper.fetch("cybersecurity")
        assert jobs == []

    @pytest.mark.asyncio
    async def test_fetch_multi_page_markup_respects_limit(self):
        from interntrack.scrapers.linkedin import LinkedInScraper

        # Three copies of the same card.
        html = "".join(f"<li>{_NEW_MARKUP}</li>" for _ in range(3))
        scraper = LinkedInScraper()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        scraper._get = AsyncMock(return_value=mock_response)

        jobs = await scraper.fetch("cybersecurity", limit=2)
        assert len(jobs) == 2
