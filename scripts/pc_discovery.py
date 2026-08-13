"""PC discovery CLI — feed bot-gated sources into the live InternTrack DB.

Why this exists
---------------
JobDexo, Foundit, Apna and Cutshort bot-gate Vercel's datacenter IPs, so
the GitHub-cron discovery on the server can't fetch them directly. From
*your* machine (residential IP) they work perfectly. This script runs
those scrapers locally, then pushes the parsed jobs to the live API's
``POST /api/v1/jobs/`` endpoint (source=manual) — so their fresh roles
land in the DB and flow into everyone's digests, with no server changes.

Usage
-----
    # Quick run: cybersecurity + Bangalore, all blocked sources
    python scripts/pc_discovery.py --query "cybersecurity" --location "Bangalore"

    # More queries / other sources / custom API
    python scripts/pc_discovery.py \
        --query "frontend developer" --query "hardware engineer" \
        --location "Chennai" --limit 12

    # Every member's domains in one go (reads the live delivery overview)
    python scripts/pc_discovery.py --all-members --limit 20

Flags
-----
    --api-url   Live API base URL (default https://cyberguide-api.vercel.app)
    --query     Repeatable; keyword searched per source (default "cybersecurity")
    --location  City to scope searches (default "Bangalore")
    --sources   Comma list: jobdexo,foundit,apna,cutshort (default all four)
    --limit     Max jobs to POST per run (default 10)
    --all-members  Derive queries + locations from the live member list

The script is best-effort: a failing source or a 409 duplicate is
reported, never fatal. It pauses briefly between posts to stay gentle.
"""

import argparse
import asyncio
import contextlib
import sys
from datetime import UTC, datetime

import httpx


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--api-url", default="https://cyberguide-api.vercel.app")
    p.add_argument("--query", action="append", default=None)
    p.add_argument("--location", default="Bangalore")
    p.add_argument("--sources", default="jobdexo,foundit,apna,cutshort")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--all-members", action="store_true")
    return p.parse_args()


def _now() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


async def _member_queries(api_url: str, location: str) -> list[str]:
    """Derive (query, location) pairs from the live delivery overview.

    Each member's stored domains + location become one discovery query so
    a single ``--all-members`` run covers every account's interests.
    """
    pairs: list[tuple[str, str]] = []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{api_url}/api/v1/notifications/delivery-overview")
            resp.raise_for_status()
            members = (resp.json().get("members") or [])[:8]
        for m in members:
            domains = [d for d in (m.get("domains") or []) if d]
            loc = (m.get("location") or location).strip()
            for d in domains[:2]:
                pairs.append((d, loc))
    except Exception as e:  # noqa: BLE001 - fall back to defaults
        print(f"  ⚠ delivery overview unavailable ({e}) — using defaults")
        pairs.append(("cybersecurity", location))
    if not pairs:
        pairs.append(("cybersecurity", location))
    return [f"{q} {loc}".strip() for q, loc in pairs]


async def _run_scraper(name: str, query: str, location: str) -> list:
    """Run one bot-gated scraper locally; return RawJob list (never raises)."""
    try:
        if name == "jobdexo":
            from interntrack.scrapers.jobdexo import JobDexoScraper

            scraper = JobDexoScraper()
        elif name == "foundit":
            from interntrack.scrapers.foundit import FounditScraper

            scraper = FounditScraper()
        elif name == "apna":
            from interntrack.scrapers.apna import ApnaScraper

            scraper = ApnaScraper()
        elif name == "cutshort":
            from interntrack.scrapers.cutshort import CutshortScraper

            scraper = CutshortScraper()
        else:
            return []
        jobs = await scraper.fetch(query, location)
        await scraper.client.aclose()
        return jobs or []
    except Exception as e:  # noqa: BLE001 - a broken source never kills the run
        print(f"  ⚠ {name} failed: {e}")
        return []


def _to_payload(job) -> dict:
    """Map a RawJob to the JobCreate payload accepted by POST /api/v1/jobs/."""
    return {
        "title": str(job.title or "")[:500],
        "company": str(job.company or "Unknown")[:200],
        "location": (job.location or None),
        "description": job.description,
        "url": str(job.url or ""),
        "job_type": job.job_type,
        "experience_level": job.raw_data.get("experience_level")
        if isinstance(getattr(job, "raw_data", None), dict)
        else None,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency or "INR",
        "is_remote": bool(job.is_remote),
        "tags": list(job.tags or [])[:15],
        "source": "manual",
    }


async def _push(client: httpx.AsyncClient, api_url: str, job) -> str:
    """POST one job; returns 'saved' / 'duplicate' / 'failed: reason'."""
    payload = _to_payload(job)
    try:
        resp = await client.post(f"{api_url}/api/v1/jobs/", json=payload, timeout=30)
        if resp.status_code in (200, 201):
            return "saved"
        if resp.status_code == 409:
            return "duplicate"
        return f"failed: HTTP {resp.status_code}"
    except Exception as e:  # noqa: BLE001 - report, never crash
        return f"failed: {e}"


async def _run() -> None:
    args = _parse_args()
    api_url = args.api_url.rstrip("/")
    print(f"🌐 PC discovery → {api_url}  ({_now()} UTC)")
    print(f"   sources: {args.sources} · limit: {args.limit}")

    if args.all_members:
        queries = await _member_queries(api_url, args.location)
        print(f"   member-derived queries: {len(queries)}")
    else:
        queries = args.query or ["cybersecurity"]

    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    all_jobs: list = []
    seen_urls: set[str] = set()
    for query in queries:
        for name in sources:
            jobs = await _run_scraper(name, query, args.location)
            fresh = 0
            for job in jobs:
                url = str(job.url or "").strip()
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_jobs.append(job)
                    fresh += 1
            print(f"   {name:<10} '{query}' → {len(jobs)} found, {fresh} new")
    if not all_jobs:
        print("   no jobs found — nothing to push")
        return

    all_jobs = all_jobs[: args.limit]
    print(f"   pushing {len(all_jobs)} job(s) to the live DB…")
    counts = {"saved": 0, "duplicate": 0, "failed": 0}
    async with httpx.AsyncClient(timeout=30) as client:
        for job in all_jobs:
            outcome = await _push(client, api_url, job)
            if outcome == "saved":
                counts["saved"] += 1
                print(
                    f"   ✅ {job.title[:50]} @ {job.company} "
                    f"· {job.location or 'Remote'}"
                )
            elif outcome == "duplicate":
                counts["duplicate"] += 1
            else:
                counts["failed"] += 1
                print(f"   ⚠ {job.title[:40]}: {outcome}")
            await asyncio.sleep(0.4)
    print(
        f"🏁 done: {counts['saved']} saved, {counts['duplicate']} "
        f"duplicates, {counts['failed']} failed ({_now()} UTC)"
    )


def main() -> int:
    # Windows consoles default to cp1252 and choke on emoji — force UTF-8
    # output so the progress lines render on any terminal.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(Exception):
                reconfigure(encoding="utf-8", errors="replace")
    try:
        asyncio.run(_run())
        return 0
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
