"""Unit tests for the search-engine scraper's query generation.

The scraper is a discovery net that asks DuckDuckGo/Bing for ``site:``
queries per board. These tests lock the query list so India-focused boards
(Naukri, Shine, Freshersworld, Unstop, Cutshort, Wellfound, Foundit,
TimesJobs, Hirect) keep getting surfaced even as the scraper evolves.
"""

import pytest

from interntrack.scrapers.search_engine import SearchEngineScraper


class _FakeResponse:
    """Minimal page response for the scraper's ``_get`` calls."""

    status_code = 200

    def __init__(self, text: str = ""):
        self.text = text


async def _fake_get(url: str, timeout: int = 10):  # noqa: ARG001 - scraper API shape
    """Fake ``_get`` returning a parseable job page for any URL."""
    return _FakeResponse(
        "<html><head>"
        "<meta property='og:title' content='Security Engineer'>"
        "<meta property='og:site_name' content='SecureCo'>"
        "</head></html>"
    )


class TestSearchEngineContentFilter:
    """The search engine must never save content articles as jobs."""

    def test_article_url_blocked(self):
        """LinkedIn Pulse / article URLs are content, not postings."""
        scraper = SearchEngineScraper()
        assert not scraper._is_job_url(
            "https://www.linkedin.com/pulse/15-best-chess-opening-moves/"
        )
        assert not scraper._is_job_url(
            "https://www.linkedin.com/posts/company/some-article-123"
        )
        assert scraper._is_job_url("https://www.linkedin.com/jobs/view/3987654321/")

    def test_junk_article_title_rejected(self):
        """Content-mill titles ("N Best ... You Must Know") are dropped."""
        scraper = SearchEngineScraper()
        for title in (
            "15 Best Chess Opening Moves That You Absolutely Must Know",
            "Top 10 Skills to Land a Cyber Security Job",
            "How to Become a SOC Analyst in 2026",
            "7 Tips for Acing Your Security Interview",
            "The Ultimate Guide to Networking",
        ):
            page = (
                "<html><head>"
                f'<meta property="og:title" content="{title}">'
                '<meta property="og:site_name" content="LinkedIn">'
                "</head></html>"
            )
            assert scraper._parse_page("https://x.com/job", page) is None, title

    def test_real_job_title_kept(self):
        """A genuine job title still parses into a RawJob."""
        scraper = SearchEngineScraper()
        page = (
            "<html><head>"
            '<meta property="og:title" content="SOC Analyst">'
            '<meta property="og:site_name" content="SecureCo">'
            "</head></html>"
        )
        job = scraper._parse_page("https://x.com/job", page)
        assert job is not None
        assert job.title == "SOC Analyst"
        assert job.company == "SecureCo"


class TestSearchEngineQueries:
    """Tests for the generated search queries."""

    @pytest.mark.asyncio
    async def test_includes_indian_job_boards(self):
        """Naukri + friends must appear in the site: query list."""
        scraper = SearchEngineScraper()
        seen: list[str] = []

        async def fake_search(engine: str, query: str) -> list[str]:
            seen.append(query)
            return []

        scraper._search_links = fake_search  # type: ignore[method-assign]
        jobs = await scraper.fetch("cybersecurity", "Bangalore", limit=8)

        assert jobs == []
        assert seen, "scraper never issued a query"
        joined = " ".join(seen)
        # Every India-focused board in _JOB_HOSTS must be queryable.
        for host in (
            "site:naukri.com",
            "site:shine.com",
            "site:freshersworld.com",
            "site:unstop.com",
            "site:cutshort.io",
            "site:wellfound.com",
            "site:foundit.in",
            "site:timesjobs.com",
            "site:hirect.in",
            "site:jobdexo.com",
            "site:instahyre.com",
            "site:hirist.com",
            # Cybersecurity-specific boards.
            "site:cybersecurityjobs.com",
            "site:cybersecurityjobsite.com",
            "site:cybersn.com",
            "site:clearedjobs.net",
            "site:infosec-jobs.com",
            "site:securityjobs.net",
            "site:ninjajobs.com",
            "site:techfetch.com",
            # ATS career boards + extra India boards.
            "site:boards.greenhouse.io",
            "site:jobs.lever.co",
            "site:jobs.ashbyhq.com",
            "site:careers.smartrecruiters.com",
            "site:glassdoor.co.in",
            "site:careerbuilder.co.in",
            "site:monsterindia.com",
            "site:jobhai.com",
            # Government / sarkari job portals.
            "site:sarkariresult.com",
            "site:freejobalert.com",
            "site:sarkariexam.com",
            "site:sarkarijobfind.com",
            "site:indgovtjobs.in",
            # Job aggregators.
            "site:simplyhired.co.in",
            "site:jooble.org",
            "site:talent.com",
            "site:careerjet.in",
            "site:adzuna.in",
            "site:ziprecruiter.com",
            "site:jora.com",
            "site:trovit.co.in",
            "site:careerbliss.com",
            "site:careerage.com",
            # Remote-first boards.
            "site:remote.co",
            "site:jobspresso.co",
            "site:workingnomads.com",
            "site:flexjobs.com",
            "site:virtualvocations.com",
            "site:nordesk.io",
            "site:justremote.co",
            "site:remoteok.com",
            "site:authenticjobs.com",
            "site:pangian.com",
            # More India boards + student platforms.
            "site:fresherslive.com",
            "site:workindia.in",
            "site:youth4work.com",
            "site:placementindia.com",
            "site:prosple.com",
            "site:twenty19.com",
            "site:letsintern.com",
            "site:hellointern.com",
            # More cybersecurity boards.
            "site:cybersecpeople.com",
            "site:cybersec4u.com",
            "site:dice.com",
            # More India boards + govt portals.
            "site:careernet.co.in",
            "site:iimjobs.com",
            "site:aasaanjobs.com",
            "site:rojgarresult.com",
            "site:employmentnews.gov.in",
            "site:apprenticeshipindia.gov.in",
            # Global boards.
            "site:themuse.com",
            "site:builtin.com",
            "site:jobrapido.com",
            "site:jobserve.com",
            # Startup / tech boards.
            "site:workatastartup.com",
            "site:otta.com",
            "site:landing.jobs",
            "site:turing.com",
            "site:gun.io",
            "site:usebraintrust.com",
            # Bug bounty / security communities.
            "site:hackerone.com",
            "site:bugcrowd.com",
            "site:intigriti.com",
            "site:isc2.org",
            "site:sans.org",
            # Research / academic.
            "site:researchgate.net",
            "site:nature.com/naturecareers",
            "site:jobs.ac.uk",
            "site:acm.org",
            # More remote boards.
            "site:jobicy.com",
            "site:remotejobs.com",
            "site:skipthedrive.com",
            # ATS career portals.
            "site:myworkdayjobs.com",
            "site:icims.com/jobs",
            "site:jobvite.com",
            "site:taleo.net",
            "site:successfactors.eu",
            "site:recruitee.com",
            "site:pinpoint.world",
            "site:teamtailor.com",
            "site:jazzhr.com",
            "site:breezy.hr",
            "site:bamboohr.com/jobs",
        ):
            assert host in joined, f"missing {host} in search queries"

    @pytest.mark.asyncio
    async def test_location_appended_to_query(self):
        """Location is folded into the base query so results are city-scoped."""
        scraper = SearchEngineScraper()
        seen: list[str] = []

        async def fake_search(engine: str, query: str) -> list[str]:
            seen.append(query)
            return []

        scraper._search_links = fake_search  # type: ignore[method-assign]
        await scraper.fetch("soc analyst", "Chennai", limit=8)

        assert seen
        assert any("soc analyst chennai" in q.lower() for q in seen)

    @pytest.mark.asyncio
    async def test_generic_query_kept_first(self):
        """The plain 'job OR vacancy' query runs first (broad net)."""
        scraper = SearchEngineScraper()
        seen: list[str] = []

        async def fake_search(engine: str, query: str) -> list[str]:
            seen.append(query)
            return []

        scraper._search_links = fake_search  # type: ignore[method-assign]
        await scraper.fetch("frontend", "Pune", limit=8)

        assert seen
        assert "job or vacancy or opening" in seen[0].lower()

    @pytest.mark.asyncio
    async def test_linkedin_surface_queries(self):
        """LinkedIn is auth-walled from datacenter IPs — the search engine
        must carry explicit ``site:linkedin.com/jobs`` queries so posting
        URLs still surface and the biggest source stays fresh."""
        scraper = SearchEngineScraper()
        seen: list[str] = []

        async def fake_search(engine: str, query: str) -> list[str]:
            seen.append(query)
            return []

        scraper._search_links = fake_search  # type: ignore[method-assign]
        await scraper.fetch("security", "Bangalore", limit=8)

        assert seen
        joined = " ".join(seen)
        assert "site:linkedin.com/jobs" in joined
        assert "site:in.linkedin.com/jobs" in joined
        # The query still carries the domain + location context.
        assert any("security" in q.lower() and "bangalore" in q.lower() for q in seen)

    @pytest.mark.asyncio
    async def test_per_query_budget_keeps_board_queries_live(self):
        """A productive generic query must not eat the whole limit — each
        board-specific ``site:`` query keeps its own slice, so LinkedIn /
        Naukri / cyber-board postings still surface even when the first
        query returns jobs."""
        scraper = SearchEngineScraper()
        calls: list[str] = []

        async def fake_search(engine: str, query: str) -> list[str]:
            calls.append(query)
            # Only the generic query "job OR vacancy" returns any links;
            # if the budget works, the loop still moves on to the later
            # site: queries instead of stopping at the limit.
            if "job or vacancy" in query.lower():
                return [
                    "https://www.linkedin.com/jobs/view/123",
                    "https://www.linkedin.com/jobs/view/124",
                    "https://www.linkedin.com/jobs/view/125",
                ]
            return []

        scraper._search_links = fake_search  # type: ignore[method-assign]
        scraper._get = _fake_get  # type: ignore[method-assign]
        await scraper.fetch("security", "Bangalore", limit=8)

        joined = " ".join(calls)
        # The board-specific queries must still have been issued even though
        # the generic one produced (3) jobs — per-query budget keeps them.
        assert "site:linkedin.com/jobs" in joined
        assert "site:naukri.com" in joined
        assert "site:cybersecurityjobs.com" in joined

    @pytest.mark.asyncio
    async def test_internship_board_query_and_brave_engine(self):
        """Internship boards are queried explicitly, and the Brave engine
        is attempted after DDG/Bing so intern postings keep surfacing."""
        scraper = SearchEngineScraper()
        engines: list[str] = []
        seen: list[str] = []

        async def fake_search(engine: str, query: str) -> list[str]:
            engines.append(engine)
            seen.append(query)
            return []

        scraper._search_links = fake_search  # type: ignore[method-assign]
        await scraper.fetch("internship", "Chennai", limit=8)

        assert engines, "no engine was tried"
        assert "brave" in engines, "brave engine missing from the fallback chain"
        joined = " ".join(seen)
        assert "site:internshala.com" in joined
        assert "site:in.indeed.com/internships" in joined
