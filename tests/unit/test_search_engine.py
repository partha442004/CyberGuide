"""
Unit tests for the search-engine discovery scraper.
"""


class TestSearchEngineScraper:
    def _scraper(self):
        from interntrack.scrapers.search_engine import SearchEngineScraper

        return SearchEngineScraper()

    def test_source_name(self):
        assert self._scraper().source_name == "search_engine"

    def test_result_links_decodes_ddg_redirect(self):
        s = self._scraper()
        import urllib.parse

        target = "https://in.linkedin.com/jobs/view/soc-analyst-123"
        encoded = urllib.parse.quote_plus(target)
        html = (
            f'<a class="result__a" href="//duckduckgo.com/l/?uddg={encoded}&amp;rut=x">'
            "SOC Analyst</a>"
            '<a class="result__a" href="https://example.com/direct">Direct</a>'
        )
        links = s._result_links(html)
        assert links[0] == target
        assert links[1] == "https://example.com/direct"

    def test_is_job_url(self):
        s = self._scraper()
        assert s._is_job_url("https://in.linkedin.com/jobs/view/soc-1")
        assert s._is_job_url("https://www.naukri.com/job-listings-pentest-1")
        assert s._is_job_url("https://careers.zscaler.com/positions/123")
        assert not s._is_job_url("https://en.wikipedia.org/wiki/Cybersecurity")
        assert not s._is_job_url("https://www.youtube.com/watch?v=abc")

    def test_parse_page_extracts_meta(self):
        s = self._scraper()
        html = (
            "<html><head>"
            '<meta property="og:title" content="SOC Analyst - Bangalore" />'
            '<meta property="og:site_name" content="Acme Corp" />'
            '<meta property="og:description" content="Monitor SIEM alerts." />'
            "</head></html>"
        )
        job = s._parse_page("https://example.com/job/1", html)
        assert job is not None
        assert job.title == "SOC Analyst - Bangalore"
        assert job.company == "Acme Corp"
        assert job.source == "search_engine"
        assert "SIEM" in (job.description or "")

    def test_parse_page_title_fallback(self):
        s = self._scraper()
        html = "<html><head><title>Security Engineer | Hiring Co</title></head></html>"
        job = s._parse_page("https://hiringco.example/careers/1", html)
        assert job is not None
        assert "Security Engineer" in job.title
        # No og:site_name -> host-derived company.
        assert job.company == "Hiringco"

    def test_parse_page_returns_none_without_title(self):
        s = self._scraper()
        assert (
            s._parse_page("https://example.com/x", "<html><body>hi</body></html>")
            is None
        )
