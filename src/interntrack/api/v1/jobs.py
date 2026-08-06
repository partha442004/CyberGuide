"""
Jobs API endpoints.
"""

import contextlib

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.job import (
    JobCreate,
    JobListResponse,
    JobResponse,
    JobSearchRequest,
    JobShareRequest,
    JobStatistics,
    JobUpdate,
)
from interntrack.database.session import get_db
from interntrack.domain.exceptions import DuplicateJobError
from interntrack.services.job_service import JobService

router = APIRouter()


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


async def _fetch_page_meta(url: str) -> dict:
    """Fetch a page and return OpenGraph meta tags for title/company.

    Used by the share endpoint so a bare link (LinkedIn post, company careers
    page, any job board) can be saved without the user typing title/company.
    Returns an empty dict when the page is unreachable, unsafe to fetch
    (SSRF guard), or has no metadata.
    """
    import httpx
    from bs4 import BeautifulSoup

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

        soup = BeautifulSoup(response.text, "html.parser")

        def _og(prop: str) -> str | None:
            tag = soup.find("meta", property=prop)
            content = tag.get("content") if tag else None
            if content is not None:
                if isinstance(content, list):
                    return " ".join(str(c) for c in content).strip()
                return str(content).strip()
            return None

        title = _og("og:title") or (
            soup.title.get_text(strip=True) if soup.title else None
        )
        site_name = _og("og:site_name") or ""
        description = _og("og:description")
        return {
            "title": title,
            "site_name": site_name,
            "description": description,
        }
    except Exception:
        return {}


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

    normalized_url = _normalize_share_url(payload.url)
    existing = await service.job_repo.get_by_url(normalized_url)
    if existing:
        return {
            "job": existing,
            "duplicate": True,
            "message": "This job is already saved.",
        }

    title = payload.title or ""
    company = payload.company or ""
    description = payload.description
    if not title or not company:
        meta = await _fetch_page_meta(normalized_url)
        title = title or (meta.get("title") or "")
        company = company or (meta.get("site_name") or "Unknown")
        description = description or meta.get("description")

    if not title:
        raise HTTPException(
            status_code=400,
            detail=(
                "Couldn't auto-detect the job title from that link. "
                "Please paste the job title as well."
            ),
        )

    try:
        job = await service.create_job(
            {
                "title": title.strip(),
                "company": company.strip() or "Unknown",
                "url": normalized_url,
                "location": payload.location,
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
    from interntrack.scheduler.jobs import _enabled_alert_targets, discovery_queries_for
    from interntrack.scrapers.registry import get_default_registry

    targets = await _enabled_alert_targets(db)
    queries: list[str] = []
    for target in targets:
        queries.extend(
            discovery_queries_for(target["prefs"], target["user"], limit=limit)
        )
    if not queries:
        queries = ["cybersecurity", "software engineering", "python developer"]
    unique = list(dict.fromkeys(q for q in queries if q.strip()))

    registry = get_default_registry()
    service = JobService(db)
    details = []
    total_found = total_saved = 0
    # Vercel serverless functions are killed at maxDuration (60s). Each query
    # can take ~15s against live job sites, so stop early once the budget is
    # used up instead of letting the whole request die with a 500.
    import time

    deadline = time.monotonic() + 50
    for query in unique:
        if time.monotonic() > deadline:
            break
        jobs = await registry.fetch_all(query=query)
        saved = await service.save_jobs(jobs)
        total_found += len(jobs)
        total_saved += len(saved)
        details.append({"query": query, "found": len(jobs), "saved": len(saved)})
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
    jobs = await registry.fetch_all(query=query, sources=[source] if source else None)
    service = JobService(db)
    saved = await service.save_jobs(jobs)

    # Notify configured channels when new jobs were saved (no-op otherwise).
    if saved:
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

    return {"discovered": len(jobs), "saved": len(saved)}
