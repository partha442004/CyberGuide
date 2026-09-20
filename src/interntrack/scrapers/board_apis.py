"""
Free public job-board APIs as additional discovery sources.

Three boards, all official JSON APIs, no keys, no bot-gating:

* **Remotive**  — remote jobs worldwide (strong software/frontend/data mix).
* **Arbeitnow** — largest German/EU board; includes English-speaking roles
  and a large remote segment.
* **Jobicy**    — curated remote roles across engineering, design, marketing.

All three are board-level sweeps: the APIs don't take search keywords, so the
scraper filters each posting against the discovery query (``matches_query``,
same contract as the HackerNews scraper). Jobs are deduped by URL inside
``save_jobs``, so repeated sweeps never create duplicates. India-hosted
postings pass the per-user location gate at digest time; the rest reach
remote-opted-in members (include_remote default True) and are excluded
from city-scoped members' digests otherwise.
"""

import logging

from interntrack.scrapers.base import BaseScraper, RawJob, matches_query

logger = logging.getLogger(__name__)


def _strip_html(html: str | None, cap: int = 1200) -> str | None:
    """Crude HTML→text for board descriptions (they ship raw HTML)."""
    if not html:
        return None
    import re

    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:cap] or None


class _BoardSweepScraper(BaseScraper):
    """Shared sweep+filter logic for keyword-less board APIs.

    Subclasses set ``api_url``/``params`` and implement ``_parse``. The
    base class owns the HTTP client, retrying ``_get`` and ``close``.
    ``fetch`` pulls the board once, then keeps only postings matching the
    discovery query (empty query = everything, used by board sweeps).
    """

    api_url: str
    params: dict[str, str | int] = {}

    @property
    def rate_limit(self) -> int:
        return 30

    async def fetch(
        self,
        query: str,
        location: str | None = None,  # noqa: ARG002 (interface contract)
        limit: int = 100,
    ) -> list[RawJob]:
        try:
            response = await self._get(self.api_url, params=self.params or None)
            payload = response.json()
        except Exception:  # noqa: BLE001 - a down board must not break discovery
            return []
        parsed = self._parse(payload)
        if not query or not query.strip():
            return parsed[:limit]
        # AND-match each board posting against the discovery query, same
        # semantics every other scraper applies to its raw results.
        return [
            j
            for j in parsed
            if matches_query(j.description or "", query, title=j.title)
        ][:limit]

    def _parse(self, payload: dict) -> list[RawJob]:  # pragma: no cover - abstract
        raise NotImplementedError


class RemotiveScraper(_BoardSweepScraper):
    """Remotive public remote-jobs API (https://remotive.com/api/remote-jobs)."""

    api_url = "https://remotive.com/api/remote-jobs"
    params = {"limit": 100}

    @property
    def source_name(self) -> str:
        return "remotive"

    def _parse(self, payload: dict) -> list[RawJob]:
        jobs: list[RawJob] = []
        for j in payload.get("jobs") or []:
            try:
                jobs.append(
                    RawJob(
                        title=str(j.get("title") or "")[:200],
                        company=str(j.get("company_name") or "Unknown"),
                        url=str(j.get("url") or ""),
                        description=_strip_html(j.get("description")),
                        location=str(j.get("candidate_required_location") or "Remote"),
                        is_remote=True,
                        tags=[str(t) for t in (j.get("tags") or [])][:10],
                        source=self.source_name,
                    )
                )
            except Exception:  # noqa: BLE001 - one bad row must not kill the batch
                logger.debug("remotive row skipped", exc_info=True)
                continue
        return [j for j in jobs if j.url]


class ArbeitnowScraper(_BoardSweepScraper):
    """Arbeitnow public job-board API (https://arbeitnow.com/api/job-board-api)."""

    api_url = "https://arbeitnow.com/api/job-board-api"

    @property
    def source_name(self) -> str:
        return "arbeitnow"

    def _parse(self, payload: dict) -> list[RawJob]:
        jobs: list[RawJob] = []
        for j in payload.get("data") or []:
            try:
                remote = bool(j.get("remote"))
                jobs.append(
                    RawJob(
                        title=str(j.get("title") or "")[:200],
                        company=str(j.get("company_name") or "Unknown"),
                        url=str(j.get("url") or ""),
                        description=_strip_html(j.get("description")),
                        location=(
                            "Remote" if remote else str(j.get("location") or "Germany")
                        ),
                        is_remote=remote,
                        tags=[str(t) for t in (j.get("tags") or [])][:10],
                        source=self.source_name,
                    )
                )
            except Exception:  # noqa: BLE001
                logger.debug("%s row skipped", self.source_name, exc_info=True)
                continue
        return [j for j in jobs if j.url]


class JobicyScraper(_BoardSweepScraper):
    """Jobicy public remote-jobs API (https://jobicy.com/api/v2/remote-jobs)."""

    api_url = "https://jobicy.com/api/v2/remote-jobs"
    params = {"count": 50}

    @property
    def source_name(self) -> str:
        return "jobicy"

    def _parse(self, payload: dict) -> list[RawJob]:
        jobs: list[RawJob] = []
        for j in payload.get("jobs") or []:
            try:
                jobs.append(
                    RawJob(
                        title=str(j.get("jobTitle") or "")[:200],
                        company=str(j.get("companyName") or "Unknown"),
                        url=str(j.get("url") or ""),
                        description=_strip_html(
                            j.get("jobDescription") or j.get("jobExcerpt")
                        ),
                        location=str(j.get("jobGeo") or "Remote"),
                        is_remote=True,
                        tags=[str(j["jobLevel"])] if j.get("jobLevel") else [],
                        source=self.source_name,
                    )
                )
            except Exception:  # noqa: BLE001
                logger.debug("%s row skipped", self.source_name, exc_info=True)
                continue
        return [j for j in jobs if j.url]
