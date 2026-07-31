# 🛡️ CyberShield Career Intelligence Platform

**AI-powered Cybersecurity Career Intelligence Platform**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 Overview

CyberShield is a comprehensive AI-powered platform that continuously discovers, verifies, analyzes, and notifies users about cybersecurity career opportunities. Never manually search for internships or jobs again!

### Features

- 🔍 **Discovery Engine** - 40+ sources including LinkedIn, Indeed, Naukri, GitHub, and company career pages
- 🛡️ **Scam Detection** - AI-powered scam scoring with confidence levels
- 🔄 **Deduplication** - Smart duplicate detection using URL, title, and semantic similarity
- ✅ **Verification** - Real-time link validation and deadline tracking
- 🏷️ **Classification** - Automatic job categorization and skill extraction
- 🔔 **Notifications** - Telegram, Email, Discord, Slack channels
- 📊 **Dashboard** - Interactive Streamlit dashboard with 13 pages
- 📈 **Analytics** - Skill trends, salary insights, hiring predictions

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- pip or poetry

### Installation

```bash
# Clone the repository
git clone https://github.com/partha442004/CyberGuide.git
cd CyberGuide

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your settings
```

### Running the Application

```bash
# Start API server
uvicorn cybershield.main:app --reload

# Start Dashboard (in another terminal)
streamlit run cybershield/dashboard/app.py

# Start Scheduler (in another terminal)
python -m cybershield.scheduler
```

### Docker Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## 📁 Project Structure

```
cybershield/
├── src/cybershield/
│   ├── api/              # FastAPI routers
│   ├── database/         # Database session & config
│   ├── domain/           # Models, enums, exceptions
│   ├── engines/          # AI engines (dedup, verify, scam, classify)
│   ├── notifications/    # Telegram, Email, Discord, Slack
│   ├── repositories/     # Data access layer
│   ├── scrapers/         # Job scrapers by region
│   │   ├── india/        # Naukri, Internshala, Unstop, Freshersworld
│   │   ├── usa/          # LinkedIn, Indeed
│   │   ├── global/       # RemoteOK, HackerNews, RSS
│   │   └── companies/    # Microsoft, Google, Amazon, Cisco
│   ├── schemas/          # Pydantic models
│   ├── dashboard/        # Streamlit dashboard
│   ├── scheduler/        # Background job scheduler
│   ├── alembic/          # Database migrations
│   ├── config.py         # Configuration
│   ├── main.py           # FastAPI entry point
│   └── dependencies.py   # Dependency injection
├── tests/                # Test suite
├── docs/                 # Documentation
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=sqlite:///./data/cybershield.db

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# Notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
DISCORD_WEBHOOK_URL=your_webhook_url
SLACK_WEBHOOK_URL=your_webhook_url
```

---

## 📚 API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/jobs/` | List jobs with filters |
| GET | `/api/v1/jobs/search` | Search jobs |
| GET | `/api/v1/jobs/{id}` | Get job details |
| POST | `/api/v1/applications/` | Create application |
| PATCH | `/api/v1/applications/{id}/status` | Update status |
| GET | `/api/v1/analytics/skills/trending` | Trending skills |

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=cybershield

# Run specific test file
pytest tests/test_engines.py -v
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with FastAPI, SQLAlchemy, Streamlit
- Scraping powered by httpx, BeautifulSoup, feedparser
- AI capabilities via sentence-transformers, scikit-learn
