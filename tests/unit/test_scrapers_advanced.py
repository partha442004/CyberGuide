"""
Unit tests for advanced scraper implementations (LinkedIn, Indeed, Glassdoor).
"""


import pytest

from interntrack.scrapers.glassdoor import GlassdoorScraper
from interntrack.scrapers.indeed import IndeedScraper
from interntrack.scrapers.linkedin import LinkedInScraper


class TestLinkedInScraper:
    """Tests for LinkedInScraper."""

    @pytest.fixture
    def scraper(self):
        """Create LinkedInScraper instance."""
        return LinkedInScraper()

    def test_source_name(self, scraper):
        """Test source_name property."""
        assert scraper.source_name == "linkedin"

    def test_rate_limit(self, scraper):
        """Test rate_limit property."""
        assert scraper.rate_limit == 10

    def test_extract_tags(self, scraper):
        """Test extracting tags from text."""
        title = "Python Developer with React Experience"
        description = "Remote position requiring Docker and AWS"
        tags = scraper._extract_tags(title, description)
        assert "python" in tags
        assert "react" in tags
        assert "remote" in tags

    def test_extract_tags_empty(self, scraper):
        """Test extracting tags from empty text."""
        tags = scraper._extract_tags("", "")
        assert len(tags) == 0


class TestIndeedScraper:
    """Tests for IndeedScraper."""

    @pytest.fixture
    def scraper(self):
        """Create IndeedScraper instance."""
        return IndeedScraper()

    def test_source_name(self, scraper):
        """Test source_name property."""
        assert scraper.source_name == "indeed"

    def test_rate_limit(self, scraper):
        """Test rate_limit property."""
        assert scraper.rate_limit == 15

    def test_parse_salary(self, scraper):
        """Test salary parsing."""
        salary_min, salary_max = scraper._parse_salary("$80,000 - $120,000")
        assert salary_min == 80000
        assert salary_max == 120000

    def test_parse_salary_single_value(self, scraper):
        """Test salary parsing with single value."""
        salary_min, salary_max = scraper._parse_salary("$80,000")
        assert salary_min == 80000
        assert salary_max == 80000

    def test_parse_salary_no_match(self, scraper):
        """Test salary parsing with no numbers."""
        salary_min, salary_max = scraper._parse_salary("Competitive")
        assert salary_min is None
        assert salary_max is None

    def test_extract_tags(self, scraper):
        """Test extracting tags from text."""
        title = "Senior Python Developer"
        description = "Entry level position with SQL and Java"
        tags = scraper._extract_tags(title, description)
        assert "python" in tags
        assert "senior" in tags
        assert "entry-level" in tags


class TestGlassdoorScraper:
    """Tests for GlassdoorScraper."""

    @pytest.fixture
    def scraper(self):
        """Create GlassdoorScraper instance."""
        return GlassdoorScraper()

    def test_source_name(self, scraper):
        """Test source_name property."""
        assert scraper.source_name == "glassdoor"

    def test_rate_limit(self, scraper):
        """Test rate_limit property."""
        assert scraper.rate_limit == 10

    def test_parse_salary(self, scraper):
        """Test salary parsing."""
        salary_min, salary_max = scraper._parse_salary("$80K - $120K")
        assert salary_min == 80000
        assert salary_max == 120000

    def test_parse_salary_comma_format(self, scraper):
        """Test salary parsing with comma format."""
        salary_min, salary_max = scraper._parse_salary("$80,000 - $120,000")
        assert salary_min == 80000
        assert salary_max == 120000

    def test_parse_salary_no_match(self, scraper):
        """Test salary parsing with no numbers."""
        salary_min, salary_max = scraper._parse_salary("Competitive")
        assert salary_min is None
        assert salary_max is None

    def test_extract_tags(self, scraper):
        """Test extracting tags from text."""
        title = "Data Scientist with Machine Learning"
        description = "Remote position requiring Python and Docker"
        tags = scraper._extract_tags(title, description)
        assert "python" in tags
        assert "ml" in tags
        assert "remote" in tags
