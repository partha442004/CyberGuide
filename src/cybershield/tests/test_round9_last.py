"""
Round 9 final-batch tests covering the last reachable uncovered branches:

- ``interntrack/scrapers/base.py`` (rate-limit default, client close, get/post)
- ``cybershield/api/v1/websocket.py`` (generic exception cleanup)
- ``cybershield/repositories/skill_repository.py`` (market data query)
- ``cybershield/repositories/job_repository.py`` (experience-level filter)
- ``cybershield/api/v1/jobs.py`` (experience-level filter)
- ``interntrack/scrapers/remoteok.py`` (limit break)
- ``interntrack/engines/deduplication.py`` (seen-pair skip)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _ConcreteBaseScraper:
    """Concrete stand-in mirroring the interntrack BaseScraper surface."""

    def __init__(self):
        from interntrack.scrapers.base import BaseScraper  # noqa: F401 (import check)

    @property
    def rate_limit(self):
        return 60

    async def close(self):
        pass


class TestInterntrackBaseScraperRound9:
    """rate-limit default, aclose, _get and _post on the interntrack base."""

    @pytest.fixture
    def scraper(self):
        from interntrack.scrapers.base import BaseScraper

        class _S(BaseScraper):
            @property
            def source_name(self):
                return "test"

            async def fetch(self, *args, **kwargs):
                return []

        return _S()

    def test_rate_limit_default(self, scraper):
        assert scraper.rate_limit == 60

    @pytest.mark.asyncio
    async def test_close_client(self, scraper):
        scraper.client = MagicMock()
        scraper.client.aclose = AsyncMock()
        await scraper.close()
        scraper.client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_and_post_delegate(self, scraper):
        response = MagicMock()
        scraper.client.get = AsyncMock(return_value=response)
        scraper.client.post = AsyncMock(return_value=response)

        got = await scraper._get("https://x.example", params={"q": "1"})
        posted = await scraper._post("https://x.example", json={"a": 1})

        assert got is response
        assert posted is response
        scraper.client.get.assert_awaited_once_with("https://x.example", params={"q": "1"})
        scraper.client.post.assert_awaited_once_with("https://x.example", json={"a": 1})


class TestWebsocketErrorPath:
    """A generic websocket exception cleans up the connection."""

    @pytest.mark.asyncio
    async def test_generic_exception_disconnects(self):
        import starlette.websockets

        from cybershield.api.v1 import websocket as ws_module

        websocket = MagicMock()
        websocket.send_json = AsyncMock()
        websocket.receive_text = AsyncMock(side_effect=RuntimeError("boom"))

        with (
            patch.object(ws_module, "ws_manager") as mock_manager,
            patch.object(ws_module, "logger"),
            patch.object(
                ws_module,
                "WebSocketDisconnect",
                starlette.websockets.WebSocketDisconnect,
            ),
        ):
            mock_manager.connect = AsyncMock(return_value="conn-1")
            mock_manager.disconnect = AsyncMock()
            await ws_module.websocket_endpoint(websocket, user_id="u1")

        mock_manager.disconnect.assert_called_once()
        assert mock_manager.disconnect.call_args.args[0] is websocket


class TestSkillRepositoryMarketData:
    """get_skill_market_data executes the aggregated query."""

    @pytest.mark.asyncio
    async def test_market_data_query(self):
        from cybershield.repositories.skill_repository import SkillRepository

        session = MagicMock()
        result = MagicMock()
        skill = MagicMock()
        skill.name = "Python"
        skill.id = 1
        row = MagicMock()
        row.__getitem__.side_effect = lambda idx: skill if idx == 0 else 5
        result.all.return_value = [row]
        session.execute = AsyncMock(return_value=result)

        repo = SkillRepository(session)
        data = await repo.get_skill_market_data()

        assert data[0]["skill"].name == "Python"
        assert data[0]["demand_count"] == 5


class TestJobRepositoryExperienceFilter:
    """get_all_jobs applies the experience-level filter."""

    @pytest.mark.asyncio
    async def test_experience_filter(self):
        from cybershield.repositories.job_repository import JobRepository

        session = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=result)

        repo = JobRepository(session)
        await repo.search_jobs(
            query_text="",
            country=None,
            job_type=None,
            experience_level="senior",
        )

        stmt = session.execute.await_args.args[0]
        assert "experience_level" in str(stmt)


class TestCybershieldJobsExperienceFilter:
    """list_jobs maps the experience_level query param into filters."""

    @pytest.mark.asyncio
    async def test_experience_filter(self):
        from cybershield.api.v1 import jobs as jobs_module

        repo = MagicMock()
        repo.get_all = AsyncMock(return_value=[])
        repo.count = AsyncMock(return_value=0)

        with patch.object(jobs_module, "JobRepository", return_value=repo):
            response = await jobs_module.list_jobs(
                country=None,
                job_type=None,
                experience_level="mid",
                skip=0,
                limit=20,
                repo=repo,
            )

        filters = repo.get_all.await_args.kwargs["filters"]
        assert filters["experience_level"] == "mid"
        assert response["total"] == 0


class TestRemoteokLimitBreak:
    """RemoteOK stops collecting once the limit is reached."""

    @pytest.mark.asyncio
    async def test_stops_at_limit(self):
        from interntrack.scrapers.remoteok import RemoteOKScraper

        scraper = RemoteOKScraper()
        job = MagicMock()
        job.title = "Security Engineer"
        job.company = "Acme"
        job.url = "https://remoteok.com/remote-jobs/1"
        scraper._parse_job = MagicMock(  # type: ignore[method-assign]
            return_value=job
        )
        scraper._get = AsyncMock(  # type: ignore[method-assign]
            return_value=MagicMock(
                status_code=200,
                json=lambda: [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}],
            )
        )

        jobs = await scraper.fetch("security", limit=2)

        assert len(jobs) == 2


class TestInterntrackDedupSeenPair:
    """find_duplicates_in_database skips an already-seen pair key."""

    @pytest.mark.asyncio
    async def test_seen_pair_skipped(self):
        from interntrack.engines.deduplication import DeduplicationEngine

        session = MagicMock()
        result = MagicMock()
        job_a = MagicMock()
        job_a.id = "x"
        job_b = MagicMock()
        job_b.id = "y"
        job_c = MagicMock()
        job_c.id = "x"  # same id as job_a -> pair (x, y) key repeats
        result.scalars.return_value.all.return_value = [job_a, job_b, job_c]
        session.execute = AsyncMock(return_value=result)

        engine = DeduplicationEngine(session)
        engine.calculate_similarity = MagicMock(  # type: ignore[method-assign]
            return_value=0.99
        )

        dupes = await engine.find_duplicates_in_database(threshold=0.9)

        # (a,b) and (b,c) share the sorted key ("x","y"); only one is kept.
        assert len(dupes) == 2
        assert engine.calculate_similarity.call_count == 2
