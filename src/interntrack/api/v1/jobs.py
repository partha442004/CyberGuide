"""
Jobs API endpoints.
"""

import asyncio
import contextlib
import re
import time

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.job import (
    JobCreate,
    JobImportLinksRequest,
    JobListResponse,
    JobResponse,
    JobSearchRequest,
    JobShareRequest,
    JobStatistics,
    JobUpdate,
)
from interntrack.database.session import get_db
from interntrack.domain.exceptions import DuplicateJobError
from interntrack.repositories.job_repository import JobRepository
from interntrack.services.job_service import JobService

router = APIRouter()

# Vercel serverless functions are killed at maxDuration (60s on Hobby), so
# discovery must stay well under that. Running every registered scraper per
# query is too slow — the US geo-locked guest APIs (linkedin, indeed,
# glassdoor, hired, angellist, the *_api scrapers) carry 15-30s timeouts and
# dominate wall time. Discovery instead runs this curated set of fast /
# India-relevant sources; users still get US/global roles via the digest's
# RSS feeds, Greenhouse vendor boards and the share endpoint.
_DISCOVERY_SOURCES: list[str] = [
    "indeed_india",
    "linkedin_india",
    "timesjobs",
    "apna",
    "naukri",
    "glassdoor_india",
    "internshala",
    "google_jobs",
    "wellfound",
    "unstop",
    "freshersworld",
    "cutshort",
    "foundit",
    "rss_feed",
    "hackernews",
    "company",
    "search_engine",
]

# Total wall-clock budget (seconds) for one discovery request. Kept at 40s so
# the endpoint always returns a (possibly partial) result before Vercel's
# 60s hard kill, even after a cold start.
_DISCOVERY_DEADLINE_SECONDS = 40


# Indian cities (plus common aliases) recognized inside discovery queries so
# the right scrapers target them. e.g. "cybersecurity bangalore" resolves to
# query="cybersecurity", location="Bangalore".
_INDIA_LOCATIONS: dict[str, str] = {
    "bangalore": "Bangalore",
    "bengaluru": "Bangalore",
    "mumbai": "Mumbai",
    "bombay": "Mumbai",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "hyderabad": "Hyderabad",
    "pune": "Pune",
    "chennai": "Chennai",
    "kolkata": "Kolkata",
    "noida": "Noida",
    "gurgaon": "Gurgaon",
    "gurugram": "Gurgaon",
    "india": "India",
}


def _extract_location_from_query(query: str) -> str | None:
    """Return the Indian city found in ``query`` (or None).

    Uses whole-word matching so "india" doesn't match "indianapolis". Does
    not modify the query itself — the caller decides whether to keep the city
    words in the keyword string (harmless, and the India scrapers accept
    them either way).
    """
    lowered = (query or "").lower()
    for alias, canonical in _INDIA_LOCATIONS.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return canonical
    return None


def _strip_location_from_query(query: str) -> str:
    """Remove India city words from a query keyword.

    The user's city is passed to the scrapers separately via the ``location``
    arg, so leaving "bengaluru" inside the keyword hurts scrapers that match
    the whole string against role titles — vendor Greenhouse boards, RSS
    feeds and HackerNews carry US/remote roles that never contain the user's
    city, and a "cybersecurity bengaluru" keyword returns nothing from them.
    """
    cleaned = query
    for alias in _INDIA_LOCATIONS:
        cleaned = re.sub(
            rf"\b{re.escape(alias)}\b",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
    cleaned = " ".join(cleaned.split())
    return cleaned or query


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    job_type: str | None = None,
    is_remote: bool | None = None,
    company: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List jobs with filters."""
    from interntrack.domain.enums import JobType

    service = JobService(db)
    parsed_job_type = None
    if job_type:
        try:
            parsed_job_type = JobType(job_type)
        except ValueError:
            parsed_job_type = None
    jobs = await service.get_jobs(
        skip=skip,
        limit=limit,
        job_type=parsed_job_type,
        is_remote=is_remote,
        company=company,
    )
    total = await service.job_repo.count({"is_active": True})
    return JobListResponse(jobs=jobs, total=total, skip=skip, limit=limit)


@router.post("/backfill-job-types")
async def backfill_job_types(
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    """Infer job_type for existing jobs still marked unknown.

    Scrapers rarely set job_type, so new jobs get it inferred at save
    time; this backfills older rows so the dashboard job-type chart and
    filters show meaningful categories.
    """
    repo = JobRepository(db)
    updated = await repo.backfill_job_types(limit=limit)
    return {"updated": updated}


@router.post("/backfill-tags")
async def backfill_job_tags(
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    """Auto-tag existing jobs saved before auto-tagging existed.

    Jobs with empty ``tags`` score ``match_score: null`` against every
    resume; this derives skill tags from their title + description so
    they earn real match/ATS scores, matching what new saves already do.
    """
    repo = JobRepository(db)
    updated = await repo.backfill_job_tags(limit=limit)
    return {"updated": updated}


@router.post("/backfill-engagement")
async def backfill_engagement(
    limit: int = Query(1000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Seed view_count from real application / bookmark activity.

    Jobs saved before view tracking existed carry ``view_count = 0`` even
    when people applied to or bookmarked them, so 🔥 Trending under-ranks
    them. Each application or bookmark implies at least one view, so this
    backfills ``view_count = max(current, applications + bookmarks)`` for
    the most recent active rows.
    """
    repo = JobRepository(db)
    updated = await repo.backfill_engagement(limit=limit)
    return {"updated": updated}


@router.post("/enrich/run")
async def run_skill_enrichment(
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Backfill tags/required_skills from job descriptions.

    Jobs saved without structured skills score ``match_score: null`` against
    every resume. This sweep derives skills from the description text so
    those jobs become matchable. Returns how many jobs were enriched.
    """
    from interntrack.scheduler.jobs import enrich_jobs_for_match

    updated = await enrich_jobs_for_match(db, limit=limit)
    return {"enriched": updated}


@router.post("/archive-expired")
async def archive_expired(days: int = 30, db: AsyncSession = Depends(get_db)):
    """Archive jobs older than N days to keep the database lean."""
    repo = JobRepository(db)
    count = await repo.archive_expired_jobs(days=days)
    return {
        "archived": count,
        "message": f"Archived {count} jobs older than {days} days",
    }


@router.get("/expired")
async def list_expired(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """List archived expired jobs."""
    repo = JobRepository(db)
    expired = await repo.get_expired_jobs(limit=limit)
    return {
        "expired_jobs": [
            {
                "id": e.id,
                "title": e.title,
                "company": e.company,
                "location": e.location,
                "source": e.source,
                "expired_at": str(e.expired_at) if e.expired_at else None,
                "reason": e.reason,
            }
            for e in expired
        ],
        "total": len(expired),
    }


@router.get("/trending")
async def trending_jobs(
    days: int = Query(14, ge=1, le=90),
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Engagement-ranked trending jobs from the last N days.

    Score = 3 per application + 2 per bookmark + 0.5 per view, so the jobs
    the team is actually applying to / saving / opening float to the top.
    When nothing has engagement yet (fresh database), falls back to the
    newest jobs so the section is never empty. Registered BEFORE
    ``/{job_id}`` on purpose — ``/trending`` is a single segment and would
    otherwise be swallowed by the detail route.
    """
    from datetime import timedelta

    from sqlalchemy import func, or_, select

    from interntrack.domain.models import Application, Bookmark, Job
    from interntrack.utils.helpers import utcnow

    cutoff = utcnow() - timedelta(days=days)
    # Jobs with a NULL ``first_seen_at`` (rows saved before the column
    # existed, or scrapes that never set it) are treated as in-window too,
    # mirroring the repository's ``get_fresh_jobs`` pattern — otherwise
    # legacy high-engagement jobs could never trend.
    rows = (
        (
            await db.execute(
                select(Job)
                .where(
                    Job.is_active.is_(True),
                    or_(
                        Job.first_seen_at.is_(None),
                        Job.first_seen_at >= cutoff,
                    ),
                )
                .order_by(Job.first_seen_at.desc().nulls_last())
            )
        )
        .scalars()
        .all()
    )

    if not rows:
        return {"trending": [], "window_days": days, "total": 0}

    job_ids = [j.id for j in rows]
    app_rows = (
        await db.execute(
            select(Application.job_id, func.count(Application.id))
            .where(Application.job_id.in_(job_ids))
            .group_by(Application.job_id)
        )
    ).all()
    app_counts: dict[str, int] = {str(rid): int(cnt) for rid, cnt in app_rows}
    bm_rows = (
        await db.execute(
            select(Bookmark.item_id, func.count(Bookmark.id))
            .where(Bookmark.item_type == "job", Bookmark.item_id.in_(job_ids))
            .group_by(Bookmark.item_id)
        )
    ).all()
    bm_counts: dict[str, int] = {str(rid): int(cnt) for rid, cnt in bm_rows}

    scored = []
    for job in rows:
        views = int(job.view_count or 0)
        apps = int(app_counts.get(str(job.id), 0))
        bms = int(bm_counts.get(str(job.id), 0))
        scored.append((apps * 3 + bms * 2 + views * 0.5, job))

    scored.sort(key=lambda item: item[0], reverse=True)

    trending = []
    for score, job in scored[:limit]:
        # Recompute per job — reusing the scoring-loop locals would leak the
        # last-scored job's counts into every row.
        trending.append(
            {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "source": job.source.value if job.source else "unknown",
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "salary_currency": job.salary_currency,
                "is_remote": job.is_remote,
                "posted_at": str(job.posted_at) if job.posted_at else None,
                "first_seen_at": str(job.first_seen_at) if job.first_seen_at else None,
                "views": int(job.view_count or 0),
                "applications": int(app_counts.get(str(job.id), 0)),
                "bookmarks": int(bm_counts.get(str(job.id), 0)),
                "engagement_score": round(score, 1),
            }
        )

    return {"trending": trending, "window_days": days, "total": len(scored)}


@router.post("/{job_id}/view")
async def increment_job_views(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Record a view on a job (feeds the Trending ranking)."""
    repo = JobRepository(db)
    count = await repo.increment_view_count(job_id)
    if count is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "view_count": count}


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific job."""
    service = JobService(db)
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    job_data: JobCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new job."""
    service = JobService(db)
    try:
        job_dict = job_data.model_dump()
        job_dict.setdefault("source", "manual")
        return await service.create_job(job_dict)
    except DuplicateJobError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create job") from e


_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref"}


def _normalize_share_url(url: str) -> str:
    """Canonicalize a pasted job URL so the same link never duplicates.

    Strips the fragment and common click-tracking query parameters, lowercases
    the scheme/host, and collapses a trailing slash — so a LinkedIn post
    shared with ``?utm_source=...`` or a trailing ``/`` maps to the same saved
    job as the bare link.
    """
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ("http", "https"):
        return url.strip()
    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            "",
            urlencode(query),
            "",
        )
    )


def _safe_fetchable(url: str) -> bool:
    """Reject URLs that would make the server fetch internal targets.

    SSRF guard for the share endpoint: only http(s) URLs are allowed and the
    hostname must not resolve to a private, loopback, link-local, multicast,
    reserved or unspecified address (cloud metadata 169.254.169.254, localhost
    services, internal hosts).
    """
    import ipaddress
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if ":" in host:  # bare IPv6 literal
        candidates = [host]
    else:
        try:
            candidates = [str(addr[4][0]) for addr in socket.getaddrinfo(host, None)]
        except OSError:
            return False
    for ip_str in candidates:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def _json_ld_jobposting(soup) -> dict | None:
    """Extract the first JobPosting from JSON-LD structured data.

    Career pages and boards that embed schema.org data (Greenhouse, Lever,
    Workable, many direct career sites) expose the real title, hiring
    company and location as JSON-LD — more accurate than OpenGraph, whose
    ``og:site_name`` is the job board ("Indeed"), not the hiring company.
    Returns ``None`` when no usable JobPosting block exists; never raises.
    """
    import json

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.get_text().strip()
        if not raw or len(raw) > 1_000_000:
            continue
        try:
            data = json.loads(raw)
        except Exception:  # noqa: S112 - a broken block just gets skipped
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            types = item.get("@type")
            norm = types if isinstance(types, list) else [types]
            if "JobPosting" not in norm:
                continue
            out: dict = {}
            title = item.get("title")
            if isinstance(title, str) and title.strip():
                out["title"] = title.strip()
            org = item.get("hiringOrganization")
            if isinstance(org, dict):
                org_name = org.get("name")
                if isinstance(org_name, str) and org_name.strip():
                    out["company"] = org_name.strip()
            elif isinstance(org, str) and org.strip():
                out["company"] = org.strip()
            loc = item.get("jobLocation")
            parts: list[str] = []
            for place in loc if isinstance(loc, list) else [loc]:
                if not isinstance(place, dict):
                    continue
                address = place.get("address")
                if isinstance(address, str):
                    if address.strip():
                        parts.append(address.strip())
                    continue
                if not isinstance(address, dict):
                    continue
                locality = address.get("addressLocality")
                region = address.get("addressRegion")
                country = address.get("addressCountry")
                if isinstance(country, dict):
                    country = country.get("name")
                for bit in (locality, region):
                    if isinstance(bit, str) and bit.strip():
                        parts.append(bit.strip())
                # Skip 2-letter country codes ("IN"); keep full names.
                if (
                    isinstance(country, str)
                    and country.strip()
                    and len(country.strip()) > 2
                ):
                    parts.append(country.strip())
            if parts:
                out["location"] = ", ".join(parts)
            if out.get("title") or out.get("company"):
                return out
    return None


def _parse_page_meta(html: str) -> dict:
    """Extract shareable metadata from a fetched page (pure, testable).

    Title preference: JSON-LD JobPosting title > OpenGraph ``og:title`` >
    the HTML ``<title>`` tag. Company comes from JSON-LD
    ``hiringOrganization`` when present (a job page's ``og:site_name`` is
    the job board, not the hiring company); otherwise ``og:site_name``.
    Location is only available from JSON-LD.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    def _og(prop: str) -> str | None:
        tag = soup.find("meta", property=prop)
        content = tag.get("content") if tag else None
        if content is not None:
            if isinstance(content, list):
                return " ".join(str(c) for c in content).strip()
            return str(content).strip()
        return None

    job_ld = _json_ld_jobposting(soup) or {}
    og_title = _og("og:title")
    html_title = soup.title.get_text(strip=True) if soup.title else None
    meta = {
        "title": job_ld.get("title") or og_title or html_title,
        "site_name": _og("og:site_name") or "",
        "description": _og("og:description"),
    }
    if job_ld.get("company"):
        meta["company"] = job_ld["company"]
    if job_ld.get("location"):
        meta["location"] = job_ld["location"]
    return meta


async def _fetch_page_meta(url: str) -> dict:
    """Fetch a page and return its title/company/location metadata.

    Used by the share endpoint so a bare link (LinkedIn post, company careers
    page, any job board) can be saved without the user typing title/company.
    Falls back through JSON-LD JobPosting, OpenGraph and the HTML title tag.
    Returns an empty dict when the page is unreachable, unsafe to fetch
    (SSRF guard), or has no metadata.
    """
    import httpx

    from interntrack.config import get_settings

    if not _safe_fetchable(url):
        return {}

    try:
        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            headers={"User-Agent": get_settings().user_agent},
        ) as client:
            response = await client.get(url)
        if response.status_code != 200:
            return {}
        return _parse_page_meta(response.text)
    except Exception:
        return {}


async def _save_shared_job(
    service: JobService,
    url: str,
    title: str | None = None,
    company: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> dict:
    """Save one shared/imported job, auto-detecting fields from the page.

    Shared by the single ``/share`` endpoint and the bulk ``/import-links``
    endpoint so a pasted link is always handled identically: the URL is
    normalized (no duplicate links), title/company auto-detected from the
    page's OpenGraph/JSON-LD meta when not supplied, and stored with
    ``source=manual`` so it shows up in the dashboard and daily alerts like
    any other job.

    Returns ``{"job", "duplicate", "message"}`` on success (``duplicate:
    True`` when the URL was already saved — idempotent) or ``{"error"}``
    when the title can't be detected. Never raises.
    """
    normalized_url = _normalize_share_url(url)
    existing = await service.job_repo.get_by_url(normalized_url)
    if existing:
        return {
            "job": existing,
            "duplicate": True,
            "message": "This job is already saved.",
        }

    title = (title or "").strip()
    company = (company or "").strip()
    if not title or not company:
        meta = await _fetch_page_meta(normalized_url)
        title = title or (meta.get("title") or "").strip()
        # Prefer the hiring company from JSON-LD; og:site_name is the board.
        company = company or (meta.get("company") or meta.get("site_name") or "Unknown")
        description = description or meta.get("description")
        location = location or meta.get("location")

    if not title:
        return {
            "error": (
                "Couldn't auto-detect the job title from that link. "
                "Please paste the job title as well."
            ),
        }

    try:
        job = await service.create_job(
            {
                "title": title.strip(),
                "company": company.strip() or "Unknown",
                "url": normalized_url,
                "location": location,
                "description": description,
                "source": "manual",
            },
        )
    except DuplicateJobError:
        existing = await service.job_repo.get_by_url(normalized_url)
        return {
            "job": existing,
            "duplicate": True,
            "message": "This job is already saved.",
        }

    return {
        "job": job,
        "duplicate": False,
        "message": "Job saved! It will now appear in your dashboard and alerts.",
    }


@router.post("/share")
async def share_job(
    payload: JobShareRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save a job the user found anywhere on the web.

    Paste any job link (LinkedIn post, careers page, job board) and it is
    stored with ``source=manual`` so it shows up in the dashboard and in the
    daily email/Telegram alerts like any other job. When title/company are not
    supplied they are auto-detected from the page's OpenGraph meta tags.

    Returns ``duplicate: true`` with the existing job when the URL is already
    saved (idempotent — safe to share the same link again).
    """
    service = JobService(db)
    result = await _save_shared_job(
        service,
        payload.url,
        payload.title,
        payload.company,
        payload.location,
        payload.description,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/import-links")
async def import_links(
    payload: JobImportLinksRequest,
    db: AsyncSession = Depends(get_db),
):
    """Bulk-save up to 8 pasted job links in a single request.

    Each link is processed exactly like a single ``/jobs/share`` call —
    title/company auto-detected from the page, duplicates skipped. Links are
    handled sequentially with a per-link deadline so one slow page can't
    stall the whole batch inside the platform's request timeout; when the
    overall time budget is exhausted the remaining links are reported as
    failed and the partial results are returned.
    """
    service = JobService(db)
    results: list[dict] = []
    # Matches the discovery deadline so the whole batch stays well under the
    # platform's 60s request kill (worst case here is budget + one 9s link).
    started = time.monotonic()
    for url in payload.urls:
        if time.monotonic() - started > 40:
            results.append(
                {
                    "url": url,
                    "skipped": True,
                    "error": "Batch time limit reached — remaining links were skipped.",
                }
            )
            continue
        try:
            result = await asyncio.wait_for(_save_shared_job(service, url), timeout=9)
        except TimeoutError:
            # A cancelled write can leave the shared session with a pending
            # transaction — roll back so the next link starts clean.
            with contextlib.suppress(Exception):
                await db.rollback()
            result = {"error": "Page took too long to load — skipped."}
        except Exception:
            result = {"error": "Unexpected error while saving this link."}
        result["url"] = url
        results.append(result)

    saved = sum(1 for r in results if not r.get("duplicate") and not r.get("error"))
    duplicates = sum(1 for r in results if r.get("duplicate"))
    skipped = sum(1 for r in results if r.get("skipped"))
    failed = sum(1 for r in results if r.get("error") and not r.get("skipped"))
    return {
        "results": results,
        "saved": saved,
        "duplicates": duplicates,
        "skipped": skipped,
        "failed": failed,
        "total": len(results),
    }


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    job_data: JobUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a job."""
    service = JobService(db)
    updates = {k: v for k, v in job_data.model_dump().items() if v is not None}
    job = await service.job_repo.update(job_id, updates)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a job."""
    service = JobService(db)
    deleted = await service.job_repo.delete(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/search", response_model=JobListResponse)
async def search_jobs(
    search: JobSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Search jobs."""
    service = JobService(db)
    jobs = await service.search_jobs(search.query, search.limit)
    return JobListResponse(jobs=jobs, total=len(jobs), skip=0, limit=search.limit)


@router.get("/stats/overview", response_model=JobStatistics)
async def get_job_statistics(
    db: AsyncSession = Depends(get_db),
):
    """Get job statistics."""
    service = JobService(db)
    return await service.get_job_statistics()


@router.get("/closing/soon", response_model=list[JobResponse])
async def get_closing_soon(
    days: int = Query(2, ge=1, le=7),
    db: AsyncSession = Depends(get_db),
):
    """Get jobs closing soon."""
    service = JobService(db)
    return await service.get_closing_soon(days)


@router.post("/discovery/run-for-users")
async def run_discovery_for_users(
    limit: int = Query(4, ge=1, le=8),
    db: AsyncSession = Depends(get_db),
):
    """Run discovery with queries derived from every enabled user's profile.

    Each account's preferred domains + skills produce the search queries, so
    a cybersecurity user's alerts are fed by security job searches (soc
    analyst, vapt, penetration testing, ...) instead of a fixed query. With
    no accounts yet it falls back to the classic fixed queries. The GitHub
    Actions cron calls this three times a day in place of the hardcoded ones.
    """
    from interntrack.scheduler.jobs import (
        DEFAULT_LOCATION,
        _enabled_alert_targets,
        discovery_queries_for,
    )
    from interntrack.scrapers.registry import get_default_registry

    targets = await _enabled_alert_targets(db)
    # (query, location) pairs so each user's location is passed straight to
    # the scrapers — this is what makes the India scrapers (LinkedIn India,
    # Internshala, TimesJobs, Indeed India) actually target Bangalore instead
    # of the US geo-locked guest APIs.
    query_locations: list[tuple[str, str | None]] = []
    for target in targets:
        user = target["user"]
        location = (getattr(user, "location", None) or "").strip() if user else None
        for q in discovery_queries_for(
            target["prefs"],
            target["user"],
            limit=limit,
        ):
            query_locations.append((q, location or DEFAULT_LOCATION))
    if not query_locations:
        query_locations = [
            ("cybersecurity", DEFAULT_LOCATION),
            ("software engineering", DEFAULT_LOCATION),
            ("python developer", DEFAULT_LOCATION),
        ]
    unique: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for q, loc in query_locations:
        key = q.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append((q.strip(), loc))

    registry = get_default_registry()
    service = JobService(db)
    details = []
    total_found = total_saved = 0
    saved_all: list = []
    # Vercel serverless functions are killed at maxDuration (60s). Discovery
    # runs only the fast/India-relevant sources and stops early once the
    # budget is used up, so the request always returns a partial result
    # instead of dying with FUNCTION_INVOCATION_TIMEOUT.
    import time

    deadline = time.monotonic() + _DISCOVERY_DEADLINE_SECONDS
    for query, location in unique:
        if time.monotonic() > deadline:
            break
        # Pass the city as the separate ``location`` arg, not inside the
        # keyword — vendor/RSS/HN scrapers match the keyword against role
        # titles and would otherwise never see non-India postings.
        jobs = await registry.fetch_all(
            query=_strip_location_from_query(query),
            location=location,
            sources=_DISCOVERY_SOURCES,
        )
        saved = await service.save_jobs(jobs)
        total_found += len(jobs)
        total_saved += len(saved)
        saved_all.extend(saved)
        details.append({"query": query, "found": len(jobs), "saved": len(saved)})
    # Ping users on Telegram the moment a high-match job lands (instead of
    # waiting for the next daily slot). One consolidated pass after all
    # queries so a user gets a single ping per run, not one per query.
    # Best-effort — never blocks/breaks discovery.
    if saved_all:
        from interntrack.scheduler.jobs import _send_instant_alerts

        with contextlib.suppress(Exception):
            await _send_instant_alerts(db, saved_all)
    return {
        "users": len(targets),
        "queries_run": len(details),
        "queries": details,
        "found": total_found,
        "saved": total_saved,
    }


@router.post("/discovery/run")
async def run_discovery(
    source: str | None = None,
    query: str = "python developer",
    body: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Run job discovery from sources.

    Accepts the query either as a query parameter (?query=...) for
    backward compatibility or in the JSON body ({"query": ...}) which
    is what the Streamlit dashboard sends. The body value wins so the
    dashboard's "Run Discovery" button searches what the user typed
    instead of silently falling back to the default.
    """
    if isinstance(body, dict) and body.get("query"):
        query = body["query"]
    from interntrack.scrapers.registry import get_default_registry

    registry = get_default_registry()
    # "cybersecurity bangalore" -> query="cybersecurity", location="Bangalore"
    # so the India scrapers target Bangalore instead of US geo-locked APIs.
    location = _extract_location_from_query(query)
    sources = [source] if source else _DISCOVERY_SOURCES
    jobs = await registry.fetch_all(
        query=_strip_location_from_query(query),
        location=location,
        sources=sources,
    )
    service = JobService(db)
    saved = await service.save_jobs(jobs)

    # Notify configured channels when new jobs were saved (no-op otherwise).
    if saved:
        from interntrack.scheduler.jobs import _send_instant_alerts
        from interntrack.services.notification_service import NotificationManager

        with contextlib.suppress(Exception):
            message = (
                f"🚀 Job Discovery\n\n"
                f"Query: {query}\n"
                f"Found: {len(jobs)} · Newly saved: {len(saved)}\n\n"
                f"Check the dashboard or the Jobs page to review them."
            )
            await NotificationManager(db).notify_all(
                message,
                subject="New Jobs Found",
            )
            # Per-user instant Telegram pings for high-match jobs.
            await _send_instant_alerts(db, saved)

    return {"discovered": len(jobs), "saved": len(saved)}
