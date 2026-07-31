# InternTrack - Discovery Engine

## Overview

The Discovery Engine is responsible for automated job discovery from multiple sources. It uses a plugin-based architecture with scrapers for different job boards.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Discovery Engine                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Scraper    │    │   Scraper    │    │   Scraper    │       │
│  │   Registry   │───▶│   Plugin     │───▶│   Plugin     │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                    │                    │               │
│         ▼                    ▼                    ▼               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Raw Jobs Buffer                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               Deduplication Engine                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               Verification Engine                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               Classification Engine                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Database Storage                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Scraper Registry

The `ScraperRegistry` manages all available scrapers:

```python
from interntrack.scrapers.registry import get_default_registry

# Get default registry with all scrapers
registry = get_default_registry()

# Fetch from all sources
jobs = await registry.fetch_all(query="python developer")

# Fetch from specific sources
jobs = await registry.fetch_all(
    query="react developer",
    sources=["hackernews", "remote_ok"]
)
```

---

## Available Scrapers

### HackerNews Scraper

Scrapes "Who is hiring?" threads from Hacker News.

| Property | Value |
|----------|-------|
| Source | `hackernews` |
| Rate Limit | 30 req/min |
| Method | Firebase API |

**Features:**
- Parses HN comment format
- Extracts company, title, location
- Identifies skill tags
- Filters by query

---

### RemoteOK Scraper

Scrapes remote job listings from RemoteOK.

| Property | Value |
|----------|-------|
| Source | `remote_ok` |
| Rate Limit | 30 req/min |
| Method | JSON API |

**Features:**
- Direct JSON API access
- Salary parsing
- Tag extraction
- Remote job focus

---

### RSS Feed Scraper

Aggregates jobs from multiple RSS feeds.

| Property | Value |
|----------|-------|
| Source | `rss_feed` |
| Rate Limit | 60 req/min |
| Method | feedparser |

**Default Feeds:**
- RemoteOK RSS
- We Work Remotely RSS
- HN Jobs RSS

---

### LinkedIn Scraper

Scrapes LinkedIn job listings.

| Property | Value |
|----------|-------|
| Source | `linkedin` |
| Rate Limit | 10 req/min |
| Method | HTML parsing |

**Note:** LinkedIn has strict anti-scraping measures. Use responsibly.

---

### Indeed Scraper

Scrapes Indeed job listings.

| Property | Value |
|----------|-------|
| Source | `indeed` |
| Rate Limit | 15 req/min |
| Method | HTML parsing |

---

### Glassdoor Scraper

Scrapes Glassdoor job listings.

| Property | Value |
|----------|-------|
| Source | `glassdoor` |
| Rate Limit | 10 req/min |
| Method | HTML parsing |

---

## Adding a New Scraper

### Step 1: Create Scraper Class

```python
# src/interntrack/scrapers/my_source.py

from interntrack.domain.enums import JobSource
from interntrack.scrapers.base import BaseScraper, RawJob

class MySourceScraper(BaseScraper):
    """Scraper for MySource job board."""

    @property
    def source_name(self) -> str:
        return "my_source"

    @property
    def rate_limit(self) -> int:
        return 30

    async def fetch(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 100,
    ) -> List[RawJob]:
        """Fetch jobs from MySource."""
        jobs = []

        # Your scraping logic here
        response = await self._get("https://api.mysource.com/jobs")
        data = response.json()

        for item in data[:limit]:
            job = self._parse_job(item, query)
            if job:
                jobs.append(job)

        return jobs

    def _parse_job(self, item: dict, query: str) -> Optional[RawJob]:
        """Parse a job item."""
        # Parse job data into RawJob
        return RawJob(
            title=item["title"],
            company=item["company"],
            url=item["url"],
            description=item.get("description"),
            location=item.get("location"),
            source=self.source_name,
        )
```

### Step 2: Register in Registry

```python
# src/interntrack/scrapers/registry.py

def get_default_registry() -> ScraperRegistry:
    registry = ScraperRegistry()

    # ... existing scrapers ...
    from interntrack.scrapers.my_source import MySourceScraper
    registry.register(MySourceScraper())

    return registry
```

---

## RawJob Data Structure

```python
@dataclass
class RawJob:
    title: str
    company: str
    url: str
    description: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    job_type: Optional[str] = None
    is_remote: bool = False
    posted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    source: str = "unknown"
    raw_data: Optional[Dict[str, Any]] = None
```

---

## Rate Limiting

Each scraper has a rate limit property:

```python
@property
def rate_limit(self) -> int:
    """Rate limit in requests per minute."""
    return 60
```

The base scraper includes retry logic with exponential backoff:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
)
async def _get(self, url: str, **kwargs) -> httpx.Response:
    return await self.client.get(url, **kwargs)
```

---

## Scheduler Integration

Job discovery runs automatically via APScheduler:

```python
# Every 30 minutes
scheduler.add_job(
    run_job_discovery,
    IntervalTrigger(minutes=30),
    id="job_discovery",
)
```

---

## Error Handling

Scrapers handle errors gracefully:

```python
async def fetch(self, query: str, ...) -> List[RawJob]:
    jobs = []
    try:
        # Scraping logic
    except Exception as e:
        print(f"Error fetching from {self.source_name}: {e}")
    return jobs
```

---

**Module Status**: ✅ Complete
