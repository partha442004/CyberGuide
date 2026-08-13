# 🎯 InternTrack

> AI-powered internship and job tracking platform with automated discovery, application management, and skill-based learning recommendations.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![CI](https://github.com/partha442004/CyberGuide/actions/workflows/ci.yml/badge.svg)
![Tests](https://img.shields.io/badge/tests-2051%20passed-brightgreen.svg)
![Coverage](https://img.shields.io/badge/coverage-99%25-green.svg)
![Security](https://img.shields.io/badge/security-bandit%20%2B%20safety%20%2B%20trivy%20clean-brightgreen.svg)

---

## ✨ Features

- 🔍 **Automated Job Discovery** - Scrape jobs from HackerNews, RemoteOK, RSS feeds
- 📋 **Application Tracking** - Kanban-style pipeline (Saved → Applied → Interview → Offer)
- 📊 **Analytics Dashboard** - Real-time charts, trends, and insights
- 🔔 **Multi-channel Notifications** - Telegram, Email, Discord, Slack
- 🤖 **AI Classification** - Smart job categorization with Ollama/Gemini
- 📚 **Learning Resources** - Skill gap analysis with curated resources
- 🌙 **Dark/Light Mode** - Modern responsive dashboard

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- pip
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/partha442004/CyberGuide.git
cd CyberGuide

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy .env.example .env  # Windows
cp .env.example .env    # macOS/Linux

# Create data directory
mkdir data

# Start the API server
uvicorn interntrack.main:app --reload
```

### Verify Installation

```bash
# Open API docs in browser
# http://localhost:8000/docs

# Test health endpoint
curl http://localhost:8000/health
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/01-software-architecture.md) | System design and patterns |
| [Folder Structure](docs/02-folder-structure.md) | Project organization |
| [Security Guide](docs/SECURITY-AND-METHODOLOGIES.md) | Security best practices |
| [TODO Checklist](TODO-CHECKLIST.md) | Complete development checklist |

---

## 🏗️ Project Structure

```
internship-tracker/
├── src/interntrack/          # Main application
│   ├── api/                  # FastAPI endpoints
│   ├── domain/               # Business models
│   ├── services/             # Business logic
│   ├── scrapers/             # Job scrapers
│   ├── engines/              # Core engines
│   └── utils/                # Utilities
├── dashboard/                # Streamlit dashboard
├── tests/                    # Test suite
├── docs/                     # Documentation
└── docker-compose.yml        # Docker setup
```

---

## 🔧 Configuration

### Environment Variables

```env
# Database
DATABASE_URL=sqlite+aiosqlite:///./data/interntrack.db

# AI (Optional)
OLLAMA_BASE_URL=http://localhost:11434
GEMINI_API_KEY=your-key

# Notifications (Optional)
TELEGRAM_BOT_TOKEN=
DISCORD_WEBHOOK_URL=
SMTP_USER=
SMTP_PASSWORD=

# Scraper
SCRAPE_INTERVAL_MINUTES=30
```

---

## 👥 Multi-User Accounts

Anyone can create a free account — each user gets **their own personalized
job alerts and resume matching**:

| What | How it works |
|---|---|
| **Sign up** | Dashboard → *My Account* → create account with name + email (+ optional location, experience level, Telegram chat ID, categories, skills, resume). Alerts are **auto-enabled** at signup with your chosen categories. |
| **Login** | By email only (no password) — the profile is looked up by email; when an account has an **access token** it must be supplied to log in (returned at registration and via `/rotate-token`). Each user's tracking data (applications, watchlist, overview) is scoped by their own `user_id`. |
| **Personalized alerts** | The daily digest (08:00 / 13:00 / 19:00 IST) and Sunday weekly recap are built **per user**: their categories, their `min_match_score`, their own no-duplicates window, and their own send history. |
| **Resume match %** | Match scores are computed from **your own** uploaded resume (stored per `user_id`), not a shared one. |
| **Delivery** | Emails go to **your** email address (the app's SMTP account is only the sender) and Telegram messages go to **your** chat ID when you provide one. Users without a chat ID simply don't get Telegram — nothing leaks to other users' chats. |

### Users API

```
POST   /api/v1/users/register         # name + email + optional profile fields → account + auto-enabled alerts + access token
POST   /api/v1/users/login            # { email } → profile + access token
POST   /api/v1/users/{id}/rotate-token  # invalidate the old token, get a new one
GET    /api/v1/users                  # list profiles
GET    /api/v1/users/{id}             # one profile
PUT    /api/v1/users/{id}             # update profile (name, location, experience, telegram_chat_id, domains, skills)
```

Personalized endpoints accept `user_id` so each user only sees/tracks their
own data: applications, the company watchlist, and `/dashboard/overview` +
charts are all scoped per user when a `user_id` is given (no `user_id` →
legacy shared view). The access token is a login credential — it is checked
at login and rotated via the API, and should be treated like a password.

Resumes continue to use the existing endpoint (keyed by `user_id`):
`POST /api/v1/resumes/upload?user_id=...` and
`POST /api/v1/resumes/match-batch?user_id=...&job_ids=...`.

---

## 🚦 API Endpoints

### Jobs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/jobs/` | List jobs |
| POST | `/api/v1/jobs/` | Create job |
| GET | `/api/v1/jobs/{id}` | Get job |
| PUT | `/api/v1/jobs/{id}` | Update job |
| DELETE | `/api/v1/jobs/{id}` | Delete job |
| POST | `/api/v1/jobs/discovery/run` | Run job discovery |
| POST | `/api/v1/jobs/discovery/run-for-users` | Per-user discovery (cron: each enabled user's categories/skills → queries) |
| POST | `/api/v1/jobs/share` | **Share a job** — paste any URL (LinkedIn post, careers page) → auto-fetches title/company and saves it |
| POST | `/api/v1/jobs/search` | Search saved jobs |
| GET | `/api/v1/jobs/stats/overview` | Job statistics |
| GET | `/api/v1/jobs/closing/soon` | Jobs closing soon |

### Applications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/applications/` | List applications (`?user_id=` scoped) |
| POST | `/api/v1/applications/` | Create application (with `user_id`) |
| GET | `/api/v1/applications/{id}` | Get application |
| PUT | `/api/v1/applications/{id}` | Update application |
| PATCH | `/api/v1/applications/{id}/status` | Update status |
| DELETE | `/api/v1/applications/{id}` | Delete application |
| GET | `/api/v1/applications/metrics/overview` | Get metrics (`?user_id=` scoped) |
| GET | `/api/v1/applications/timeline/recent` | Recent applications timeline |

### Watchlist
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/watchlists/?user_id=...` | Your watched companies |
| POST | `/api/v1/watchlists/` | Watch a company (appears in your daily digest) |
| DELETE | `/api/v1/watchlists/{id}` | Unwatch |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/reports/daily` | Daily report |
| GET | `/api/v1/reports/weekly` | Weekly report |
| GET | `/api/v1/reports/monthly` | Monthly report |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Readiness probe (200 healthy / 503 degraded) |
| GET | `/metrics` | Request metrics (counts, error rate, latency) |

---

## ☁️ Cloud Deployment (Vercel + Neon — free, no credit card)

The app runs live at **https://cyberguide-api.vercel.app** — hosted on
Vercel (serverless) with a Neon Postgres database. Both are free forever.

- `api/index.py` — Vercel serverless entrypoint (re-exports the FastAPI app)
- `vercel.json` — build/routes config for the Python runtime
- `.vercelignore` — excludes `pyproject.toml` (Vercel installs from
  `requirements.txt`) and other local files
- Env vars on Vercel: `DATABASE_URL` (Neon, asyncpg + `?ssl=require`),
  `DEBUG=false`, `RATE_LIMIT_ENABLED=false`
- **Auto-deploy**: every push to `master` redeploys automatically
- Neon free tier: PostgreSQL 18, 0.5 GB storage, scale-to-zero compute
- **Auto-refresh**: `.github/workflows/daily-refresh.yml` (free GitHub Actions
  cron) triggers `POST /api/v1/jobs/discovery/run` + `GET /api/v1/reports/daily`
  on the live API twice a day — replaces the always-on worker that can't run
  on serverless

Note: serverless cold start is ~1-3s on the first request after idle.

### 💻 PC discovery CLI (optional — unlock bot-gated sources)

Some boards (JobDexo, Foundit, Apna, Cutshort) bot-gate datacenter IPs,
so Vercel's cron can't fetch them directly. From a residential network
*your machine* they work fine. `scripts/pc_discovery.py` runs those
scrapers locally and pushes the parsed jobs straight into the live DB:

```bash
# One quick run: cybersecurity jobs near Bangalore, all 4 blocked sources
python scripts/pc_discovery.py --query "cybersecurity" --location "Bangalore"

# Every member's domains + cities in one go
python scripts/pc_discovery.py --all-members --limit 20
```

Each run prints what was found vs. what actually saved (duplicates are
skipped automatically).

**To run it automatically every day from your PC** (residential IP, so the
blocked boards work):

1. Double-click `scripts/run_pc_discovery.bat` once to confirm it works
   (it auto-installs deps and logs to `%USERPROFILE%\pc_discovery.log`).
2. Open **Task Scheduler** → **Create Basic Task**:
   - Trigger: **Daily** at a time your PC is usually on (e.g. 09:00)
   - Action: **Start a program** → browse to
     `scripts/run_pc_discovery.bat` (start in: the repo folder)
   - Check **Run whether user is logged on or not** for background runs

> Honest note on automation: the *main* pipeline (search-engine net over
> DuckDuckGo/Bing/Brave, Internshala, RSS and the other unblocked
> sources) already runs automatically 3× a day from Vercel — no action
> needed. JobDexo / Foundit / Apna / Cutshort block **both** Vercel and
> GitHub-runner IPs (verified), so they can only be fetched from a
> residential network — that is exactly what this PC task does.

---

## 🐳 Docker Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=interntrack --cov-report=html

# Run unit tests only
pytest tests/unit

# Run integration tests
pytest tests/integration
```

---

## 📊 Dashboard

Start the Streamlit dashboard locally:

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

Open http://localhost:8501 in your browser. The dashboard reads `API_URL`
and `HEALTH_URL` (in order): `st.secrets` → environment variable → default.
The default points at the **live Vercel deployment**, so the cloud dashboard
works with zero configuration. For local development against your local API,
set the env vars (or a local `.streamlit/secrets.toml`):

```bash
API_URL=http://localhost:8000/api/v1 HEALTH_URL=http://localhost:8000/health \
  streamlit run dashboard/app.py
```

### Dashboard on Streamlit Community Cloud (free, no credit card)

1. Push the repo to GitHub, then go to https://share.streamlit.io and sign in
   with GitHub
2. Click **New app** → select `partha442004/CyberGuide` → branch `master`
3. Set **Main file path** to `dashboard/app.py`
4. Click **Deploy** — the dashboard is live at `your-app.streamlit.app` and
   automatically pulls data from https://cyberguide-api.vercel.app (no
   secrets required; optionally override via the app's **Settings → Secrets**
   with `API_URL` / `HEALTH_URL`)
5. Every push to `master` redeploys the dashboard automatically

---

## 🤖 AI Integration

### Ollama (Local)

```bash
# Install Ollama
# https://ollama.ai

# Pull model
ollama pull llama3

# Start Ollama
ollama serve
```

### Gemini (Cloud)

Get API key from [Google AI Studio](https://ai.google.dev/) and set in `.env`:

```env
GEMINI_API_KEY=your-api-key
```

---

## 📝 Development

### Code Quality

```bash
# Lint
make lint

# Format
make format

# Type check
make typecheck

# Run all checks
make dev
```

### Adding a New Scraper

1. Create file in `src/interntrack/scrapers/`
2. Inherit from `BaseScraper`
3. Implement `fetch()` method
4. Register in `registry.py`

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Streamlit](https://streamlit.io/)
- [Ollama](https://ollama.ai/)

---

## 📧 Contact

**PARTHASARATHI B** - parthasarathi442004@gmail.com

Project Link: https://github.com/partha442004/CyberGuide
