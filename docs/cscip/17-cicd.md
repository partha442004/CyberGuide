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
> lint + format check, mypy across both modules, the combined InternTrack +
> CyberGuide test suite (782 tests) with coverage collection and an uploaded
> `coverage.xml` artifact, plus a security gate (bandit static scan + safety
> dependency scan + Trivy filesystem scan scoped to `src/`). Docker build
> remains a CD concern; the CI pipeline is focused on lint/type/tests/coverage/security.

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
        run: ruff check src/ tests/ dashboard/
      - name: Ruff format check
        run: ruff format --check src/ tests/ dashboard/

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

  version:
    name: Version consistency
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python scripts/check_versions.py

  test:
    name: Tests (pytest)
    runs-on: ubuntu-latest
    needs: [lint, typecheck, version, security]

  smoke:
    name: Smoke (live API boot)
    runs-on: ubuntu-latest
    needs: [lint, typecheck, security, version, test]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -r requirements-dev.txt
      - run: python scripts/smoke_test.py
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
          pytest tests src/cybershield/tests -q -p no:cacheprovider -o addopts='' \
            --cov=interntrack --cov=cybershield \
            --cov-report=term-missing --cov-report=xml:coverage.xml

      - name: Upload coverage report
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage.xml

  security:
    name: Security (bandit + safety + trivy)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install security tools
        # safety pinned to <3 (v3 replaced `check` with `scan`) to match
        # requirements-dev.txt and keep the gate deterministic
        run: python -m pip install bandit "safety>=2.3.0,<3"
      - name: Bandit scan (medium+ severities)
        run: bandit -r src/ scripts/ dashboard/ -ll -q
      - name: Safety dependency scan
        run: safety check -r requirements.txt -r requirements-dev.txt --full-report
      - name: Trivy filesystem scan (HIGH/CRITICAL)
        uses: aquasecurity/trivy-action@0.30.0
        with:
          scan-type: fs
          scan-ref: src/
          skip-dirs: tests,dashboard,data,migrations
          severity: HIGH,CRITICAL
          exit-code: '1'
          format: table
```

> The `test` job depends on `lint`, `typecheck`, and `security` — a medium+ or
> high-severity bandit finding, any known-vulnerable dependency flagged by
> safety, or a HIGH/CRITICAL Trivy finding blocks the test run.

### CD Workflow

> ✅ **Implemented** in `.github/workflows/cd.yml` (2026-08-01). Tag-based
> releases (`v*`) build and push the Docker image, then SSH-deploy and run
> migrations. Requires `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`,
> `SERVER_HOST`, `SERVER_USER`, and `SSH_PRIVATE_KEY` secrets to actually run.

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

> ✅ **Implemented** in `.pre-commit-config.yaml` (2026-08-01): ruff `--fix` +
> `ruff-format`, mypy (`PYTHONPATH=src`, both modules), and commitizen. Install
> with `pip install pre-commit && pre-commit install`; run all with
> `pre-commit run --all-files`.

```yaml
# .pre-commit-config.yaml

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.7
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.15.0
    hooks:
      - id: mypy
        entry: mypy
        args: [src/interntrack, src/cybershield]
        pass_filenames: false
        env:
          PYTHONPATH: src
        additional_dependencies:
          - pydantic>=2.5.0
          - sqlalchemy>=2.0.23
          - types-requests

  - repo: https://github.com/commitizen-tools/commitizen
    rev: v3.31.0
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
| Security (static) | bandit | 0 medium/high |
| Security (deps) | safety | 0 known vulnerabilities |
| Security (container) | trivy | 0 HIGH/CRITICAL (fs scan of src/) |
| Build | docker build | Success (CD, tag-based) |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 18: Testing](./18-testing.md)
