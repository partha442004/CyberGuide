# CyberShield Career Intelligence Platform (CSCIP) - Software Architecture

## 1. System Overview

**CyberShield Career Intelligence Platform (CSCIP)** is the world's most advanced FREE AI-powered cybersecurity career intelligence platform. It continuously discovers, verifies, analyzes, classifies, ranks, predicts, and notifies cybersecurity opportunities across India and USA.

### 1.1 Vision
A self-hosted, open-source AI ecosystem that eliminates manual job searching for cybersecurity professionals. The system becomes an AI career assistant that automatically discovers opportunities, verifies legitimacy, detects scams, matches skills, and provides intelligent recommendations.

### 1.2 Core Capabilities

| Capability | Description |
|------------|-------------|
| **Intelligent Discovery** | AI-powered scraping from 40+ sources with smart query optimization |
| **Deduplication Engine** | Semantic similarity, hash matching, embedding-based dedup |
| **Verification Engine** | Real-time job verification, link checking, deadline validation |
| **Scam Detection** | AI-powered scam confidence scoring, fake recruiter detection |
| **Resume Intelligence** | ATS scoring, skill matching, improvement suggestions |
| **Predictive Analytics** | Hiring predictions, salary estimation, market trends |
| **17 AI Engines** | Specialized engines for every career intelligence need |
| **Multi-Channel Notifications** | Telegram, Email, Discord, Slack, Push with instant alerts |
| **Smart Dashboard** | Dark/Light mode, charts, analytics, watchlists, timelines |
| **Learning Integration** | Skill gap analysis with curated learning resources |

---

## 2. Architecture Style

### 2.1 Event-Driven Microservices Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CSCIP Architecture                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    PRESENTATION LAYER                                │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │    │
│  │  │   REST API   │  │  Dashboard   │  │     Mobile API (Future)  │  │    │
│  │  │   (FastAPI)  │  │ (Streamlit)  │  │     (FastAPI + React)    │  │    │
│  │  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │    │
│  └─────────┼─────────────────┼───────────────────────┼────────────────┘    │
│            │                 │                       │                      │
│  ┌─────────┴─────────────────┴───────────────────────┴────────────────┐    │
│  │                    APPLICATION LAYER                                │    │
│  │                                                                     │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │                    ORCHESTRATION ENGINE                      │   │    │
│  │  │  • Discovery Orchestrator  • Notification Orchestrator       │   │    │
│  │  │  • Report Generator        • Scheduler Manager               │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  │                                                                     │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │                    AI ENGINE LAYER (17 Engines)              │   │    │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │   │    │
│  │  │  │Dedup     │ │Verify    │ │Scam Det  │ │Resume    │       │   │    │
│  │  │  │Engine    │ │Engine    │ │Engine    │ │Engine    │       │   │    │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │   │    │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │   │    │
│  │  │  │Portfolio │ │Interview │ │Skill Mkt │ │Salary    │       │   │    │
│  │  │  │Engine    │ │Engine    │ │Engine    │ │Engine    │       │   │    │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │   │    │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │   │    │
│  │  │  │Hiring Cal│ │Prediction│ │Cyber News│ │Cert      │       │   │    │
│  │  │  │Engine    │ │Engine    │ │Engine    │ │Engine    │       │   │    │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │   │    │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │   │    │
│  │  │  │CTF       │ │Bug Bounty│ │Event     │                    │   │    │
│  │  │  │Engine    │ │Engine    │ │Engine    │                    │   │    │
│  │  │  └──────────┘ └──────────┘ └──────────┘                    │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  │                                                                     │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │                    BUSINESS SERVICES                        │   │    │
│  │  │  • Job Service        • Application Service                 │   │    │
│  │  │  • User Service       • Notification Service                │   │    │
│  │  │  • Report Service     • Learning Service                    │   │    │
│  │  │  • Watchlist Service  • Analytics Service                   │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    DOMAIN LAYER (Core Business Logic)               │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │    │
│  │  │ Entities │ │  Enums   │ │ Exceptions│ │ Value Obj│ │Events  │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    INFRASTRUCTURE LAYER                              │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │    │
│  │  │Database  │ │Scraper   │ │AI/LLM    │ │Cache     │ │Queue   │  │    │
│  │  │Adapter   │ │Adapter   │ │Adapter   │ │Adapter   │ │Adapter │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Layer Responsibilities

| Layer | Responsibility | Dependencies |
|-------|---------------|--------------|
| **Presentation** | HTTP handling, request/response, WebSocket, auth | Application |
| **Application** | Use case orchestration, DTOs, validation, event publishing | Domain |
| **AI Engines** | Specialized AI processing, ML inference, pattern matching | Domain, Infrastructure |
| **Domain** | Business logic, entities, repository interfaces, domain events | None (innermost) |
| **Infrastructure** | External integrations, DB access, scraping, caching | Domain |

### 2.3 Key Principles

- **Event-Driven**: Loose coupling via domain events
- **CQRS**: Separate read/write models for scalability
- **Repository Pattern**: Abstract data access
- **Dependency Injection**: Constructor injection throughout
- **SOLID Principles**: Single responsibility, open/closed, etc.
- **Clean Architecture**: Domain at center, dependencies point inward

---

## 3. Technology Stack

### 3.1 Core Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Language** | Python 3.11+ | Async support, rich ecosystem, AI/ML libraries |
| **Web Framework** | FastAPI | Async, OpenAPI docs, performance, WebSocket support |
| **ORM** | SQLAlchemy 2.0+ | Async support, mature, excellent ecosystem |
| **Migrations** | Alembic | Schema versioning, rollback support |
| **Database** | SQLite (dev) → PostgreSQL (prod) | Progressive scaling |
| **Cache** | Redis | Rate limiting, caching, pub/sub |
| **Task Queue** | APScheduler + asyncio | Simplicity, no broker needed for v1 |
| **Event Bus** | asyncio.Queue + Redis Pub/Sub | Event-driven architecture |

### 3.2 Scraping Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **HTTP Client** | httpx (async) | Async, modern API, connection pooling |
| **HTML Parsing** | BeautifulSoup4 | Reliable, battle-tested |
| **Browser Automation** | Playwright | JS-heavy sites, anti-bot bypass |
| **Feed Parsing** | feedparser | RSS/Atom support |
| **Rate Limiting** | aiolimiter | Async rate limiting |
| **Retry Logic** | tenacity | Exponential backoff, circuit breaker |

### 3.3 AI/ML Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Local LLM** | Ollama | Free, private, offline capable |
| **Cloud LLM** | Gemini Free API | Generous free tier |
| **Embeddings** | sentence-transformers | Semantic similarity |
| **NLP** | spaCy / NLTK | Text processing, entity extraction |
| **Data Analysis** | Pandas, NumPy | Data manipulation |
| **ML Models** | scikit-learn | Classification, clustering |
| **Similarity** | TF-IDF + Cosine | Skill matching, dedup |

### 3.4 Notification Stack

| Channel | Technology | Free Tier |
|---------|------------|-----------|
| Telegram | python-telegram-bot | Unlimited |
| Email | Gmail SMTP | 500/day |
| Discord | discord.py webhook | Unlimited |
| Slack | slack-sdk webhook | Limited |
| Push | Web Push API | Unlimited |
| WebSocket | FastAPI WebSocket | Real-time dashboard |

### 3.5 Frontend Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Dashboard** | Streamlit | Fast prototyping, Python-native |
| **Charts** | Plotly + Chart.js | Interactive visualizations |
| **Styling** | Custom CSS | Dark/Light mode, responsive |
| **Export** | Jinja2 + WeasyPrint | PDF/HTML report generation |

### 3.6 DevOps Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Containerization** | Docker + Compose | Consistent environments |
| **CI/CD** | GitHub Actions | Free for public repos |
| **Secrets** | .env + Fernet encryption | Security |
| **Logging** | structlog | Structured, JSON logging |
| **Monitoring** | Prometheus + Grafana (optional) | Metrics, alerting |

---

## 4. Data Flow Architecture

### 4.1 Discovery Pipeline (Event-Driven)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DISCOVERY PIPELINE                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────┐    ┌──────────┐    ┌────────────┐    ┌────────────────────┐   │
│  │ Sources │───▶│ Scraper  │───▶│  Raw Jobs  │───▶│  Event: JobsFound  │   │
│  │ (40+)   │    │ Registry │    │  Buffer    │    │                    │   │
│  └─────────┘    └──────────┘    └────────────┘    └─────────┬──────────┘   │
│                                                              │              │
│                         ┌────────────────────────────────────┘              │
│                         ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PROCESSING PIPELINE                               │   │
│  │                                                                      │   │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │   │
│  │  │Dedup     │───▶│Scam Det  │───▶│Verify    │───▶│Classify  │     │   │
│  │  │Engine    │    │Engine    │    │Engine    │    │(AI)      │     │   │
│  │  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │   │
│  │       │               │               │               │            │   │
│  │       ▼               ▼               ▼               ▼            │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │              Event: JobsProcessed                            │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                         │                                                   │
│                         ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    POST-PROCESSING                                   │   │
│  │                                                                      │   │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │   │
│  │  │Watchlist │    │Notify    │    │Analytics │    │Store     │     │   │
│  │  │Check     │    │Alert     │    │Update    │    │Database  │     │   │
│  │  └──────────┘    └──────────┘    └──────────┘    └──────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 AI Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AI PROCESSING PIPELINE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Input: Raw Job Data                                                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 1: Validation & Enrichment                                    │   │
│  │  • Link verification (HTTP HEAD check)                              │   │
│  │  • Deadline validation                                              │   │
│  │  • Company info enrichment                                          │   │
│  │  • Location normalization                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 2: Security Analysis                                          │   │
│  │  • Scam detection (AI + rules)                                      │   │
│  │  • Fake recruiter detection                                         │   │
│  │  • Suspicious URL analysis                                          │   │
│  │  • Training fee detection                                           │   │
│  │  • Scam Confidence Score (0-100)                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 3: Classification & Tagging                                   │   │
│  │  • Job type classification (internship, full-time, etc.)            │   │
│  │  • Experience level detection                                       │   │
│  │  • Skill extraction (required + preferred)                          │   │
│  │  • Category tagging (Blue Team, Red Team, SOC, etc.)                │   │
│  │  • Salary/stipend extraction                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 4: Matching & Scoring                                         │   │
│  │  • Resume match score (if resume uploaded)                          │   │
│  │  • Skill gap analysis                                               │   │
│  │  • Priority scoring                                                 │   │
│  │  • Urgency detection (deadline approaching)                         │   │
│  │  • Opportunity ranking                                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Stage 5: Prediction & Insights                                      │   │
│  │  • Hiring probability prediction                                    │   │
│  │  • Salary estimation (if missing)                                   │   │
│  │  • Company expansion detection                                      │   │
│  │  • Market trend analysis                                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Output: Enriched, Scored, Classified Job                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Notification Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NOTIFICATION FLOW                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐         │
│  │ Trigger  │────▶│ Rule     │────▶│ Channel  │────▶│ Delivery │         │
│  │ Event    │     │ Engine   │     │ Router   │     │ Manager  │         │
│  └──────────┘     └──────────┘     └──────────┘     └──────────┘         │
│       │               │                │                │                  │
│       ▼               ▼                ▼                ▼                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Triggers:                                                          │   │
│  │  • New job matching watchlist keyword                               │   │
│  │  • New job from watched company                                     │   │
│  │  • Job closing soon (reminder)                                      │   │
│  │  • Daily/Weekly/Monthly report ready                                │   │
│  │  • Application status change                                        │   │
│  │  • New CTF/Event/Bug Bounty                                         │   │
│  │  • Certification opportunity                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Channels:                                                          │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │   │
│  │  │ Telegram │ │  Email   │ │ Discord  │ │  Slack   │ │  Push  │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Message Types:                                                      │   │
│  │  • Instant Alert (new matching job)                                  │   │
│  │  • Daily Report (6 AM)                                               │   │
│  │  │  • New internships/jobs                                           │   │
│  │  │  • Remote jobs                                                    │   │
│  │  │  • Government jobs                                                │   │
│  │  │  • Highest salary/stipend                                         │   │
│  │  │  • Closing today/tomorrow                                         │   │
│  │  │  • Must Apply                                                     │   │
│  │  │  • Top Companies/Skills                                           │   │
│  │  • Weekly Report (Monday 8 AM)                                       │   │
│  │  │  • Hiring trends                                                  │   │
│  │  │  • Salary/Skill trends                                            │   │
│  │  │  • Top Cities                                                     │   │
│  │  │  • Upcoming hiring                                                │   │
│  │  │  │  New certifications                                            │   │
│  │  │  │  Upcoming CTFs                                                 │   │
│  │  • Monthly Report (1st of month)                                     │   │
│  │     • Complete analytics                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. AI Engines Architecture

### 5.1 Engine Registry Pattern

```python
# All AI engines follow this pattern
class BaseEngine(ABC):
    """Base class for all AI engines."""
    
    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Unique engine identifier."""
        pass
    
    @abstractmethod
    async def process(self, data: Any) -> Any:
        """Process input data and return results."""
        pass
    
    async def validate_input(self, data: Any) -> bool:
        """Validate input data before processing."""
        pass


class EngineRegistry:
    """Registry for managing AI engines."""
    
    def __init__(self):
        self._engines: Dict[str, BaseEngine] = {}
    
    def register(self, engine: BaseEngine) -> None:
        self._engines[engine.engine_name] = engine
    
    async def execute(self, engine_name: str, data: Any) -> Any:
        engine = self._engines.get(engine_name)
        if not engine:
            raise EngineNotFoundError(engine_name)
        
        if not await engine.validate_input(data):
            raise InvalidInputError(engine_name)
        
        return await engine.process(data)
```

### 5.2 17 AI Engines

| # | Engine | Purpose | Input | Output |
|---|--------|---------|-------|--------|
| 1 | **DeduplicationEngine** | Remove duplicate jobs | List[RawJob] | List[UniqueJob] |
| 2 | **VerificationEngine** | Verify job legitimacy | Job | VerificationResult |
| 3 | **ScamDetectionEngine** | Detect scams/fraud | Job | ScamScore |
| 4 | **ResumeEngine** | Analyze resume vs jobs | Resume + Jobs | MatchResults |
| 5 | **PortfolioEngine** | Analyze GitHub/LinkedIn | Portfolio | Recommendations |
| 6 | **InterviewEngine** | Generate interview prep | Company + Role | Questions |
| 7 | **SkillMarketEngine** | Analyze skill trends | Jobs | TrendReport |
| 8 | **SalaryEngine** | Estimate salaries | Job | SalaryEstimate |
| 9 | **HiringCalendarEngine** | Predict hiring cycles | HistoricalData | Calendar |
| 10 | **PredictionEngine** | Predict opportunities | Patterns | Predictions |
| 11 | **CyberNewsEngine** | Analyze security news | News | HiringInsights |
| 12 | **CertificationEngine** | Track certifications | CertData | Opportunities |
| 13 | **CTFEngine** | Track CTF competitions | CTFData | Events |
| 14 | **BugBountyEngine** | Track bug bounty programs | BountyData | Programs |
| 15 | **EventEngine** | Track conferences/meetups | EventData | Events |
| 16 | **LearningEngine** | Recommend learning | Skills | Resources |
| 17 | **ClassificationEngine** | Classify opportunities | Job | Classification |

---

## 6. Domain Events

### 6.1 Event Types

```python
class DomainEvent:
    """Base domain event."""
    event_id: str
    timestamp: datetime
    aggregate_id: str


# Discovery Events
class JobsDiscovered(DomainEvent):
    source: str
    job_count: int
    jobs: List[dict]


class JobProcessed(DomainEvent):
    job_id: str
    processing_stage: str
    result: dict


# Scam Detection Events
class ScamDetected(DomainEvent):
    job_id: str
    scam_score: float
    scam_reasons: List[str]


# Notification Events
class NotificationTriggered(DomainEvent):
    channel: str
    notification_type: str
    recipients: List[str]


# Watchlist Events
class WatchlistMatched(DomainEvent):
    watchlist_id: str
    match_type: str  # keyword, company
    matched_value: str
    job_id: str
```

### 6.2 Event Bus

```python
class EventBus:
    """Async event bus for domain events."""
    
    def __init__(self):
        self._handlers: Dict[Type[DomainEvent], List[Callable]] = {}
    
    def subscribe(self, event_type: Type[DomainEvent], handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def publish(self, event: DomainEvent):
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            await handler(event)
```

---

## 7. Security Architecture

### 7.1 Authentication & Authorization

```
┌─────────────────────────────────────────────────────────────────┐
│                    Security Architecture                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │   Client     │────▶│  API Gateway │────▶│   Auth       │   │
│  │   (Browser)  │     │  (FastAPI)   │     │   Middleware  │   │
│  └──────────────┘     └──────────────┘     └──────┬───────┘   │
│                                                     │           │
│                                                     ▼           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Security Layers                        │   │
│  │                                                          │   │
│  │  • HTTPS (via reverse proxy)                             │   │
│  │  • API Key Authentication                                │   │
│  │  • Rate Limiting (per-IP)                                │   │
│  │  • Input Validation (Pydantic)                           │   │
│  │  • SQL Injection Prevention (SQLAlchemy ORM)             │   │
│  │  • XSS Prevention (Output encoding)                      │   │
│  │  • CSRF Protection (SameSite cookies)                    │   │
│  │  • Encrypted Secrets (Fernet)                            │   │
│  │  • robots.txt Compliance                                 │   │
│  │  • Respect Terms of Service                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Scam Detection Rules

```python
SCAM_INDICATORS = {
    # Red Flags (High Confidence)
    "training_fee": {"weight": 0.9, "description": "Requests payment for training"},
    "advance_payment": {"weight": 0.95, "description": "Requests advance payment"},
    "disposable_email": {"weight": 0.7, "description": "Uses temporary email domain"},
    "fake_domain": {"weight": 0.8, "description": "Domain doesn't match company"},
    "typosquatting": {"weight": 0.85, "description": "Similar to legitimate domain"},
    
    # Yellow Flags (Medium Confidence)
    "vague_description": {"weight": 0.4, "description": "Job description is vague"},
    "no_company_info": {"weight": 0.5, "description": "Missing company details"},
    "unrealistic_salary": {"weight": 0.6, "description": "Salary seems too good"},
    "urgency_pressure": {"weight": 0.5, "description": "Creates false urgency"},
    
    # Orange Flags (Lower Confidence)
    "copied_description": {"weight": 0.3, "description": "Description copied from elsewhere"},
    "suspicious_url": {"weight": 0.6, "description": "URL has suspicious patterns"},
    "no_contact_info": {"weight": 0.3, "description": "No valid contact information"},
}
```

---

## 8. Caching Strategy

| Data Type | TTL | Invalidation | Strategy |
|-----------|-----|--------------|----------|
| Job listings | 1 hour | On update | Write-through |
| Search results | 5 min | Time-based | Cache-aside |
| User preferences | 24 hours | On change | Write-through |
| Report data | 1 hour | On generation | Write-behind |
| API responses | 5 min | Time-based | Cache-aside |
| Skill trends | 6 hours | Daily refresh | Write-behind |
| Company info | 24 hours | Weekly refresh | Cache-aside |
| Watchlist matches | Real-time | Event-driven | Event-sourced |

---

## 9. Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| API Response Time | < 200ms (p95) | ~150ms |
| Scrape Job Time | < 5s per source | ~3s |
| Dedup Processing | < 100ms per job | ~50ms |
| Scam Detection | < 500ms per job | ~200ms |
| Resume Matching | < 2s | ~1.5s |
| Report Generation | < 30s | ~20s |
| Notification Delivery | < 10s | ~5s |
| Dashboard Load | < 3s | ~2s |

---

## 10. Scalability Path

### Phase 1 (Current)
- **Users**: Single user / small team
- **Jobs**: ~10,000 jobs/month
- **Database**: SQLite
- **Deployment**: Single Docker Compose

### Phase 2
- **Users**: 100+ users
- **Jobs**: 100,000+ jobs/month
- **Database**: PostgreSQL + read replicas
- **Cache**: Redis cluster
- **Queue**: Celery for heavy tasks

### Phase 3
- **Users**: 10,000+ users
- **Jobs**: 1,000,000+ jobs/month
- **Database**: PostgreSQL + sharding
- **Search**: Elasticsearch/Meilisearch
- **ML**: Dedicated inference servers

---

## Appendix A: Decision Log

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| FastAPI over Flask | Native async, better performance | Flask, Django |
| SQLAlchemy over Tortoise | Mature, better ecosystem | Tortoise ORM, Prisma |
| Streamlit over React | Faster development, Python-native | React, Vue, Svelte |
| SQLite → PostgreSQL | Simple start, easy upgrade | PostgreSQL from start |
| Ollama for AI | Free, private, local | OpenAI, Anthropic |
| Event-driven architecture | Loose coupling, scalability | Monolithic |
| 17 specialized engines | Better separation of concerns | Single AI service |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 2: Folder Structure](./02-folder-structure.md)
