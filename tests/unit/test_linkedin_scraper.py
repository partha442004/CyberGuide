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
