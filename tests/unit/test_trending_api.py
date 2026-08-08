"""Trending jobs + view-tracking API tests.

Covers ``GET /api/v1/jobs/trending`` (engagement ranking with a newest-job
fallback) and ``POST /api/v1/jobs/{job_id}/view`` (view_count increment that
feeds the ranking).
"""

import asyncio

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    """TestClient wired to a hermetic temp-file SQLite database.

    Mirrors tests/unit/test_api_v1_full.py: a throwaway file-backed SQLite
    engine plus a ``get_db`` dependency override so the endpoints are
    deterministic and CI-safe.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import interntrack.database.session as session_module
    from interntrack.database.session import get_db
    from interntrack.domain.models import Base
    from interntrack.main import app

    db_path = tmp_path / "test_trending.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    test_session_local = async_sessionmaker(engine, expire_on_commit=False)

    async def _init_tables() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init_tables())

    async def override_get_db():
        async with test_session_local() as session:
            # Mirror the real ``get_db`` (session.py) which commits after
            # the request — without the commit, created rows never persist
            # and later requests can't see them.
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db

    original_factory = session_module.async_session_factory
    session_module.async_session_factory = test_session_local

    try:
        yield TestClient(app)
    finally:
        session_module.async_session_factory = original_factory
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())


def _create_job(client: TestClient, title: str, company: str = "Acme") -> str:
    """Create a job via the API and return its id."""
    resp = client.post(
        "/api/v1/jobs/",
        json={
            "title": title,
            "company": company,
            "url": f"https://example.com/{title}",
        },
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


class TestViewTracking:
    """POST /api/v1/jobs/{job_id}/view."""

    def test_view_increments_count(self, client):
        job_id = _create_job(client, "Security Engineer")
        assert client.post(f"/api/v1/jobs/{job_id}/view").json()["view_count"] == 1
        assert client.post(f"/api/v1/jobs/{job_id}/view").json()["view_count"] == 2
        # The count is persisted and surfaced on the job detail.
        detail = client.get(f"/api/v1/jobs/{job_id}").json()
        assert detail["view_count"] == 2

    def test_view_missing_job_404(self, client):
        resp = client.post("/api/v1/jobs/no-such-job/view")
        assert resp.status_code == 404


class TestTrending:
    """GET /api/v1/jobs/trending."""

    def test_empty_database(self, client):
        resp = client.get("/api/v1/jobs/trending")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trending"] == []
        assert body["total"] == 0

    def test_fallback_to_newest_when_no_engagement(self, client):
        _create_job(client, "VAPT Analyst")
        _create_job(client, "SOC Analyst L2")
        body = client.get("/api/v1/jobs/trending?days=14&limit=8").json()
        titles = [t["title"] for t in body["trending"]]
        assert "VAPT Analyst" in titles
        assert "SOC Analyst L2" in titles
        # All engagement 0 in a fresh DB — the endpoint still returns them.
        assert all(t["engagement_score"] == 0 for t in body["trending"])

    def test_applied_job_ranks_first(self, client):
        hot_id = _create_job(client, "Hot Security Role")
        _create_job(client, "Quiet Data Role")
        # Two different people applied to the hot job (the endpoint is
        # idempotent per user, so distinct user_ids are required).
        for user in ("user-a", "user-b"):
            resp = client.post(
                "/api/v1/applications/",
                json={"job_id": hot_id, "user_id": user},
            )
            assert resp.status_code in (200, 201), resp.text
        body = client.get("/api/v1/jobs/trending").json()
        assert body["total"] > 0
        first = body["trending"][0]
        assert first["id"] == hot_id
        assert first["applications"] == 2
        assert first["engagement_score"] >= 6  # 2 apps * 3

    def test_views_raise_score(self, client):
        job_id = _create_job(client, "Viewed Role")
        client.post(f"/api/v1/jobs/{job_id}/view")
        client.post(f"/api/v1/jobs/{job_id}/view")
        body = client.get("/api/v1/jobs/trending").json()
        hit = next(t for t in body["trending"] if t["id"] == job_id)
        assert hit["views"] == 2
        assert hit["engagement_score"] == 1.0  # 2 views * 0.5
