# InternTrack - Software Architecture

## 1. System Overview

**InternTrack** is a comprehensive internship and job tracking platform with AI-powered job discovery, application management, skill-based learning recommendations, and automated reporting.

### 1.1 Vision
A self-hosted, open-source platform that helps students and job seekers discover opportunities, track applications, and develop relevant skills through curated learning resources.

### 1.2 Core Capabilities
| Capability | Description |
|------------|-------------|
| Job Discovery | Automated scraping from multiple job boards with deduplication |
| Application Tracking | Kanban-style pipeline from discovery to offer |
| Smart Notifications | Multi-channel alerts (Telegram, Email, Discord, Slack) |
| AI Classification | ML-powered job categorization and skill matching |
| Analytics Dashboard | Real-time insights with charts and trends |
| Learning Paths | Skill gap analysis with curated resources |

---

## 2. Architecture Style

### 2.1 Clean Architecture (Hexagonal/Ports & Adapters)

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  REST API   │  │  Dashboard  │  │  CLI Interface  │  │
│  │  (FastAPI)  │  │  (Streamlit)│  │  (Click/Typer)  │  │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │
├─────────┼────────────────┼──────────────────┼────────────┤
│         │        Application Layer          │            │
│  ┌──────┴───────────────────────────────────┴────────┐   │
│  │              Use Cases / Services                  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │   │
│  │  │ Job      │ │ App      │ │ Notification      │  │   │
│  │  │ Service  │ │ Service  │ │ Service           │  │   │
│  │  └──────────┘ └──────────┘ └───────────────────┘  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │   │
│  │  │ Report   │ │ AI       │ │ Learning          │  │   │
│  │  │ Service  │ │ Service  │ │ Service           │  │   │
│  │  └──────────┘ └──────────┘ └───────────────────┘  │   │
│  └──────────────────────────┬────────────────────────┘   │
├─────────────────────────────┼────────────────────────────┤
│              Domain Layer   │                            │
│  ┌──────────────────────────┴────────────────────────┐   │
│  │         Entities & Value Objects                  │   │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐  │   │
│  │  │ Job  │ │ App  │ │User  │ │Skill │ │Report  │  │   │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └────────┘  │   │
│  └──────────────────────────┬────────────────────────┘   │
├─────────────────────────────┼────────────────────────────┤
│           Infrastructure    │                            │
│  ┌──────────────────────────┴────────────────────────┐   │
│  │         Adapters & External Services              │   │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐  │   │
│  │  │ DB   │ │Scraper│ │AI/LLM│ │Email │ │Cache   │  │   │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └────────┘  │   │
│  └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Layer Responsibilities

| Layer | Responsibility | Dependencies |
|-------|---------------|--------------|
| **Presentation** | HTTP handling, request/response, auth | Application |
| **Application** | Use case orchestration, DTOs, validation | Domain |
| **Domain** | Business logic, entities, repository interfaces | None (innermost) |
| **Infrastructure** | External integrations, DB access, scraping | Domain |

### 2.3 Key Principles
- **Dependency Inversion**: Domain defines interfaces; Infrastructure implements them
- **Single Responsibility**: Each service handles one bounded context
- **Open/Closed**: Extend via plugins, not modification
- **Explicit Dependencies**: Constructor injection, no hidden globals

---

## 3. Technology Stack

### 3.1 Core Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Language** | Python 3.11+ | Async support, rich ecosystem |
| **Web Framework** | FastAPI | Async, OpenAPI docs, performance |
| **ORM** | SQLAlchemy 2.0+ | Async support, mature |
| **Migrations** | Alembic | Schema versioning |
| **Database** | SQLite (dev) → PostgreSQL (prod) | Progressive scaling |
| **Cache** | Redis (optional) | Rate limiting, caching |
| **Task Queue** | APScheduler + asyncio | Simplicity, no broker needed |

### 3.2 Scraping Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **HTTP Client** | httpx (async) | Async, modern API |
| **HTML Parsing** | BeautifulSoup4 | Reliable, battle-tested |
| **Browser Automation** | Playwright | JS-heavy sites |
| **Feed Parsing** | feedparser | RSS/Atom support |
| **Rate Limiting** | urllib3 Retry | Built-in backoff |

### 3.3 AI/ML Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Local LLM** | Ollama | Free, private, offline |
| **Cloud LLM** | Gemini Free API | Generous free tier |
| **Data Analysis** | Pandas | Data manipulation |
| **Skill Matching** | TF-IDF / Embeddings | Skill similarity |

### 3.4 Notification Stack

| Channel | Technology | Free Tier |
|---------|------------|-----------|
| Telegram | python-telegram-bot | Unlimited |
| Email | Gmail SMTP | 500/day |
| Discord | discord.py webhook | Unlimited |
| Slack | slack-sdk webhook | Limited |
| Push | Web Push API | Unlimited |

### 3.5 Frontend Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Dashboard** | Streamlit | Fast prototyping, Python-native |
| **Charts** | Plotly / Chart.js | Interactive visualizations |
| **Styling** | Custom CSS | Dark/Light mode |
| **Export** | Jinja2 PDF/HTML | Report generation |

### 3.6 DevOps Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Containerization** | Docker + Compose | Consistent environments |
| **CI/CD** | GitHub Actions | Free for public repos |
| **Hosting** | GitHub Pages (static) | Free |
| **Secrets** | .env + encryption | Security |

---

## 4. Data Flow Architecture

### 4.1 Job Discovery Pipeline

```
┌─────────┐    ┌──────────┐    ┌────────────┐    ┌────────────┐
│ Sources │───▶│ Scraper  │───▶│  Raw Jobs  │───▶│ Dedup      │
│ (RSS,   │    │ (async)  │    │  Buffer    │    │ Engine     │
│  API)   │    └──────────┘    └────────────┘    └─────┬──────┘
└─────────┘                                            │
                                                       ▼
┌─────────┐    ┌──────────┐    ┌────────────┐    ┌────────────┐
│ Store   │◀───│ Classify │◀───│  Verified  │◀───│ Verify     │
│ (DB)    │    │ (AI)     │    │  Jobs      │    │ Engine     │
└─────────┘    └──────────┘    └────────────┘    └────────────┘
```

### 4.2 Application Tracking Flow

```
┌────────────────────────────────────────────────────────────┐
│                    Application States                       │
│                                                            │
│  ┌──────┐   ┌──────┐   ┌───────┐   ┌──────────┐           │
│  │ Saved│──▶│Applie│──▶│Interview│──▶│Assessment│           │
│  └──────┘   │  d   │   └───┬───┘   └────┬─────┘           │
│             └──────┘       │            │                   │
│                            │            ▼                   │
│                            │     ┌──────────┐              │
│                            │     │Rejected  │              │
│                            │     └──────────┘              │
│                            ▼                               │
│                      ┌───────┐   ┌──────┐                  │
│                      │ Offer │──▶│Joined│                  │
│                      └───────┘   └──────┘                  │
└────────────────────────────────────────────────────────────┘
```

### 4.3 Report Generation Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Scheduler (APScheduler)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Daily 6AM│  │ Weekly   │  │ Monthly  │              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│       │             │             │                      │
│       ▼             ▼             ▼                      │
│  ┌──────────────────────────────────────────┐           │
│  │           Report Generator               │           │
│  │  • Query DB for metrics                  │           │
│  │  • Calculate trends                      │           │
│  │  • Generate charts                       │           │
│  │  • Format with Jinja2                    │           │
│  └─────────────────────┬────────────────────┘           │
│                        │                                 │
│       ┌────────────────┼────────────────┐               │
│       ▼                ▼                ▼               │
│  ┌─────────┐     ┌──────────┐    ┌──────────┐          │
│  │ Telegram│     │  Email   │    │ Dashboard│          │
│  └─────────┘     └──────────┘    └──────────┘          │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Component Architecture

### 5.1 Service Layer

```python
# Service interfaces (Domain layer)
class JobRepository(ABC):
    @abstractmethod
    async def find_by_id(self, job_id: UUID) -> Optional[Job]
    
    @abstractmethod
    async def find_duplicate(self, job: Job) -> Optional[Job]
    
    @abstractmethod
    async def save(self, job: Job) -> Job

class NotificationService(ABC):
    @abstractmethod
    async def send(self, notification: Notification) -> bool

# Service implementations (Application layer)
class JobService:
    def __init__(
        self,
        job_repo: JobRepository,
        scraper: ScraperAdapter,
        dedup_engine: DeduplicationEngine,
        notification: NotificationService
    ):
        self._job_repo = job_repo
        self._scraper = scraper
        self._dedup = dedup_engine
        self._notification = notification
    
    async def discover_jobs(self, source: str) -> List[Job]:
        raw_jobs = await self._scraper.fetch(source)
        unique_jobs = await self._dedup.filter(raw_jobs)
        saved_jobs = []
        for job in unique_jobs:
            saved = await self._job_repo.save(job)
            saved_jobs.append(saved)
        await self._notify_new_jobs(saved_jobs)
        return saved_jobs
```

### 5.2 Scraper Architecture

```python
# Scraper interface
class BaseScraper(ABC):
    @abstractmethod
    async def fetch(self, query: JobQuery) -> List[RawJob]
    
    @property
    @abstractmethod
    def source_name(self) -> str
    
    @property
    def rate_limit(self) -> int:
        return 60  # requests per minute

# Scraper registry
class ScraperRegistry:
    def __init__(self):
        self._scrapers: Dict[str, BaseScraper] = {}
    
    def register(self, scraper: BaseScraper):
        self._scrapers[scraper.source_name] = scraper
    
    def get(self, source: str) -> BaseScraper:
        return self._scrapers.get(source)
```

### 5.3 Notification Architecture

```python
# Channel interface
class NotificationChannel(ABC):
    @abstractmethod
    async def send(self, message: Message) -> bool
    
    @abstractmethod
    def format_message(self, data: Any) -> str

# Notification manager
class NotificationManager:
    def __init__(self):
        self._channels: Dict[str, NotificationChannel] = {}
    
    def register_channel(self, name: str, channel: NotificationChannel):
        self._channels[name] = channel
    
    async def notify(
        self,
        channels: List[str],
        message: Message
    ) -> Dict[str, bool]:
        results = {}
        for channel_name in channels:
            channel = self._channels.get(channel_name)
            if channel:
                results[channel_name] = await channel.send(message)
        return results
```

---

## 6. Configuration Architecture

### 6.1 Environment Configuration

```python
# .env structure
# Database
DATABASE_URL=sqlite+aiosqlite:///./data/interntrack.db
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost/interntrack

# Cache (optional)
REDIS_URL=redis://localhost:6379/0

# AI Services
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
GEMINI_API_KEY=your-key-here

# Notifications
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
SLACK_WEBHOOK_URL=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# Scraper Settings
SCRAPE_INTERVAL_MINUTES=30
MAX_CONCURRENT_SCRAPERS=5
REQUEST_TIMEOUT=30
# user_agent is derived from the package __version__ (no USER_AGENT env override)

# Security
SECRET_KEY=change-me-in-production
API_KEY_HEADER=X-API-Key
```

### 6.2 Settings Management

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./data/interntrack.db"
    
    # AI
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    gemini_api_key: Optional[str] = None
    
    # Scraper
    scrape_interval_minutes: int = 30
    max_concurrent_scrapers: int = 5
    
    # Security
    secret_key: str = "change-me"

    # CORS
    cors_origins: list[str] = ["*"]
    cors_allow_all: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

### 6.3 CORS Configuration

CORS is settings-driven (`src/interntrack/config.py`) and parsed from comma-separated
environment variables:

```env
# Comma-separated list of allowed origins
CORS_ORIGINS=https://app.example.com,https://admin.example.com
CORS_ALLOW_ALL=false
CORS_ALLOW_METHODS=GET,POST,PUT,PATCH,DELETE
CORS_ALLOW_HEADERS=*
```

When `CORS_ALLOW_ALL=true` (default) `allow_credentials` is `False` — the
spec-correct combination with the `*` wildcard. When origins are restricted,
`allow_credentials` becomes `True`.

`Settings.validate_security()` logs warnings at startup when the default secret
key is still in use or CORS allows all origins, so misconfiguration surfaces
early in production.

---

## 7. Security Architecture

### 7.1 Authentication Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │────▶│  API Key │────▶│  FastAPI  │
│          │     │  Header  │     │  Middleware│
└──────────┘     └──────────┘     └─────┬────┘
                                        │
                                        ▼
                                 ┌──────────────┐
                                 │  Token Store │
                                 │  (SQLite)    │
                                 └──────────────┘
```

### 7.2 Security Measures

| Layer | Measure |
|-------|---------|
| **Transport** | HTTPS (via reverse proxy) |
| **Authentication** | API Key + JWT tokens |
| **Authorization** | Role-based access (future) |
| **Input Validation** | Pydantic models |
| **Rate Limiting** | Per-IP throttling |
| **Data Protection** | Encrypted secrets at rest |
| **Scraping Ethics** | robots.txt compliance, throttling |

### 7.3 Secrets Management

```python
from cryptography.fernet import Fernet

class SecretManager:
    def __init__(self, key: str):
        self._cipher = Fernet(key.encode())
    
    def encrypt(self, value: str) -> str:
        return self._cipher.encrypt(value.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        return self._cipher.decrypt(encrypted.encode()).decode()
```

---

## 8. Error Handling Architecture

### 8.1 Exception Hierarchy

```python
# Base application exceptions
class AppException(Exception):
    def __init__(self, message: str, code: str, status: int = 500):
        self.message = message
        self.code = code
        self.status = status

    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": {},
            }
        }

class NotFoundError(AppException):
    def __init__(self, resource: str, id: str):
        super().__init__(
            f"{resource} with id {id} not found",
            "NOT_FOUND",
            404
        )
        self.details = {"resource": resource, "identifier": id}

class ScrapingError(AppException):
    def __init__(self, source: str, reason: str):
        super().__init__(
            f"Scraping failed for {source}: {reason}",
            "SCRAPING_ERROR",
            422
        )

class NotificationError(AppException):
    def __init__(self, channel: str, reason: str):
        super().__init__(
            f"Notification failed for {channel}: {reason}",
            "NOTIFICATION_ERROR",
            502
        )
```

### 8.2 Exception Handlers (FastAPI)

`main.py` registers two handlers:

1. **`domain_exception_handler`** for `AppException` — returns `exc.status` and
   `exc.to_dict()` so domain errors (404/409/422/502) surface with their correct
   HTTP status instead of being masked as 500.
2. **`global_exception_handler`** for unexpected `Exception` — returns 500 with a
   consistent payload and debug detail gated behind `settings.debug`.

Both handlers share one error contract:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Job with identifier 'abc' not found",
    "details": { "resource": "Job", "identifier": "abc" }
  }
}
```

> ⚠️ Exception-handler ordering matters: Starlette routes `Exception` to
> `ServerErrorMiddleware` (outermost) while `HTTPException` (4xx) and `AppException`
> handlers run inside `ExceptionMiddleware`, so FastAPI's built-in HTTPException
> responses are preserved.

### 8.3 Retry Strategy

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(ScrapingError)
)
async def scrape_with_retry(scraper: BaseScraper, query: JobQuery):
    return await scraper.fetch(query)
```

---

## 9. Caching Architecture

### 9.1 Cache Strategy

| Data Type | TTL | Invalidation |
|-----------|-----|--------------|
| Job listings | 1 hour | On update |
| Search results | 5 min | Time-based |
| User preferences | 24 hours | On change |
| Report data | 1 hour | On generation |
| API responses | 5 min | Time-based |

### 9.2 Cache Implementation

```python
from functools import wraps
import hashlib

def cached(ttl_seconds: int = 300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = _make_key(func.__name__, args, kwargs)
            
            # Check cache
            cached_value = await cache.get(cache_key)
            if cached_value:
                return cached_value
            
            # Execute and cache
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl=ttl_seconds)
            return result
        return wrapper
    return decorator
```

---

## 10. Deployment Architecture

### 10.1 Docker Deployment

```yaml
# docker-compose.yml structure
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://db:5432/interntrack
    depends_on:
      - db
      - redis
      - ollama
  
  dashboard:
    build: .
    command: streamlit run dashboard/app.py
    ports:
      - "8501:8501"
  
  worker:
    build: .
    command: python -m interntrack.worker
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
  
  ollama:
    image: ollama/ollama
    volumes:
      - ollama_data:/root/.ollama

volumes:
  postgres_data:
  ollama_data:
```

### 10.2 Production Setup

```
┌─────────────────────────────────────────────────────────┐
│                     Load Balancer                        │
│                    (nginx / Traefik)                     │
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   API (x3)   │ │ Dashboard    │ │ Worker (x2)  │
│   FastAPI    │ │ Streamlit    │ │ Background   │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ PostgreSQL   │ │ Redis        │ │ Ollama       │
│ Primary      │ │ Cache        │ │ Local LLM    │
└──────────────┘ └──────────────┘ └──────────────┘
```

---

## 11. Scalability Considerations

### 11.1 Current Scale (v1)
- **Users**: Single user / small team
- **Jobs**: ~10,000 jobs/month
- **Database**: SQLite
- **Deployment**: Single Docker Compose

### 11.2 Growth Path (v2+)
- **Users**: Multi-user with auth
- **Jobs**: 100,000+ jobs/month
- **Database**: PostgreSQL + read replicas
- **Cache**: Redis cluster
- **Queue**: Celery/RQ for heavy tasks
- **Search**: Elasticsearch/Meilisearch

### 11.3 Performance Targets

| Metric | Target |
|--------|--------|
| API Response Time | < 200ms (p95) |
| Scrape Job Time | < 5s per source |
| Report Generation | < 30s |
| Notification Delivery | < 10s |
| Dashboard Load | < 3s |

---

## 12. Monitoring & Observability

### 12.1 Metrics to Track

| Category | Metrics |
|----------|---------|
| **Scraping** | Success rate, duration, jobs found |
| **API** | Request count, latency, errors |
| **Database** | Query time, connections, size |
| **Notifications** | Delivery rate, failures |
| **System** | CPU, memory, disk |

### 12.2 Logging Strategy

```python
import structlog

logger = structlog.get_logger()

# Structured logging
logger.info(
    "job.scraped",
    source="linkedin",
    job_count=15,
    duration_ms=1234
)

logger.error(
    "scrape.failed",
    source="indeed",
    error="Connection timeout",
    retry_count=3
)
```

---

## 13. Future Enhancements

### Phase 2
- [ ] Multi-user support with OAuth
- [ ] Resume parsing and matching
- [ ] Calendar integration
- [ ] Mobile app (Flutter)

### Phase 3
- [ ] Chrome extension for job saving
- [ ] AI cover letter generation
- [ ] Salary prediction model
- [ ] Company reviews aggregation

### Phase 4
- [ ] Job marketplace
- [ ] Mentorship matching
- [ ] Interview prep tools
- [ ] Career path visualization

---

## Appendix A: Decision Log

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| FastAPI over Flask | Native async, better performance | Flask, Django |
| SQLAlchemy over Tortoise | Mature, better ecosystem | Tortoise ORM, Prisma |
| Streamlit over React | Faster development, Python-native | React, Vue, Svelte |
| SQLite → PostgreSQL | Simple start, easy upgrade | PostgreSQL from start |
| Ollama for AI | Free, private, local | OpenAI, Anthropic |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 2: Folder Structure](./02-folder-structure.md)
