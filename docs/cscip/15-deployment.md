# CyberShield Career Intelligence Platform (CSCIP) - Deployment

## Overview

CSCIP supports Docker-based deployment with Docker Compose for production and local development.

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       DEPLOYMENT ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Docker Compose Services                           │   │
│  │                                                                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │   API    │  │Dashboard │  │  Worker  │  │   DB     │          │   │
│  │  │ FastAPI  │  │Streamlit │  │Scheduler │  │PostgreSQL│          │   │
│  │  │  :8000   │  │  :8501   │  │          │  │  :5432   │          │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │   │
│  │                                                                      │   │
│  │  ┌──────────┐  ┌──────────┐                                       │   │
│  │  │  Redis   │  │  Ollama  │                                       │   │
│  │  │  :6379   │  │  :11434  │                                       │   │
│  │  └──────────┘  └──────────┘                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Docker Compose Configuration

```yaml
# docker-compose.yml

version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://cybershield:password@db:5432/cybershield
      - REDIS_URL=redis://redis:6379/0
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  dashboard:
    build:
      context: .
      dockerfile: Dockerfile.dashboard
    ports:
      - "8501:8501"
    environment:
      - API_URL=http://api:8000
    depends_on:
      api:
        condition: service_healthy
    restart: unless-stopped

  worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: python -m cybershield.worker
    environment:
      - DATABASE_URL=postgresql+asyncpg://cybershield:password@db:5432/cybershield
      - REDIS_URL=redis://redis:6379/0
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=cybershield
      - POSTGRES_USER=cybershield
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cybershield"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped

volumes:
  postgres_data:
  ollama_data:
```

---

## Dockerfile

```dockerfile
# Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY migrations/ ./migrations/

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "cybershield.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Environment Variables

```env
# .env

# Database
DATABASE_URL=postgresql+asyncpg://cybershield:password@db:5432/cybershield

# Redis
REDIS_URL=redis://redis:6379/0

# AI Services
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3
GEMINI_API_KEY=

# Notifications
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
SLACK_WEBHOOK_URL=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# Scraper
SCRAPE_INTERVAL_MINUTES=30
MAX_CONCURRENT_SCRAPERS=5
REQUEST_TIMEOUT=30
# user_agent is derived from the package __version__ (no USER_AGENT env override)

# Security
SECRET_KEY=change-me-in-production
API_KEY_HEADER=X-API-Key

# Application
APP_NAME=CyberShield
APP_VERSION=1.16.0
DEBUG=false
```

---

## Deployment Commands

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Reset database
docker-compose down -v
docker-compose up -d --build

# Run migrations
docker-compose exec api alembic upgrade head

# Seed database
docker-compose exec api python -m cybershield.scripts.seed_data

# View service status
docker-compose ps
```

---

## Schema Upgrades for Existing Deployments

> Applies to deployments that already ran `001_initial_schema` **before** the
> 2026-08-01 hardening pass.

`001_initial_schema.py` was updated to include the `companies.is_trusted` column.
Fresh installs get it automatically, but an existing database that already applied
the old migration will **not** — edit the initial migration only works for new
schemas. Apply this manually once on the running database:

```sql
ALTER TABLE companies ADD COLUMN is_trusted BOOLEAN DEFAULT 0;
```

PostgreSQL equivalent:

```sql
ALTER TABLE companies ADD COLUMN is_trusted BOOLEAN NOT NULL DEFAULT FALSE;
```

Then verify the company trust-status read/update endpoints respond normally. If
you prefer a tracked migration, generate a new revision with
`alembic revision -m "add companies.is_trusted"` and add the same `op.add_column`
step.

---

## Production Checklist

- [ ] Set secure SECRET_KEY
- [ ] Configure production database credentials
- [ ] Set up SSL/TLS (nginx reverse proxy)
- [ ] Configure firewall rules
- [ ] Set up monitoring (Prometheus + Grafana)
- [ ] Configure log aggregation
- [ ] Set up automated backups
- [ ] Configure rate limiting
- [ ] Set up CI/CD pipeline

---

**Module Status**: ✅ Complete

**Next Module**: [Module 16: Docker](./16-docker.md)
