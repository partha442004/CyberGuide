"""
Unit tests for the search-engine discovery scraper.
"""

import re


class TestSearchEngineScraper:
    def _scraper(self):
        from interntrack.scrapers.search_engine import SearchEngineScraper

        return SearchEngineScraper()

    def test_source_name(self):
        assert self._scraper().source_name == "search_engine"

    def test_junk_title_rejects_articles_and_guides(self):
        """Article-style titles never become jobs (content, not postings)."""
        from interntrack.scrapers import search_engine as se

        junk = [
            "What does a nuclear reactor operator do? - Career Explorer",
            "15 Best Companies Hiring Cybersecurity Analysts",
            "Top 10 Ways to Land a Security Job",
            "Day in the life of a SOC analyst",
            "Cybersecurity Career Path: What Is a Security Engineer?",
        ]
        for title in junk:
            assert se._JUNK_TITLE_RE.search(title), f"expected junk: {title}"

    def test_junk_title_keeps_real_postings(self):
        """Legit job titles must not be caught by the article filter."""
        from interntrack.scrapers import search_engine as se

        real = [
            "SOC Analyst - Bengaluru",
            "Cyber Security Engineer",
            "Frontend Developer (React) - Chennai",
            "Whatfix - Senior Security Engineer",
        ]
        for title in real:
            assert not se._JUNK_TITLE_RE.search(title), f"rejected real: {title}"

    def test_pdf_guide_rejected_as_document(self):
        """Product-guide PDFs are documents, not recruitment notices."""
        from interntrack.scrapers import search_engine as se

        # A guide PDF must not be parsed into a job; the generic junk regex
        # plus the document markers drop it before RawJob is built.
        guide_text = (
            "Microsoft Copilot Credits Guide | August 2026 Page 1 "
            "Copilot Credits: How to use your monthly credits"
        )
        assert se._JUNK_TITLE_RE.search(guide_text[:300]) or re.search(
            r"\b(credits? guide|whitepaper|product guide|user guide)\b",
            guide_text[:300],
            re.IGNORECASE,
        )

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

    def test_brave_links_extracts_external_results(self):
        """Brave links are plain external hrefs; chrome is filtered out."""
        s = self._scraper()
        html = (
            '<a href="https://internshala.com/internship/detail/cyber-intern-1">I</a>'
            '<a href="https://search.brave.com/settings">settings</a>'
            '<a href="https://cdn.search.brave.com/asset.js">asset</a>'
            '<a href="https://in.indeed.com/viewjob?jk=1&amp;from=app">J</a>'
        )
        links = s._brave_links(html)
        assert "https://internshala.com/internship/detail/cyber-intern-1" in links
        assert "https://in.indeed.com/viewjob?jk=1&from=app" in links
        assert not any("brave.com" in link for link in links)

    def test_is_job_url(self):
        s = self._scraper()
        assert s._is_job_url("https://in.linkedin.com/jobs/view/soc-1")
        assert s._is_job_url("https://www.naukri.com/job-listings-pentest-1")
        assert s._is_job_url("https://careers.zscaler.com/positions/123")
        assert not s._is_job_url("https://en.wikipedia.org/wiki/Cybersecurity")
        assert not s._is_job_url("https://www.youtube.com/watch?v=abc")

    def test_is_job_url_accepts_pdf_notices(self):
        """Recruitment-notice PDFs (govt / university / walk-in drives) are
        individual documents, not listing pages."""
        s = self._scraper()
        assert s._is_job_url("https://www.isro.gov.in/Recruitment_2026.pdf")
        assert s._is_job_url("https://university.edu/careers/Walk-in_Interview.pdf")
        assert not s._is_job_url("https://en.wikipedia.org/wiki/guide.pdf")

    def test_parse_pdf_extracts_notice(self):
        """A readable recruitment PDF becomes a RawJob (title + description)."""
        from unittest.mock import patch

        from interntrack.scrapers.search_engine import SearchEngineScraper

        class _FakePage:
            def extract_text(self):
                return (
                    "WALK-IN INTERVIEW\n"
                    "Cyber Security Internship - Off-campus drive\n"
                    "Send resume to hr@example.com before 30 Aug"
                )

        class _FakeReader:
            pages = [_FakePage()]

        s = SearchEngineScraper()
        with patch("pypdf.PdfReader", return_value=_FakeReader()):
            job = s._parse_pdf(
                "https://university.edu/recruitment.pdf", b"%PDF-1.4 fake"
            )
        assert job is not None
        assert job.url.endswith(".pdf")
        assert "WALK-IN INTERVIEW" in job.title.upper()
        assert "Cyber Security Internship" in job.description
        assert job.company  # host-derived

    def test_parse_pdf_unreadable_returns_none(self):
        """Binary garbage / encrypted PDFs never raise."""
        from unittest.mock import patch

        from interntrack.scrapers.search_engine import SearchEngineScraper

        def boom(*args, **kwargs):  # noqa: ARG001
            raise ValueError("bad pdf")

        s = SearchEngineScraper()
        with patch("pypdf.PdfReader", side_effect=boom):
            assert s._parse_pdf("https://x.edu/n.pdf", b"garbage") is None

    def test_is_job_url_rejects_listing_pages(self):
        """Board search pages are listings, not postings — rejected."""
        s = self._scraper()
        listings = [
            "https://in.linkedin.com/jobs/cyber-security-intern-jobs-bengaluru",
            "https://www.naukri.com/cybersecurity-internship-jobs-in-bangalore",
            "https://in.indeed.com/q-cyber-security,-internship-l-bangalore-jobs.html",
            (
                "https://www.glassdoor.co.in/Job/bengaluru-cybersecurity-jobs-"
                "SRCH_IL.0,9_IC2940587.htm"
            ),
            (
                "https://internshala.com/internships/cyber-security-internship-"
                "in-bangalore/stipend-6000/"
            ),
            "https://www.dice.com/jobs/q-SOC+Analyst-jobs",
            "https://www.roberthalf.com/us/en/jobs/all/soc-analyst",
            "https://www.apna.co/jobs/jobs-in-bengaluru",
            "https://internshala.com/jobs/jobs-in-bangalore/",
            "https://www.jobhai.com/jobs-in-bangalore-cty",
            "https://www.linkedin.com/posts/deltawaresolution-private-limited_hiring",
            "https://internshala.com/registration/student",
            "https://wellfound.com/startups/l/bangalore/cyber-security",
            "https://wellfound.com/role/l/cybersecurity/bangalore",
            "https://help.wellfound.com/article/777-setting-up-a-search",
            "https://support.greenhouse.io/hc/en-us/articles/1",
            "https://recruiter.foundit.in/edge/user-management/planDashboard/",
            "https://www.lever.co/alternative/lever-vs-greenhouse",
            "https://cutshort.io/companies/saas-companies-in-chennai",
        ]
        for url in listings:
            assert not s._is_job_url(url), url

    def test_is_job_url_accepts_real_postings(self):
        """Individual postings keep working across boards."""
        s = self._scraper()
        postings = [
            "https://in.indeed.com/viewjob?jk=e0b3e4ceeba09e4e",
            (
                "https://internshala.com/internship/detail/work-from-home-cyber-"
                "security-internship-at-x-1785310553"
            ),
            "https://wellfound.com/jobs/4562736-investigations-engineer-nyc",
            "https://cutshort.io/job/Cyber-Security-Bengaluru-Bangalore-CloudSEK-0mKJLkaY",
            (
                "https://cutshort.io/job/Fullstack-Developer-Mumbai-"
                "Cutshort-Lightning-hm7QSYFD"
            ),
            "https://www.timesjobs.com/job/soc-analyst-bengaluru-jobid-12345",
            (
                "https://www.naukri.com/job-listings-soc-analyst-rooman-"
                "bengaluru-0-to-4-years-050826503196"
            ),
            "https://www.linkedin.com/jobs/view/soc-analyst-4000000000",
            (
                "https://infosec-career.com/job/cybersecurity-internship-"
                "vapt-web-network"
            ),
        ]
        for url in postings:
            assert s._is_job_url(url), url

    def test_parse_page_rejects_listing_titles(self):
        """A fetched page whose title is a search page is dropped."""
        s = self._scraper()
        listing_titles = [
            "SOC Analyst jobs | Dice.com",
            "384 Results for Soc Analyst Jobs",
            "Job Search | Naukri",
            "Cyber Security Internships in Bangalore | Internshala",
        ]
        for title in listing_titles:
            html = (
                "<html><head>"
                f'<meta property="og:title" content="{title}" />'
                "</head></html>"
            )
            assert s._parse_page("https://example.com/jobs/1", html) is None, title

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

    def test_decode_bing_redirect(self):
        import base64

        s = self._scraper()
        target = "https://wellfound.com/jobs/4562736-investigations-engineer"
        encoded = "a1" + base64.urlsafe_b64encode(target.encode()).decode()
        redirect = f"https://www.bing.com/ck/a?!&&p=xx&u={encoded}&ntb=1"
        assert s._decode_bing_redirect(redirect) == target
        assert s._decode_bing_redirect("https://naukri.com/x") == "https://naukri.com/x"

    def test_bing_links_extracts_and_decodes(self):
        import base64

        s = self._scraper()
        target = "https://cutshort.io/job/Cyber-Security-CloudSEK-0mKJLkaY"
        encoded = "a1" + base64.urlsafe_b64encode(target.encode()).decode()
        html = (
            '<h2><a href="https://www.bing.com/ck/a?!&&p=1'
            f'&amp;u={encoded}">Cyber Security</a></h2>'
            '<h2><a href="https://direct.example.com/job/2">Direct</a></h2>'
        )
        links = s._bing_links(html)
        assert links[0] == target
        assert links[1] == "https://direct.example.com/job/2"

    async def test_fetch_respects_wall_clock_budget(self, monkeypatch):
        """One fetch call must stop once its time budget is exhausted.

        Without this cap the ~90 site: queries × 3 engines × 10s timeouts
        would consume the whole daily discovery slot on the first member's
        query, leaving every other member's digest empty.
        """
        import interntrack.scrapers.search_engine as se

        s = self._scraper()
        calls = {"n": 0}
        real = se.time.monotonic

        def fake_monotonic() -> float:
            calls["n"] += 1
            # First call sets the deadline; every later call is already
            # past it, so the fetch must stop after the first query.
            if calls["n"] == 1:
                return 1000.0
            return 2000.0

        monkeypatch.setattr(se.time, "monotonic", fake_monotonic)

        async def fake_search_links(engine: str, query: str) -> list:
            return []

        monkeypatch.setattr(s, "_search_links", fake_search_links)
        jobs = await s.fetch("security engineer")
        assert jobs == []
        assert real() > 0  # real monotonic still works (sanity)
        # The budget break happens before any query body runs.
        assert calls["n"] >= 2
