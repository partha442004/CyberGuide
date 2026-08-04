"""
Extended tests for the BaseScraper.

Covers caching helpers, fetch paths, rate limiting, URL normalization,
date parsing, run/clear_cache/get_stats, and the ScraperConfig defaults.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cybershield.cache import cache_manager
from cybershield.scrapers.base import BaseScraper, ScrapedJob, ScraperConfig


class _TestScraper(BaseScraper):
    """Concrete scraper for testing base behavior."""

    def __init__(self, config, cache_ttl=300):
        super().__init__(config, cache_ttl)

    async def scrape(self, **kwargs):
        return []


def _make_scraper(**config_overrides):
    config = ScraperConfig(
        name="test",
        base_url="https://test.com",
        **config_overrides,
    )
    return _TestScraper(config)


def _response(status_code: int = 200, text: str = "ok") -> httpx.Response:
    request = httpx.Request("GET", "https://test.com/jobs")
    return httpx.Response(status_code, text=text, request=request)


class TestScraperConfig:
    def test_default_headers(self):
        config = ScraperConfig(name="x", base_url="https://x.com")
        assert "User-Agent" in config.headers
        assert "Accept" in config.headers
        assert config.rate_limit == 1.0
        assert config.max_retries == 3
        assert config.timeout == 30.0
        assert config.proxy is None

    def test_custom_values(self):
        config = ScraperConfig(
            name="x",
            base_url="https://x.com",
            rate_limit=5.0,
            timeout=10.0,
            headers={"User-Agent": "custom"},
            proxy="http://proxy:8080",
        )
        assert config.rate_limit == 5.0
        assert config.timeout == 10.0
        assert config.headers["User-Agent"] == "custom"
        assert config.proxy == "http://proxy:8080"


class TestScrapedJob:
    def test_defaults(self):
        job = ScrapedJob()
        assert job.is_remote is False
        assert job.is_hybrid is False
        assert job.is_onsite is True
        assert job.required_skills == []
        assert job.preferred_skills == []
        assert job.raw_data == {}
        assert job.title is None

    def test_to_dict_includes_all_fields(self):
        job = ScrapedJob()
        job.title = "T"
        job.company_name = "C"
        data = job.to_dict()
        assert data["title"] == "T"
        assert data["company_name"] == "C"
        assert data["is_onsite"] is True
        assert "raw_data" not in data  # raw_data is excluded from dict


class TestCacheKeyAndContentHash:
    def test_generate_cache_key_deterministic(self):
        scraper = _make_scraper()
        k1 = scraper._generate_cache_key("https://x.com", {"a": 1})
        k2 = scraper._generate_cache_key("https://x.com", {"a": 1})
        assert k1 == k2
        assert len(k1) == 32  # md5 hexdigest

    def test_generate_cache_key_different_params(self):
        scraper = _make_scraper()
        k1 = scraper._generate_cache_key("https://x.com", {"a": 1})
        k2 = scraper._generate_cache_key("https://x.com", {"a": 2})
        assert k1 != k2


class TestNormalizeUrl:
    def test_removes_tracking_params(self):
        scraper = _make_scraper()
        url = "https://example.com/job/1?utm_source=a&ref=b&id=123"
        normalized = scraper._normalize_url(url)
        assert "utm_source" not in normalized
        assert "ref=" not in normalized
        assert "id=123" in normalized

    def test_no_params_unchanged(self):
        scraper = _make_scraper()
        url = "https://example.com/job/1"
        assert scraper._normalize_url(url) == url

    def test_empty_url(self):
        scraper = _make_scraper()
        assert scraper._normalize_url("") == ""


class TestParseDate:
    def test_iso_date(self):
        scraper = _make_scraper()
        assert scraper._parse_date("2024-01-15") is not None

    def test_iso_datetime(self):
        scraper = _make_scraper()
        assert scraper._parse_date("2024-01-15T10:30:00") is not None

    def test_dmy_format(self):
        scraper = _make_scraper()
        assert scraper._parse_date("15/01/2024") is not None

    def test_long_month_format(self):
        scraper = _make_scraper()
        assert scraper._parse_date("January 15, 2024") is not None

    def test_invalid_returns_none(self):
        scraper = _make_scraper()
        assert scraper._parse_date("not-a-date") is None

    def test_empty_returns_none(self):
        scraper = _make_scraper()
        assert scraper._parse_date(None) is None


class TestFetch:
    @pytest.mark.asyncio
    async def test_do_fetch_success(self):
        scraper = _make_scraper(rate_limit=0)

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, *args, **kwargs):
                return _response()

        with patch("cybershield.scrapers.base.httpx.AsyncClient", FakeClient):
            response = await scraper._do_fetch("https://test.com/jobs")
            assert response.status_code == 200
            assert scraper._request_count == 1

    @pytest.mark.asyncio
    async def test_do_fetch_http_error_raises_and_counts(self):
        scraper = _make_scraper(rate_limit=0)

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, *args, **kwargs):
                request = httpx.Request("GET", "https://test.com/missing")
                return httpx.Response(404, text="nope", request=request)

        with patch("cybershield.scrapers.base.httpx.AsyncClient", FakeClient):
            with pytest.raises(httpx.HTTPStatusError):
                await scraper._do_fetch("https://test.com/missing")
            assert scraper._error_count == 1

    @pytest.mark.asyncio
    async def test_do_fetch_request_error_raises_and_counts(self):
        scraper = _make_scraper(rate_limit=0)

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, *args, **kwargs):
                raise httpx.ConnectError("refused")

        with patch("cybershield.scrapers.base.httpx.AsyncClient", FakeClient):
            with pytest.raises(httpx.RequestError):
                await scraper._do_fetch("https://test.com/down")
            assert scraper._error_count == 1


class TestFetchWithCache:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_network(self):
        scraper = _make_scraper(rate_limit=0)
        cached = {
            "status_code": 200,
            "content": "<html>cached</html>",
            "headers": {"content-type": "text/html"},
        }

        with patch.object(cache_manager, "get_json", AsyncMock(return_value=cached)):
            response = await scraper._fetch_with_cache("https://test.com/jobs")
            assert response.status_code == 200
            assert response.text == "<html>cached</html>"
            assert scraper._cache_hits == 1
            assert scraper._request_count == 0  # no network call

    @pytest.mark.asyncio
    async def test_cache_miss_fetches_and_stores(self):
        scraper = _make_scraper(rate_limit=0)

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, *args, **kwargs):
                request = httpx.Request("GET", "https://test.com/jobs")
                return httpx.Response(200, text="<html>fresh</html>", request=request)

        stored = {}

        async def fake_set_json(key, value, ttl=None):
            stored[key] = value

        with (
            patch.object(cache_manager, "get_json", AsyncMock(return_value=None)),
            patch.object(cache_manager, "set_json", fake_set_json),
            patch("cybershield.scrapers.base.httpx.AsyncClient", FakeClient),
        ):
            response = await scraper._fetch_with_cache("https://test.com/jobs")
            assert response.status_code == 200
            assert scraper._cache_misses == 1
            assert len(stored) == 1

    @pytest.mark.asyncio
    async def test_use_cache_false_skips_cache(self):
        scraper = _make_scraper(rate_limit=0)

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, *args, **kwargs):
                request = httpx.Request("GET", "https://test.com/jobs")
                return httpx.Response(200, text="ok", request=request)

        with (
            patch.object(cache_manager, "get_json", AsyncMock(return_value={"x": 1})),
            patch("cybershield.scrapers.base.httpx.AsyncClient", FakeClient),
        ):
            response = await scraper._fetch_with_cache("https://test.com/jobs", use_cache=False)
            assert response.status_code == 200
            assert scraper._cache_hits == 0  # cache not consulted


class TestCreateCachedResponse:
    def test_creates_response(self):
        scraper = _make_scraper()
        response = scraper._create_cached_response(
            {
                "status_code": 200,
                "content": "<html>x</html>",
                "headers": {"content-type": "text/html"},
            }
        )
        assert response.status_code == 200
        assert "x" in response.text
        assert response.headers["content-type"] == "text/html"


class TestRunAndStats:
    @pytest.mark.asyncio
    async def test_run_returns_results(self):
        scraper = _make_scraper()
        scraper.scrape = AsyncMock(return_value=[ScrapedJob(), ScrapedJob()])
        results = await scraper.run()
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_run_propagates_errors(self):
        scraper = _make_scraper()

        async def boom(**kwargs):
            raise RuntimeError("scrape failed")

        scraper.scrape = boom
        with pytest.raises(RuntimeError):
            await scraper.run()

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        scraper = _make_scraper()
        with patch.object(cache_manager, "flush", AsyncMock()) as mock_flush:
            await scraper.clear_cache()
            mock_flush.assert_awaited_once()

    def test_get_stats_empty(self):
        scraper = _make_scraper()
        stats = scraper.get_stats()
        assert stats["name"] == "test"
        assert stats["requests"] == 0
        assert stats["errors"] == 0
        assert stats["cache_hit_rate"] == 0
        assert stats["success_rate"] == 0

    def test_get_stats_with_counts(self):
        scraper = _make_scraper()
        scraper._request_count = 10
        scraper._error_count = 2
        scraper._cache_hits = 5
        scraper._cache_misses = 5
        stats = scraper.get_stats()
        assert stats["cache_hit_rate"] == 50.0
        assert stats["success_rate"] == 80.0


class TestExtractSkills:
    def test_empty_text(self):
        scraper = _make_scraper()
        assert scraper._extract_skills("") == []
        assert scraper._extract_skills(None) == []

    def test_word_boundaries_no_false_positives(self):
        """Short skills must not match inside larger words."""
        scraper = _make_scraper()
        # 'Go' inside 'Google', 'C' inside 'Certificate', 'AWS' inside 'awesome'
        skills = scraper._extract_skills("Google Certificate program. Awesome workspace, awsome.")
        assert "Go" not in skills
        assert "C" not in skills
        assert "AWS" not in skills

    def test_standalone_skills_detected(self):
        scraper = _make_scraper()
        skills = scraper._extract_skills(
            "We need Python, AWS, Docker, Kubernetes and OWASP experience."
        )
        assert "Python" in skills
        assert "AWS" in skills
        assert "Docker" in skills
        assert "Kubernetes" in skills
        assert "OWASP" in skills

    def test_multiword_phrase_skills(self):
        scraper = _make_scraper()
        skills = scraper._extract_skills(
            "Experience with penetration testing and incident response is key. "
            "We value vulnerability assessment skills."
        )
        assert "Penetration Testing" in skills
        assert "Incident Response" in skills
        assert "Vulnerability Assessment" in skills

    def test_case_insensitive(self):
        scraper = _make_scraper()
        skills = scraper._extract_skills("python PYTHON Python")
        assert skills.count("Python") == 1

    def test_cpp_does_not_match_c(self):
        scraper = _make_scraper()
        skills = scraper._extract_skills("We use C++ and Java")
        assert "C++" in skills
        assert "C" not in skills  # 'C' should not be detected standalone from C++
        assert "Java" in skills


class TestRateLimitWait:
    @pytest.mark.asyncio
    async def test_rate_limit_zero_no_wait(self):
        scraper = _make_scraper(rate_limit=0)
        with patch("cybershield.scrapers.base.asyncio.sleep", AsyncMock()) as mock_sleep:
            await scraper._rate_limit_wait()
            mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rate_limit_waits_when_needed(self):
        scraper = _make_scraper(rate_limit=1.0)
        # Force elapsed to be tiny so a wait is required
        scraper._last_request_time = 9999999999.0
        with patch("cybershield.scrapers.base.asyncio.sleep", AsyncMock()) as mock_sleep:
            await scraper._rate_limit_wait()
            mock_sleep.assert_awaited()
