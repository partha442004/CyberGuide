"""
RemoteOK job scraper.
"""

from datetime import UTC, datetime

from interntrack.domain.enums import JobSource
from interntrack.scrapers.base import BaseScraper, RawJob, matches_query


class RemoteOKScraper(BaseScraper):
    """Scraper for RemoteOK job board."""

    BASE_URL = "https://remoteok.com/api"

    @property
    def source_name(self) -> str:
        return JobSource.REMOTE_OK.value

    @property
    def rate_limit(self) -> int:
        return 30

    async def fetch(
        self,
        query: str,
        location: str | None = None,  # noqa: ARG002 (interface contract)
        limit: int = 100,
    ) -> list[RawJob]:
        """Fetch remote jobs from RemoteOK."""
        jobs = []

        try:
            response = await self._get(self.BASE_URL)
            data = response.json()

            # First item is metadata
            for item in data[1:]:
                job = self._parse_job(item, query)
                if job:
                    jobs.append(job)
                if len(jobs) >= limit:
                    break

        except Exception as e:
            print(f"Error fetching from RemoteOK: {e}")

        return jobs

    def _parse_job(self, item: dict, query: str) -> RawJob | None:
        """Parse job item from RemoteOK."""
        title = item.get("position", "")
        company = item.get("company", "")
        description = item.get("description", "")

        # Check if matches query (multi-token + security-family expansion;
        # security queries match against title + company)
        if not matches_query(
            f"{title} {company} {description}",
            query,
            title=f"{title} {company}",
        ):
            return None

        # Parse salary
        salary_min = None
        salary_max = None
        salary_text = item.get("salary", "")
        if salary_text:
            salary_min, salary_max = self._parse_salary(salary_text)

        return RawJob(
            title=title,
            company=company,
            url=item.get("url", f"https://remoteok.com/l/{item.get('id', '')}"),
            description=description,
            location=item.get("location", "Remote"),
            salary_min=salary_min,
            salary_max=salary_max,
            is_remote=True,
            posted_at=self._parse_date(item.get("epoch")),
            tags=item.get("tags", []),
            source=self.source_name,
            raw_data=item,
        )

    def _parse_salary(self, salary_text: str) -> tuple:
        """Parse salary from text."""
        import re

        numbers = re.findall(r"[\d,]+", salary_text)
        if len(numbers) >= 2:
            return (
                int(numbers[0].replace(",", "")),
                int(numbers[1].replace(",", "")),
            )
        if len(numbers) == 1:
            val = int(numbers[0].replace(",", ""))
            return (val, val)
        return (None, None)

    def _parse_date(self, epoch: int | None) -> datetime | None:
        """Parse epoch timestamp."""
        if epoch:
            return datetime.fromtimestamp(epoch, tz=UTC)
        return None
