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

```yaml
# .github/workflows/ci.yml

name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install ruff mypy
      
      - name: Run Ruff linter
        run: ruff check src/ tests/
      
      - name: Run Ruff formatter check
        run: ruff format --check src/ tests/

  test:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      
      - name: Run tests
        run: pytest tests/ -v --cov=cybershield --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  typecheck:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install mypy types-requests
      
      - name: Run mypy
        run: mypy src/cybershield --ignore-missing-imports

  build:
    runs-on: ubuntu-latest
    needs: [test, typecheck]
    steps:
      - uses: actions/checkout@v4
      
      - name: Build Docker image
        run: docker build -t cybershield:test .
      
      - name: Run security scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'cybershield:test'
          format: 'table'
          exit-code: '1'
          severity: 'CRITICAL,HIGH'
```

### CD Workflow

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
