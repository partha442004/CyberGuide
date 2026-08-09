"""
Unit tests for the apna.co scraper.

The scraper parses Next.js `self.__next_f.push` flight payloads, where the
job data is double-escaped JSON. Fixtures below mimic that exact shape
(HTML-escaped backslashes inside a <script> block).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _payload_script(jobs_blob: str) -> str:
    """Wrap a jobsList JSON blob in the double-escaped flight-script shape."""
    # One level of escaping: " -> \\"  (the raw HTML contains \\" for a quote).
    escaped = jobs_blob.replace('"', '\\\\"')
    return (
        '<script>self.__next_f.push([1,"9:\\"jobFeedType\\\\":\\\\"'
        'PUBLIC_JOB_FEED_TYPE\\\\",\\\\"jobsList\\\\":'
        + escaped
        + '\\\\"}"]);</script>'
    )


_SAMPLE = (
    '[{"id":"$undefined","type":3,"data":{'
    '"jobID":154830089,'
    '"jobTitle":"SIEM & SOAR Subject Matter Expert",'
    '"jobOrganisationDetails":{"organisationName":"Techowl Infosec"},'
    '"jobPublicURL":"/job/chennai-region/siem-soar-subject-matter-expert-154830089",'
    '"jobSalaryRangeDetails":{"salaryMax":100000,"salaryMin":40000},'
    '"jobCardAddress":"Work From Home"},'
    '"id":"$undefined","type":3,"data":{'
    '"jobID":608389202,'
    '"jobTitle":"Customer Care Executive",'
    '"jobOrganisationDetails":{"organisationName":"M11 Insurance"},'
    '"jobPublicURL":"/job/amritsar/customer-care-executive-550776593",'
    '"jobSalaryRangeDetails":{"salaryMax":250000,"salaryMin":180000},'
    '"jobCardAddress":"Ranjit Avenue, Amritsar"}}]'
)


class TestApnaScraper:
    """Apna scraper parsing and URL building."""

    def _scraper(self):
        from interntrack.scrapers.apna import ApnaScraper

        return ApnaScraper()

    def test_source_name(self):
        assert self._scraper().source_name == "apna"

    def test_slug_building(self):
        s = self._scraper()
        assert s._slug("Cyber Security") == "cyber-security"
        assert s._slug("  python   developer ") == "python-developer"
        assert s._slug("!!!") == "jobs"

    def test_search_url_keyword_only(self):
        s = self._scraper()
        assert s._search_url("cyber security", None) == (
            "https://apna.co/jobs/cyber-security-jobs"
        )

    def test_search_url_with_location(self):
        s = self._scraper()
        assert s._search_url("cyber security", "Bengaluru") == (
            "https://apna.co/jobs/cyber-security-jobs-in-bengaluru-bangalore"
        )
        assert s._search_url("soc analyst", "Chennai") == (
            "https://apna.co/jobs/soc-analyst-jobs-in-chennai-region"
        )

    def test_search_url_unknown_location_ignored(self):
        s = self._scraper()
        assert s._search_url("cyber security", "Atlantis") == (
            "https://apna.co/jobs/cyber-security-jobs"
        )

    def test_fallback_query_maps_multi_word_to_curated(self):
        s = self._scraper()
        assert s._fallback_query("cybersecurity") == "security"
        assert s._fallback_query("soc analyst") == "security"
        assert s._fallback_query("cyber security") == "security"
        assert s._fallback_query("react developer") == "frontend developer"

    def test_fallback_query_none_for_curated_itself(self):
        s = self._scraper()
        assert s._fallback_query("security") is None
        assert s._fallback_query("sales") is None

    def test_fallback_query_strips_intern_suffix(self):
        s = self._scraper()
        # discovery_queries_for appends "<skill> intern" — those must still
        # resolve to the curated security feed.
        assert s._fallback_query("vapt intern") == "security"
        assert s._fallback_query("soc analyst intern") == "security"
        assert s._fallback_query("cybersecurity internship") == "security"

    def test_unescape_script(self):
        s = self._scraper()
        html = _payload_script(_SAMPLE)
        payload = s._unescape_script(html)
        assert '"jobID":154830089' in payload
        assert '"jobTitle":"SIEM & SOAR Subject Matter Expert"' in payload
        assert "jobsList" in payload

    def test_extract_field_pairs(self):
        s = self._scraper()
        html = _payload_script(_SAMPLE)
        payload = s._unescape_script(html)
        pairs = s._extract_field_pairs(payload)
        assert len(pairs) == 2
        first = pairs[0]
        assert first["title"] == "SIEM & SOAR Subject Matter Expert"
        assert first["organisation"] == "Techowl Infosec"
        assert first["salary_max"] == 100000
        assert first["salary_min"] == 40000
        assert first["address"] == "Work From Home"
        assert first["public_url"].endswith("154830089")

    @pytest.mark.asyncio
    async def test_fetch_parses_and_filters(self):
        from interntrack.scrapers.apna import ApnaScraper

        scraper = ApnaScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = _payload_script(_SAMPLE)
        with patch.object(scraper, "_get", new=AsyncMock(return_value=mock_resp)):
            # Real discovery queries are the security keyword alone (location
            # is passed separately); "security" expands to SIEM/SOAR/IR etc.
            jobs = await scraper.fetch("security", "Bengaluru", limit=10)

        # Only the SIEM job matches the query — the Customer Care Executive
        # listing is filtered out by matches_query.
        assert len(jobs) == 1
        job = jobs[0]
        assert job.title == "SIEM & SOAR Subject Matter Expert"
        assert job.company == "Techowl Infosec"
        assert job.source == "apna"
        assert job.salary_currency == "INR"
        assert job.salary_min == 40000
        assert job.salary_max == 100000
        assert job.is_remote is True
        assert job.url == (
            "https://apna.co/job/chennai-region/"
            "siem-soar-subject-matter-expert-154830089"
        )
        assert job.raw_data == {"apna_job_id": 154830089}

    @pytest.mark.asyncio
    async def test_fetch_non_200_returns_empty(self):
        from interntrack.scrapers.apna import ApnaScraper

        scraper = ApnaScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "forbidden"
        with patch.object(scraper, "_get", new=AsyncMock(return_value=mock_resp)):
            jobs = await scraper.fetch("cyber security")
        assert jobs == []

    @pytest.mark.asyncio
    async def test_fetch_no_payload_returns_empty(self):
        from interntrack.scrapers.apna import ApnaScraper

        scraper = ApnaScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>no jobs here</html>"
        with patch.object(scraper, "_get", new=AsyncMock(return_value=mock_resp)):
            jobs = await scraper.fetch("cyber security")
        assert jobs == []

    @pytest.mark.asyncio
    async def test_fetch_never_raises(self):
        from interntrack.scrapers.apna import ApnaScraper

        scraper = ApnaScraper()
        with patch.object(
            scraper, "_get", new=AsyncMock(side_effect=RuntimeError("boom"))
        ):
            jobs = await scraper.fetch("cyber security")
        assert jobs == []

    @pytest.mark.asyncio
    async def test_fetch_rejects_guard_roles(self):
        from interntrack.scrapers.apna import ApnaScraper

        scraper = ApnaScraper()
        mixed = _payload_script(
            '[{"id":"$undefined","type":3,"data":{'
            '"jobID":1,'
            '"jobTitle":"Security Head Ex-Army Man",'
            '"jobOrganisationDetails":{"organisationName":"Krish V Global"},'
            '"jobPublicURL":"/job/bengaluru-bangalore/security-head-ex-army-man-1",'
            '"jobCardAddress":"HBR Layout, Bengaluru"}},'
            '{"id":"$undefined","type":3,"data":{'
            '"jobID":2,'
            '"jobTitle":"SOC Analyst",'
            '"jobOrganisationDetails":{"organisationName":"Baroda Institute"},'
            '"jobPublicURL":"/job/vadodara/soc-analyst-2",'
            '"jobCardAddress":"Vadodara"}}]'
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = mixed
        with patch.object(scraper, "_get", new=AsyncMock(return_value=mock_resp)):
            jobs = await scraper.fetch("security", "Bangalore", limit=10)

        # Guard role filtered out; only the real SOC job survives.
        assert [j.title for j in jobs] == ["SOC Analyst"]

    @pytest.mark.asyncio
    async def test_fetch_uses_fallback_when_primary_empty(self):
        from interntrack.scrapers.apna import ApnaScraper

        scraper = ApnaScraper()
        empty_resp = MagicMock()
        empty_resp.status_code = 200
        empty_resp.text = _payload_script(
            '[{"id":"$undefined","type":3,"data":{'
            '"jobID":1,'
            '"jobTitle":"Sales Executive",'
            '"jobOrganisationDetails":{"organisationName":"Acme"},'
            '"jobPublicURL":"/job/delhi-ncr/sales-executive-1",'
            '"jobCardAddress":"Delhi"}}]'
        )
        good_resp = MagicMock()
        good_resp.status_code = 200
        good_resp.text = _payload_script(_SAMPLE)

        # First candidate (cybersecurity slug) -> no matches; the fallback
        # (security slug) -> real SIEM job. The fallback must be fetched.
        with patch.object(
            scraper, "_get", new=AsyncMock(side_effect=[empty_resp, good_resp])
        ):
            jobs = await scraper.fetch("cybersecurity", limit=10)

        assert len(jobs) == 1
        assert jobs[0].title == "SIEM & SOAR Subject Matter Expert"
        assert jobs[0].source == "apna"


class TestApnaInRegistry:
    """The apna scraper is registered and used by discovery."""

    def test_registry_contains_apna(self):
        from interntrack.scrapers.registry import get_default_registry

        registry = get_default_registry()
        assert "apna" in registry.list_sources()

    def test_discovery_sources_include_apna(self):
        from interntrack.api.v1.jobs import _DISCOVERY_SOURCES

        assert "apna" in _DISCOVERY_SOURCES
