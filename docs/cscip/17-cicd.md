# CyberShield Career Intelligence Platform (CSCIP) - CI/CD

## Overview

CSCIP uses GitHub Actions for continuous integration and deployment with automated testing, linting, and deployment pipelines.

---

## CI/CD Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CI/CD ARCHITECTURE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    CI Pipeline (Push/PR)                             │   │
│  │                                                                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │  Lint    │──▶│  Test    │──▶│  Type    │──▶│  Build   │          │   │
│  │  │ (ruff)   │  │ (pytest) │  │ (mypy)   │  │ (Docker) │          │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    CD Pipeline (Main Branch)                         │   │
│  │                                                                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │  Build   │──▶│  Push    │──▶│  Deploy  │──▶│  Notify  │          │   │
│  │  │  Image   │  │  Registry│  │  Server  │  │  Team    │          │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## GitHub Actions Workflows

### CI Workflow

> ✅ **Implemented** in `.github/workflows/ci.yml` (2026-08-01). It runs ruff
> lint + format check, mypy across both modules, and the combined InternTrack +
> CyberGuide test suite (679 tests). Docker build + Trivy scan are future
> enhancements; the current pipeline is focused on lint/type/tests.

```yaml
# .github/workflows/ci.yml

name: CI

on:
  push:
    branches: [main, master, develop]
  pull_request:
    branches: [main, master]

jobs:
  lint:
    name: Lint (ruff)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -r requirements-dev.txt
      - name: Ruff check
        run: ruff check src/ tests/
      - name: Ruff format check
        run: ruff format --check src/ tests/

  typecheck:
    name: Typecheck (mypy)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -r requirements-dev.txt
      - name: Mypy (interntrack + cybershield)
        run: |
          export PYTHONPATH=src
          mypy src/interntrack src/cybershield

  test:
    name: Tests (pytest)
    runs-on: ubuntu-latest
    needs: [lint, typecheck]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -r requirements-dev.txt
      - name: Run full test suite (InternTrack + CyberGuide)
        env:
          PYTHONPATH: src
        run: |
          pytest tests src/cybershield/tests -q -p no:cacheprovider -o addopts=''
```

### CD Workflow

> ⏳ **Planned / future enhancement.** Not yet implemented — shown here as the
> target pipeline for tag-based releases. Requires Docker Hub credentials and a
> deploy target with SSH access.

```yaml
# .github/workflows/cd.yml

name: CD

on:
  push:
    branches: [main]
    tags: ['v*']

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: cybershield/cybershield
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    runs-on: ubuntu-latest
    needs: build-and-push
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - name: Deploy to server
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/cybershield
            docker-compose pull
            docker-compose up -d
            docker-compose exec api alembic upgrade head
```

---

## Pre-commit Configuration

```yaml
# .pre-commit-config.yaml

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
  
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v3.13.0
    hooks:
      - id: commitizen
```

---

## Quality Gates

| Gate | Tool | Threshold |
|------|------|-----------|
| Linting | ruff | 0 errors |
| Formatting | ruff format | All files formatted |
| Type checking | mypy | 0 errors |
| Tests | pytest | 100% pass |
| Coverage | pytest-cov | ≥80% |
| Security | trivy | 0 critical/high |
| Build | docker build | Success |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 18: Testing](./18-testing.md)
