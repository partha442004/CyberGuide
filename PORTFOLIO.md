# 🎯 InternTrack — Professional Portfolio Package

> Everything you need to present this project on your **resume**, **LinkedIn**, and **portfolio website**.
> All facts below are verified against the live system (August 2026).

---

## 1. Project Snapshot

| Item | Value |
|---|---|
| **Project name** | InternTrack — AI-Powered Job & Internship Discovery Platform |
| **GitHub** | [github.com/partha442004/CyberGuide](https://github.com/partha442004/CyberGuide) |
| **Live API** | [cyberguide-api.vercel.app](https://cyberguide-api.vercel.app) |
| **Live dashboard** | [cyberguide2026aug.streamlit.app](https://cyberguide2026aug.streamlit.app) |
| **Status** | 🟢 Live · healthy · v1.21.0 |
| **Tests** | 2,612 tests (unit + integration + API), ~99% coverage |
| **CI/CD** | GitHub Actions — lint (ruff), type-check (mypy), tests, security (bandit + safety + trivy) |
| **Deployment** | Vercel (API) + Streamlit Cloud (dashboard) + GitHub cron scheduler |

---

## 2. One-Liner (for resume summary / LinkedIn headline)

> **InternTrack** — a full-stack AI job-discovery platform that scrapes 9+ sources (LinkedIn, Indeed, Naukri-style boards, Internshala, Wellfound, RSS), classifies roles with an ML keyword engine, and delivers **personalized daily job alerts** (email/Telegram/SMS) filtered by each user's domain and city — deployed and serving real users.

---

## 3. Resume Bullet Points (pick 4–5, quantifiable)

**InternTrack — AI Job Discovery & Notification Platform** *(Personal Project, 2026)*

- Built a **full-stack job discovery platform** (FastAPI + Streamlit + PostgreSQL) that aggregates **9+ job sources** — LinkedIn, Indeed, Internshala, Wellfound, Naukri-style boards, RSS feeds — into one searchable database of **600+ live cybersecurity jobs**.
- Engineered an **AI classification engine** (keyword + scoring heuristics with Ollama/Gemini fallback) that auto-categorizes jobs into domains (Cybersecurity, Frontend, Backend, Data…) with **per-domain + per-city filtering** for personalized alerts.
- Designed a **multi-user notification system** delivering **3× daily personalized digests** via **email (SMTP), Telegram bot, and SMS (Twilio)** — each user gets only jobs matching their role + location (e.g., "Cybersecurity × Bengaluru", "Frontend × Chennai") with **dedup, history tracking, and vacation pause**.
- Implemented **closing-soon alerts** (jobs expiring within 48h, per-user, no duplicate nagging), **salary estimate chips** from role×city benchmarks, and a **Digest Archive** page reviewing every past alert.
- Added **resume parsing + job match scoring** (ATS-style % match with skill extraction) so users see their fit for each role.
- Maintained **2,612 automated tests** (~99% coverage) with ruff linting, mypy type-checking, and bandit/safety/trivy security scans all **green in CI**.
- Deployed on **Vercel + Streamlit Cloud with GitHub Actions cron scheduling**; monitored via Prometheus/Grafana/Loki (when self-hosted) and a live scraper-health endpoint (66.7% source health, self-healing).

---

## 4. LinkedIn / Portfolio Description (professional paragraph)

**InternTrack — AI-Powered Job & Internship Discovery Platform**

InternTrack is a production-grade, multi-user platform I designed and built end-to-end that solves a real problem: job seekers drowning in irrelevant postings. It continuously discovers jobs and internships from 9+ sources — including LinkedIn, Indeed, Internshala, Wellfound, and RSS feeds — then uses a custom classification engine to tag each role by domain (Cybersecurity, Frontend, Backend, Data, etc.) and location, so every user receives a **personalized digest of only the jobs that match their profile**.

The platform delivers **3 daily digests** through email, Telegram, and SMS, with per-user deduplication, alert history, closing-soon reminders for expiring roles, and a vacation pause — all configurable from an analytics dashboard that also tracks applications, match scores, and trends. The backend is a FastAPI service with 30+ REST endpoints, a PostgreSQL database with auto-migrating schemas, and a Redis cache; the frontend is a feature-rich Streamlit dashboard with dark/light themes.

Engineering highlights: a resilient scraper layer that degrades gracefully behind bot protection, an ML-lite scoring engine for job classification and resume matching, multi-channel notification orchestration, and a full observability stack (Prometheus metrics, Grafana dashboards, Loki logs, structured logging). The project is **CI-green with 2,612 tests (~99% coverage)**, security-scanned (bandit, safety, trivy), containerized (Docker), and deployable to Kubernetes (Helm) or PaaS (Vercel/Railway/Render).

**Tech stack:** Python 3.11 · FastAPI · Streamlit · PostgreSQL · SQLAlchemy (async) · Redis · Celery/APScheduler · Telegram Bot API · Twilio · SMTP · Ollama/Gemini · Docker · Kubernetes/Helm · GitHub Actions · Prometheus · Grafana · Loki · Vercel · Streamlit Cloud

---

## 5. Key Metrics to Quote

- **9+** integrated job sources (LinkedIn, Indeed, Internshala, Wellfound, RSS, + custom India boards)
- **600+** live jobs in the database; **12+ jobs/day** auto-ingested
- **2,612** automated tests · **~99%** test coverage
- **3× daily** personalized alerts per user (email + Telegram + SMS)
- **30+** REST API endpoints under `/api/v1`
- **9** scraper sources monitored live with self-healing health checks (66.7% healthy)
- **0** credentials committed — security audit clean, secrets fully externalized to env vars

---

## 6. Screenshots to Capture (for portfolio)

1. **Overview page** — KPI cards (Total Jobs, Applications, Response Rate), "Fresh for you" section, Job of the Day, Trending jobs, Top Companies chart.
2. **Jobs page** — searchable table with domain chips, salary chips, match %, Apply links.
3. **My Account / Settings** — per-user domains, location, channels (email/Telegram/SMS), vacation pause.
4. **Digest Archive** — history of every alert sent with jobs + match % + Apply buttons.
5. **Resume Match** — ATS-style match score with skill breakdown.
6. **Telegram chat** — a real daily digest message on your phone.

---

## 7. Demo Script (60 seconds)

1. Open the dashboard → Overview shows live KPIs + "Fresh for you" cybersecurity jobs from Bengaluru.
2. Open Jobs → filter by Cybersecurity → show domain chips, salary estimate, Apply link.
3. Open Settings → show your alert profile (Cybersecurity × Bengaluru, email + Telegram on).
4. Open your Telegram/email → show today's personalized digest with match % + Apply buttons.
5. Open Digest Archive → show history of past alerts, proving consistency.
