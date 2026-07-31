# CyberShield Career Intelligence Platform (CSCIP) - Docker

## Overview

CSCIP uses Docker for consistent development and production environments.

---

## Docker Images

### API Image

```dockerfile
# Dockerfile

FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application
COPY src/ ./src/
COPY migrations/ ./migrations/

# Create data directory
RUN mkdir -p /app/data && chown -R nobody:nogroup /app/data

USER nobody

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "cybershield.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Dashboard Image

```dockerfile
# Dockerfile.dashboard

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY dashboard/ ./dashboard/

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

---

## Docker Compose Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| api | cybershield/api | 8000 | FastAPI backend |
| dashboard | cybershield/dashboard | 8501 | Streamlit frontend |
| worker | cybershield/api | - | Background tasks |
| db | postgres:16-alpine | 5432 | PostgreSQL database |
| redis | redis:7-alpine | 6379 | Cache & queue |
| ollama | ollama/ollama | 11434 | Local LLM |

---

## Useful Commands

```bash
# Build all images
docker-compose build

# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f api
docker-compose logs -f worker

# Execute command in container
docker-compose exec api alembic upgrade head
docker-compose exec api python -m cybershield.scripts.seed_data

# Stop and remove
docker-compose down

# Stop and remove volumes (reset data)
docker-compose down -v

# Restart specific service
docker-compose restart api
```

---

**Module Status**: ✅ Complete

**Next Module**: [Module 17: CI/CD](./17-cicd.md)
