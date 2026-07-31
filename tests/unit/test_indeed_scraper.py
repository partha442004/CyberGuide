"""Unit tests for scrapers/indeed.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestIndeedScraper:
    """Tests for IndeedScraper class."""

    def test_source_name(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        assert scraper.source_name == "indeed"

    def test_rate_limit(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        assert scraper.rate_limit == 15

    def test_parse_salary_range(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        salary_min, salary_max = scraper._parse_salary("$80,000 - $120,000")
        assert salary_min == 80000
        assert salary_max == 120000

    def test_parse_salary_single_value(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        salary_min, salary_max = scraper._parse_salary("$80,000 per year")
        assert salary_min == 80000
        assert salary_max == 80000

    def test_parse_salary_no_match(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        salary_min, salary_max = scraper._parse_salary("Competitive salary")
        assert salary_min is None
        assert salary_max is None

    def test_extract_tags_python(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        result = scraper._extract_tags("Python Developer", "Python and Django")
        assert "python" in result

    def test_extract_tags_javascript(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        result = scraper._extract_tags("JavaScript Engineer", "React and Node.js")
        assert "javascript" in result
        assert "react" in result

    def test_extract_tags_remote(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        result = scraper._extract_tags("Remote Developer", "Work from anywhere")
        assert "remote" in result

    def test_extract_tags_empty(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        result = scraper._extract_tags("Developer", "Generic description")
        assert len(result) == 0

    def test_parse_job_card_returns_none_for_no_title(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        card = MagicMock()
        card.find.return_value = None

        result = scraper._parse_job_card(card)
        assert result is None

    def test_parse_job_card_returns_none_for_exception(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        card = MagicMock()
        card.find.side_effect = Exception("Parse error")

        result = scraper._parse_job_card(card)
        assert result is None

    def test_parse_job_card_returns_job_for_valid_card(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        card = MagicMock()

        title_elem = MagicMock()
        title_elem.get_text.return_value = "Python Developer"

        company_elem = MagicMock()
        company_elem.get_text.return_value = "TechCorp"

        link_elem = MagicMock()
        link_elem.get.return_value = "/rc/clk?jk=123"

        location_elem = MagicMock()
        location_elem.get_text.return_value = "Remote"

        salary_elem = MagicMock()
        salary_elem.get_text.return_value = "$80,000 - $120,000"

        snippet_elem = MagicMock()
        snippet_elem.get_text.return_value = "Python and Django experience required"

        def find_side_effect(tag, class_=None, **kwargs):
            if tag == "h2" and class_ == "jobTitle":
                return title_elem
            if tag == "span" and class_ == "companyName":
                return company_elem
            if tag == "a":
                return link_elem
            if tag == "div" and class_ == "companyLocation":
                return location_elem
            if tag == "span" and class_ == "salaryText":
                return salary_elem
            if tag == "div" and class_ == "job-snippet":
                return snippet_elem
            return MagicMock(get_text=MagicMock(return_value="Unknown"))

        card.find.side_effect = find_side_effect

        result = scraper._parse_job_card(card)
        assert result is not None
        assert result.title == "Python Developer"
        assert result.company == "TechCorp"
        assert result.source == "indeed"
        assert "python" in result.tags

    @pytest.mark.asyncio
    async def test_fetch_returns_empty_on_error(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        scraper._get = AsyncMock(side_effect=Exception("Network error"))

        result = await scraper.fetch("python developer")
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_returns_empty_on_non_200(self):
        from interntrack.scrapers.indeed import IndeedScraper

        scraper = IndeedScraper()
        mock_response = MagicMock()
        mock_response.status_code = 403
        scraper._get = AsyncMock(return_value=mock_response)

        result = await scraper.fetch("python developer")
        assert result == []
