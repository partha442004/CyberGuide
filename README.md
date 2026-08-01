# 🎯 InternTrack

> AI-powered internship and job tracking platform with automated discovery, application management, and skill-based learning recommendations.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![CI](https://github.com/partha442004/CyberGuide/actions/workflows/ci.yml/badge.svg)
![Tests](https://img.shields.io/badge/tests-817%20passed-brightgreen.svg)
![Coverage](https://img.shields.io/badge/coverage-67%25-yellow.svg)
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

### Applications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/applications/` | List applications |
| POST | `/api/v1/applications/` | Create application |
| PATCH | `/api/v1/applications/{id}/status` | Update status |
| GET | `/api/v1/applications/metrics/overview` | Get metrics |

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

Start the Streamlit dashboard:

```bash
streamlit run dashboard/app.py
```

Open http://localhost:8501 in your browser.

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
