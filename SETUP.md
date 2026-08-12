# 🚀 InternTrack - Complete Setup Guide

> Follow these steps to get InternTrack running on your machine.

---

## 📋 Prerequisites

Before you begin, ensure you have:

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| **Python** | 3.11+ | `python --version` |
| **pip** | Latest | `pip --version` |
| **Git** | Latest | `git --version` |
| **Node.js** | Optional (for frontend) | `node --version` |

---

## 🎯 Quick Start (5 Minutes)

### Step 1: Clone & Enter Project
```bash
# Clone the repository
git clone https://github.com/partha442004/CyberGuide.git

# Enter project directory
cd CyberGuide
```

### Step 2: Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies (optional)
pip install -r requirements-dev.txt
```

### Step 4: Configure Environment
```bash
# Copy environment template
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env
```

### Step 5: Create Data Directory
```bash
# Windows
mkdir data

# macOS/Linux
mkdir -p data
```

### Step 6: Start the Application
```bash
# Start API server
uvicorn interntrack.main:app --reload

# Open browser
# http://localhost:8000/docs
```

---

## 📖 Detailed Setup Instructions

### Option A: Manual Setup (Recommended for Development)

#### 1.1 Clone Repository
```bash
git clone https://github.com/partha442004/CyberGuide.git
cd CyberGuide
```

#### 1.2 Create Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (Command Prompt)
venv\Scripts\activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate

# Verify activation
python --version  # Should show Python 3.11+
```

#### 1.3 Install Dependencies
```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Install production dependencies
pip install -r requirements.txt

# Install development dependencies (for testing/linting)
pip install -r requirements-dev.txt
```

#### 1.4 Configure Environment Variables
```bash
# Copy the example environment file
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env
```

**Edit `.env` file with your settings:**
```env
# Database (SQLite for development)
DATABASE_URL=sqlite+aiosqlite:///./data/interntrack.db

# Security (change this in production!)
SECRET_KEY=your-secret-key-here

# Optional: AI Services
# OLLAMA_BASE_URL=http://localhost:11434
# GEMINI_API_KEY=your-gemini-api-key

# Optional: Notifications
# TELEGRAM_BOT_TOKEN=your-telegram-bot-token
# TELEGRAM_CHAT_ID=your-telegram-chat-id
# DISCORD_WEBHOOK_URL=your-discord-webhook-url
```

#### 1.5 Initialize Database
```bash
# Create data directory
mkdir data

# Run database migrations (if using Alembic)
alembic upgrade head
```

#### 1.6 Start the Application
```bash
# Start the API server with auto-reload
uvicorn interntrack.main:app --reload --host 0.0.0.0 --port 8000

# The server will start at: http://localhost:8000
# API docs available at: http://localhost:8000/docs
```

#### 1.7 Start the Dashboard (Optional)
```bash
# In a new terminal
streamlit run dashboard/app.py

# Dashboard will start at: http://localhost:8501
```

---

### Option B: Automated Setup (Quick)

#### For macOS/Linux:
```bash
# Make setup script executable
chmod +x setup.sh

# Run setup script
./setup.sh
```

#### For Windows (PowerShell):
```powershell
# Run setup script
.\setup.ps1
```

---

### Option C: Docker Setup (Recommended for Production)

#### 2.1 Install Docker
- Download Docker Desktop: https://www.docker.com/products/docker-desktop

#### 2.2 Build and Start Services
```bash
# Build Docker images
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

#### 2.3 Access the Application
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Dashboard**: http://localhost:8501

#### 2.4 Stop Services
```bash
docker-compose down
```

---

## 🔧 Development Setup

### Setting Up for Development

```bash
# Clone and enter project
git clone https://github.com/partha442004/CyberGuide.git
cd CyberGuide

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install all dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks (optional)
pre-commit install

# Start development server
uvicorn interntrack.main:app --reload
```

### IDE Configuration

#### VS Code
1. Install Python extension
2. Select Python interpreter: `./venv/bin/python`
3. Install recommended extensions

#### PyCharm
1. Open project folder
2. Set Python interpreter to `venv/bin/python`
3. Mark `src` as Sources Root

---

## 🧪 Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=interntrack --cov-report=html

# Run unit tests only
pytest tests/unit

# Run integration tests only
pytest tests/integration

# View coverage report
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
```

---

## 📊 Running the Dashboard

```bash
# Start Streamlit dashboard
streamlit run dashboard/app.py

# Open browser to http://localhost:8501
```

---

## 🐳 Docker Commands

```bash
# Build images
docker-compose build

# Start services (detached)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up -d --build

# View running containers
docker-compose ps
```

---

## 🔍 Verifying Installation

### Test API Health
```bash
# Using curl
curl http://localhost:8000/health

# Expected response
{"status": "healthy"}
```

### Test API Endpoints
```bash
# List jobs
curl http://localhost:8000/api/v1/jobs/

# Create a job
curl -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Python Developer",
    "company": "TechCorp",
    "url": "https://example.com/job/1"
  }'
```

### Run Job Discovery
```bash
# Trigger job discovery from HackerNews
curl -X POST "http://localhost:8000/api/v1/jobs/discovery/run?query=python%20developer"
```

---

## 🛠️ Common Commands Reference

```bash
# Development
make run              # Start API server
make worker           # Start background worker
make dashboard        # Start Streamlit dashboard

# Code Quality
make lint             # Run linter
make format           # Format code
make typecheck        # Run type checker

# Testing
make test             # Run all tests
make test-unit        # Run unit tests
make test-cov         # Generate coverage report

# Database
make db-migrate       # Run migrations
make db-reset         # Reset database

# Docker
make docker-build     # Build images
make docker-up        # Start services
make docker-down      # Stop services
```

---

## ⚠️ Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'interntrack'"
**Solution:**
```bash
# Ensure you're in the project directory
cd CyberGuide

# Ensure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate

# Reinstall in development mode
pip install -e .
```

### Issue: "Database connection error"
**Solution:**
```bash
# Create data directory
mkdir data

# Ensure DATABASE_URL in .env is correct
# For SQLite: sqlite+aiosqlite:///./data/interntrack.db
```

### Issue: "Port already in use"
**Solution:**
```bash
# Find process using port 8000
# Windows
netstat -ano | findstr :8000

# macOS/Linux
lsof -i :8000

# Kill the process or use different port
uvicorn interntrack.main:app --port 8001
```

### Issue: "Permission denied on setup.sh"
**Solution:**
```bash
chmod +x setup.sh
./setup.sh
```

---

## 📚 Next Steps After Setup

1. **Explore API Docs**: Open http://localhost:8000/docs
2. **Run Job Discovery**: Use the API to discover jobs
3. **Check Dashboard**: Open http://localhost:8501
4. **Read Documentation**: Check the `docs/` folder
5. **Configure Notifications**: Set up Telegram/Discord in `.env`

---

## 📨 Email Deliverability (why alerts land in Spam)

Emails are sent through the provider configured in `.env`. A common
cause of alerts landing in the **Spam** folder is the From address:
the historical default `EMAIL_FROM="InternTrack <noreply@interntrack.local>"`
uses a non-routable `.local` domain, which can never pass SPF/DKIM
authentication. Since v1.22 the code never sends From such an address —
it automatically falls back to the authenticated SMTP account — and adds
deliverability headers (`Date`, `Message-ID`, `List-Unsubscribe`, and a
plain-text alternative) to every message.

### Recommended: Resend (best deliverability)
```env
RESEND_API_KEY=re_xxxxxxxx
# Optional: a verified sending domain; falls back to EMAIL_FROM
# RESEND_FROM=Alerts <alerts@yourdomain.com>
```
Resend authenticates mail automatically (SPF/DKIM/DMARC), works from
serverless, and is used automatically whenever `RESEND_API_KEY` is set.

### SMTP (Gmail or any relay)
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=app-password
# Optional: a real, routable domain you own (best results).
# EMAIL_FROM=Alerts <alerts@yourdomain.com>
```
For Gmail use an [app password](https://myaccount.google.com/apppasswords)
and set `EMAIL_FROM` to your own Gmail address (or any domain with valid
SPF/DKIM records). If alerts still land in Spam:

1. Open one InternTrack email in Gmail and choose **Report not spam**.
2. Add the From address to your contacts.
3. For a custom domain, publish SPF (`v=spf1 include:... ~all`), DKIM and
   DMARC records for it.

The dashboard **Settings → Email deliverability** panel shows the live
provider, the effective From address and these tips.

---

## 🆘 Getting Help

- **Documentation**: Check `docs/` folder
- **Issues**: Open GitHub issue
- **Discord**: Join our Discord server
- **Email**: parthasarathi442004@gmail.com

---

**Last Updated:** 2026-08-01
**Version:** 1.2.0
