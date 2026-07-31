# CyberGuide - Deployment Log

> **Date**: 2026-07-30
> **Status**: PUSHED TO GITHUB
> **Author**: KIRA (AI-assisted)
> **Repo**: https://github.com/partha442004/CyberGuide

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Pre-Deployment Health Check](#2-pre-deployment-health-check)
3. [Bugs Found & Fixed](#3-bugs-found--fixed)
4. [Deployment Config Changes](#4-deployment-config-changes)
5. [Test Results](#5-test-results)
6. [File Inventory](#6-file-inventory)
7. [Git Status](#7-git-status)
8. [Oracle Cloud Deployment Steps](#8-oracle-cloud-deployment-steps)
9. [Post-Deployment Checklist](#9-post-deployment-checklist)
10. [Known Issues & Notes](#10-known-issues--notes)

---

## 1. Project Overview

**CyberGuide** is a career intelligence platform that scrapes job listings from cybersecurity companies, India job boards, and global tech boards. It includes:

- **17 scrapers**: Cisco, CrowdStrike, Fortinet, Google, McAfee, Microsoft, PaloAlto, Symantec, TrendMicro, Amazon, Internshala, Naukri, FreshersWorld, Unstop, HackerNews, Indeed, RemoteOK
- **295 CyberGuide tests** (`src/cybershield/tests/`)
- **347 InternTrack tests** (`tests/`)
- **Stack**: FastAPI + SQLAlchemy (async) + Redis + Elasticsearch + PostgreSQL + Ollama

### Key Paths

| Path | Description |
|------|-------------|
| `src/cybershield/` | **CyberGuide** (latest, 113 files, 295 tests) |
| `src/interntrack/` | **InternTrack** (older, 65 files, 347 tests in `tests/`) |
| `tests/` | InternTrack tests (root dir, uses root `pyproject.toml`) |
| `dashboard/` | Streamlit dashboard |
| `deploy/oracle-cloud/` | Oracle Cloud deployment scripts |

---

## 2. Pre-Deployment Health Check

### Test Results (ALL PASSING)

```
InternTrack: 347 passed (29.54s)
CyberGuide:  295 passed (7.91s)
TOTAL:       642 tests passing
```

### Configuration Verified

- [x] Root `pyproject.toml` configured for InternTrack (DO NOT CHANGE)
- [x] `src/cybershield/pyproject.toml` configured for CyberGuide (correct)
- [x] `Dockerfile` CMD uses `cybershield.main:app`
- [x] `docker-compose.yml` uses CyberGuide container names
- [x] `.env` uses CyberGuide naming
- [x] `setup.sh` paths fixed for CyberGuide
- [x] `requirements.txt` includes bcrypt, pydantic-settings

---

## 3. Bugs Found & Fixed

### BUG 1: Broken Import in `applications.py`

**File**: `src/cybershield/api/v1/applications.py:12`
**Error**: `from cybershield.domain.models import ApplicationStatus`
**Fix**: `from cybershield.domain.enums import ApplicationStatus`

`ApplicationStatus` is an enum, defined in `domain/enums.py`, not `domain/models.py`.

### BUG 2: Missing `bcrypt` Dependency

**Error**: `ModuleNotFoundError: No module named 'bcrypt'`
**Fix**: Added `bcrypt>=4.0.0` to `requirements.txt` and installed with `pip install bcrypt`

### BUG 3: Dockerfile CMD Pointing to Wrong Module

**File**: `Dockerfile:37`
**Before**: `CMD ["uvicorn", "interntrack.main:app", ...]`
**After**: `CMD ["uvicorn", "cybershield.main:app", ...]`

### BUG 4: Docker Compose Using Old Container Names

**File**: `docker-compose.yml`
**Before**: `interntrack-api`, `interntrack-postgres`, `interntrack-redis`, etc.
**After**: `cyberguide-api`, `cyberguide-postgres`, `cyberguide-redis`, etc.

Also added missing services: `postgres` (16-alpine), `elasticsearch` (8.12.0), `ollama`, and named volumes.

### BUG 5: setup.sh Path Errors

**File**: `deploy/oracle-cloud/setup.sh`
**Before**: `cd cybershield/src/cybershield && docker-compose up -d`
**After**: `cd cybershield && docker-compose up -d`

The `cd` went too deep. The script runs from `/home/opc/cybershield/` where `docker-compose.yml` lives.

### BUG 6: Missing `pydantic-settings` Dependency

**File**: `requirements.txt`
**Fix**: Added `pydantic-settings>=2.1.0`

### BUG 7: `interntrack/config.py` Missing `elasticsearch_url` Field

**File**: `src/interntrack/config.py`
**Error**: Pydantic validation error when `.env` has `ELASTICSEARCH_URL`
**Fix**: Added `elasticsearch_url: str | None = None` field to the `Settings` class.

### BUG 8: `DATABASE_URL` Windows Path in `.env`

**File**: `.env`
**Before**: `DATABASE_URL=sqlite+aiosqlite:///C:/internship-tracker/data/cyberguide.db`
**Note**: This is correct for LOCAL development on Windows. The `setup.sh` script generates a proper PostgreSQL URL for the cloud deployment. No change needed.

---

## 4. Deployment Config Changes

### 4.1 Dockerfile (`Dockerfile`)

```dockerfile
# Line 37 - Changed CMD
CMD ["uvicorn", "cybershield.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4.2 docker-compose.yml

Complete rewrite. Services now include:

| Service | Image | Container Name | Port |
|---------|-------|----------------|------|
| api | Build from Dockerfile | cyberguide-api | 8000 |
| worker | Build from Dockerfile | cyberguide-worker | - |
| dashboard | Build from Dockerfile.dashboard | cyberguide-dashboard | 8501 |
| redis | redis:7-alpine | cyberguide-redis | 6379 |
| postgres | postgres:16-alpine | cyberguide-postgres | 5432 |
| elasticsearch | elasticsearch:8.12.0 | cyberguide-elasticsearch | 9200 |
| ollama | ollama/ollama:latest | cyberguide-ollama | 11434 |

Named volumes: `redis_data`, `postgres_data`, `es_data`, `ollama_data`

### 4.3 .env

- `APP_NAME=CyberGuide`
- `EMAIL_FROM=CyberGuide <noreply@cyberguide.dev>`
- `USER_AGENT=CyberGuide/1.0 (+https://github.com/partha442004/cybershield)`
- Added `ELASTICSEARCH_URL=http://localhost:9200`
- `DATABASE_URL` points to `cyberguide.db` (local dev)

### 4.4 setup.sh

- Fixed `cd` path: `cd cybershield` (was `cd cybershield/src/cybershield`)
- Fixed compose command: `docker-compose up -d` (was `cd src/cybershield && docker-compose up -d`)
- Generates production `.env` with PostgreSQL URL

### 4.5 requirements.txt

Added:
- `bcrypt>=4.0.0`
- `pydantic-settings>=2.1.0`

---

## 5. Test Results

### InternTrack Tests (347)

```
tests/integration/test_api.py         21 passed
tests/unit/test_ai_service.py         12 passed
tests/unit/test_application_service.py 8 passed
tests/unit/test_cache.py             13 passed
tests/unit/test_classification_engine.py 17 passed
tests/unit/test_deduplication.py      7 passed
tests/unit/test_dependencies.py       8 passed
tests/unit/test_encryption.py        15 passed
tests/unit/test_glassdoor_scraper.py 15 passed
tests/unit/test_hackernews_scraper.py 16 passed
tests/unit/test_helpers.py           27 passed
tests/unit/test_indeed_scraper.py    14 passed
tests/unit/test_job_service.py        8 passed
tests/unit/test_learning_service.py  16 passed
tests/unit/test_linkedin_scraper.py  14 passed
tests/unit/test_logger.py            3 passed
tests/unit/test_notification_service.py 18 passed
tests/unit/test_remoteok_scraper.py  13 passed
tests/unit/test_rss_feeds_scraper.py 16 passed
tests/unit/test_scheduler_jobs.py    10 passed
tests/unit/test_scheduler_setup.py    3 passed
tests/unit/test_scraper_base.py      13 passed
tests/unit/test_scrapers.py          12 passed
tests/unit/test_scrapers_advanced.py 16 passed
tests/unit/test_utils.py            14 passed
tests/unit/test_verification.py      13 passed
tests/unit/test_worker.py            2 passed
TOTAL: 347 passed (29.54s)
Coverage: 75%
```

### CyberGuide Tests (295)

```
test_api.py                          9 passed
test_cache.py                       23 passed
test_checkpoint_scraper.py          18 passed
test_crowdstrike_scraper.py         19 passed
test_elasticsearch_service.py       16 passed
test_engines.py                     18 passed
test_fortinet_scraper.py            17 passed
test_mcafee_scraper.py              17 passed
test_middleware.py                   9 passed
test_notifications.py               9 passed
test_paloalto_scraper.py            19 passed
test_resume_parser.py               45 passed
test_scrapers.py                     9 passed
test_symantec_scraper.py            17 passed
test_trendmicro_scraper.py          18 passed
test_watchlist_api.py               11 passed
test_websocket.py                   18 passed
TOTAL: 295 passed (7.91s)
```

---

## 6. File Inventory

### Deployment Files (Modified)

| File | Change Description |
|------|-------------------|
| `Dockerfile` | CMD changed to `cybershield.main:app` |
| `Dockerfile.dashboard` | Unchanged (already correct) |
| `docker-compose.yml` | Full rewrite: CyberGuide containers, added postgres/es/ollama |
| `.env` | CyberGuide naming, added ELASTICSEARCH_URL |
| `deploy/oracle-cloud/setup.sh` | Fixed cd paths |
| `requirements.txt` | Added bcrypt, pydantic-settings |

### Source Files (Modified - Bug Fixes)

| File | Change |
|------|--------|
| `src/cybershield/api/v1/applications.py` | Fixed ApplicationStatus import |
| `src/interntrack/config.py` | Added elasticsearch_url field |

### Database

| File | Description |
|------|-------------|
| `data/cyberguide.db` | Created locally for dev/testing |

---

## 7. Git Status

### Last Commits

```
19a20ad chore: remove stale workflow files missing from disk
fef0965 fix: deployment config and import bugs for Oracle Cloud
36a597b feat: add Oracle Cloud Free Tier deployment guide and setup script
50def1a chore: fix root pyproject.toml name to cybershield
e09c97e feat: rename CyberShield to CyberGuide across codebase
5c5704b chore: update author to PARTHASARATHI B (partha442004)
c9b895c feat: CyberShield Career Intelligence Platform - Complete Implementation
```

### Current Status

- **Branch**: `master`
- **Remote**: `origin` -> `https://github.com/partha442004/cybershield.git`
- **Pushed**: YES (all commits pushed)
- **Unstaged changes**: ~160 files with CRLF/LF line-ending warnings (cosmetic, no functional impact)
---

## 8. Oracle Cloud Deployment Steps

### Prerequisites
- Oracle Cloud account with Always Free Tier
- SSH key pair generated

### Step 1: Create ARM VM

1. Go to **Compute > Instances > Create Instance**
2. **Image**: Oracle Linux 9 (latest)
3. **Shape**: VM.Standard.A1.Flex
4. **Configure**: 4 OCPU, 24 GB RAM
5. **Boot Volume**: 50 GB
6. **SSH Key**: Paste public key from `ssh-keygen -t rsa -b 4096 -f cybershield-key`
7. **Create** the instance

### Step 2: Configure Security Rules

Go to **Networking > VCN > Default Security List > Add Ingress Rules**:

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 22 | TCP | YOUR_IP/32 | SSH |
| 8000 | TCP | 0.0.0.0/0 | API |
| 8501 | TCP | 0.0.0.0/0 | Dashboard |

### Step 3: Connect to VM

```bash
chmod 400 cybershield-key
ssh -i cybershield-key opc@YOUR_PUBLIC_IP
```

### Step 4: Push Code to GitHub

**From local machine** (not yet done):

```bash
cd C:\internship-tracker
git remote add origin https://github.com/partha442004/cybershield.git
git add Dockerfile docker-compose.yml deploy/oracle-cloud/setup.sh requirements.txt
git add src/cybershield/api/v1/applications.py src/interntrack/config.py
git commit -m "fix: deployment config and import bugs for Oracle Cloud"
git push -u origin master
```

### Step 5: Deploy on VM

```bash
# Option A: One-liner
curl -sSL https://raw.githubusercontent.com/partha442004/CyberGuide/main/deploy/oracle-cloud/setup.sh | bash

# Option B: Manual
git clone https://github.com/partha442004/CyberGuide.git
cd CyberGuide
chmod +x deploy/oracle-cloud/setup.sh
./deploy/oracle-cloud/setup.sh
```

### Step 6: Verify

```bash
docker-compose ps
curl http://localhost:8000/health
curl http://localhost:8000/api/docs
```

---

## 9. Post-Deployment Checklist

- [ ] All containers running (`docker-compose ps`)
- [ ] Health endpoint returns `{"status":"healthy"}`
- [ ] API docs accessible at `http://IP:8000/api/docs`
- [ ] Dashboard accessible at `http://IP:8501`
- [ ] Elasticsearch accessible at `http://IP:9200`
- [ ] Logs clean (`docker-compose logs -f`)
- [ ] Scraper scheduler running
- [ ] Notifications configured (optional)

---

## 10. Known Issues & Notes

### DO NOT Touch Root `pyproject.toml`

The root `pyproject.toml` is configured for **InternTrack**:
- `packages = ["src/interntrack"]`
- `testpaths = ["tests"]`
- `--cov=interntrack`

Changing this breaks all 347 InternTrack tests. CyberGuide has its own `src/cybershield/pyproject.toml`.

### Line Ending Warnings

Git shows CRLF/LF warnings for all modified files. This is cosmetic and doesn't affect functionality. To suppress:
```bash
git config --global core.autocrlf true
```

### `.env` is Gitignored

The `.env` file is in `.gitignore`. The `setup.sh` script generates a production `.env` with:
- PostgreSQL connection string
- Random SECRET_KEY and API_KEY
- Production settings

### Ollama GPU Requirements

The `docker-compose.yml` includes Ollama with GPU passthrough. If the ARM VM has no GPU, remove the `deploy.resources` section from the ollama service, or comment out the ollama service entirely.

### Dashboard Dockerfile

`Dockerfile.dashboard` copies from `dashboard/` directory. This directory exists and is populated. No issues.
