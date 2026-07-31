# CyberShield Career Intelligence Platform (CSCIP) - Scheduler

## Overview

CSCIP uses APScheduler for task scheduling. The scheduler manages all automated background tasks including job discovery, report generation, verification, and notifications.

---

## Scheduler Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SCHEDULER ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    APScheduler (AsyncIOScheduler)                    │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                    Interval Triggers                         │   │   │
│  │  │  • Job Discovery (every 30 minutes)                         │   │   │
│  │  │  • Link Verification (every 6 hours)                        │   │   │
│  │  │  • Scam Re-analysis (every 12 hours)                        │   │   │
│  │  │  • Skill Trends Update (daily)                              │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                    Cron Triggers                             │   │   │
│  │  │  • Daily Report (6:00 AM)                                   │   │   │
│  │  │  • Weekly Report (Monday 8:00 AM)                           │   │   │
│  │  │  • Monthly Report (1st of month 9:00 AM)                    │   │   │
│  │  │  • Hiring Calendar Update (1st of month)                    │   │   │
│  │  │  • News Analysis (every 4 hours)                            │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                    Event-Driven Jobs                         │   │   │
│  │  │  • Instant Notifications (on new match)                     │   │   │
│  │  │  • Scam Alerts (on scam detection)                          │   │   │
│  │  │  • Watchlist Matches (on match found)                       │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    TASK EXECUTION                                    │   │
│  │                                                                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │  Scraper │  │  Engine  │  │ Notifier │  │ Reporter │          │   │
│  │  │  Tasks   │  │  Tasks   │  │  Tasks   │  │  Tasks   │          │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Scheduled Jobs

### 1. Job Discovery

| Property | Value |
|----------|-------|
| **Job ID** | `job_discovery` |
| **Trigger** | Interval |
| **Interval** | 30 minutes |
| **Priority** | High |
| **Timeout** | 10 minutes |

**Description:** Discovers new jobs from all configured sources.

**Execution Flow:**
```
┌─────────────────────────────────────────────────────────────────┐
│                    JOB DISCOVERY FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Get all registered scrapers                                 │
│           │                                                     │
│           ▼                                                     │
│  2. For each scraper (parallel):                                │
│     ┌─────────────────────────────────────────┐                │
│     │  a. Fetch jobs from source              │                │
│     │  b. Parse into RawJob objects           │                │
│     │  c. Return to buffer                    │                │
│     └─────────────────────────────────────────┘                │
│           │                                                     │
│           ▼                                                     │
│  3. Deduplication Engine                                         │
│     ┌─────────────────────────────────────────┐                │
│     │  a. Hash-based dedup                    │                │
│     │  b. Semantic similarity check           │                │
│     │  c. URL normalization                   │                │
│     └─────────────────────────────────────────┘                │
│           │                                                     │
│           ▼                                                     │
│  4. Verification Engine                                         │
│     ┌─────────────────────────────────────────┐                │
│     │  a. Link health check                   │                │
│     │  b. Deadline validation                 │                │
│     │  c. Company verification                │                │
│     └─────────────────────────────────────────┘                │
│           │                                                     │
│           ▼                                                     │
│  5. Scam Detection Engine                                       │
│     ┌─────────────────────────────────────────┐                │
│     │  a. Rule-based checks                   │                │
│     │  b. AI scam scoring                     │                │
│     │  c. Flag suspicious jobs                │                │
│     └─────────────────────────────────────────┘                │
│           │                                                     │
│           ▼                                                     │
│  6. Classification Engine                                       │
│     ┌─────────────────────────────────────────┐                │
│     │  a. Job type classification             │                │
│     │  b. Skill extraction                    │                │
│     │  c. Category tagging                    │                │
│     └─────────────────────────────────────────┘                │
│           │                                                     │
│           ▼                                                     │
│  7. Save to Database                                            │
│           │                                                     │
│           ▼                                                     │
│  8. Check Watchlists                                            │
│           │                                                     │
│           ▼                                                     │
│  9. Trigger Notifications (if matches found)                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 2. Link Verification

| Property | Value |
|----------|-------|
| **Job ID** | `link_verification` |
| **Trigger** | Interval |
| **Interval** | 6 hours |
| **Priority** | Medium |
| **Timeout** | 15 minutes |

**Description:** Verifies all job links are still accessible.

**Execution Flow:**
```
1. Get all active jobs from database
2. For each job (batch of 50):
   a. HTTP HEAD request to job URL
   b. Check response status code
   c. Detect redirects (404, 500, etc.)
   d. Update job.is_active if link broken
3. Generate broken links report
4. Notify admin if many links broken
```

---

### 3. Scam Re-analysis

| Property | Value |
|----------|-------|
| **Job ID** | `scam_reanalysis` |
| **Trigger** | Interval |
| **Interval** | 12 hours |
| **Priority** | Medium |
| **Timeout** | 20 minutes |

**Description:** Re-analyzes jobs for scam indicators with updated AI models.

---

### 4. Skill Trends Update

| Property | Value |
|----------|-------|
| **Job ID** | `skill_trends` |
| **Trigger** | Cron (daily at 2:00 AM) |
| **Priority** | Low |
| **Timeout** | 10 minutes |

**Description:** Updates skill market trends based on recent job data.

**Execution Flow:**
```
1. Analyze jobs from last 7 days
2. Count skill mentions
3. Calculate growth rates
4. Update skill_trends table
5. Generate trend report
```

---

### 5. News Analysis

| Property | Value |
|----------|-------|
| **Job ID** | `news_analysis` |
| **Trigger** | Interval |
| **Interval** | 4 hours |
| **Priority** | Low |
| **Timeout** | 10 minutes |

**Description:** Analyzes cybersecurity news for hiring insights.

---

### 6. Daily Report Generation

| Property | Value |
|----------|-------|
| **Job ID** | `daily_report` |
| **Trigger** | Cron (daily at 6:00 AM) |
| **Priority** | High |
| **Timeout** | 5 minutes |

**Description:** Generates and sends daily report to all users.

**Report Contents:**
```
┌─────────────────────────────────────────────────────────────────┐
│                    DAILY REPORT CONTENTS                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📊 Summary                                                     │
│  • New internships found: 45                                    │
│  • New jobs found: 120                                          │
│  • Remote jobs: 35                                              │
│  • Government jobs: 8                                           │
│                                                                  │
│  💰 Top Opportunities                                           │
│  • Highest salary: ₹25,00,000 - Security Engineer              │
│  • Highest stipend: ₹50,000/month - SOC Analyst Intern         │
│                                                                  │
│  ⏰ Closing Today                                               │
│  • CrowdStrike - SOC Analyst (3 positions)                      │
│  • Palo Alto - Security Intern                                  │
│                                                                  │
│  ⏰ Closing Tomorrow                                            │
│  • Google - Security Engineer                                   │
│  • Microsoft - Azure Security                                   │
│                                                                  │
│  🎯 Must Apply (High Match)                                     │
│  • 5 jobs matching your skills > 80%                            │
│                                                                  │
│  🏢 Top Companies Hiring                                         │
│  • CrowdStrike (15 openings)                                    │
│  • Palo Alto Networks (12 openings)                             │
│  • Cloudflare (10 openings)                                     │
│                                                                  │
│  🔧 Top Skills in Demand                                        │
│  • Python (↑15%)                                                │
│  • SOC (↑12%)                                                   │
│  • Kubernetes (↑25%)                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 7. Weekly Report Generation

| Property | Value |
|----------|-------|
| **Job ID** | `weekly_report` |
| **Trigger** | Cron (Monday 8:00 AM) |
| **Priority** | High |
| **Timeout** | 10 minutes |

**Description:** Generates comprehensive weekly report.

**Report Contents:**
```
┌─────────────────────────────────────────────────────────────────┐
│                    WEEKLY REPORT CONTENTS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📊 Weekly Summary                                              │
│  • Total jobs discovered: 850                                   │
│  • Applications submitted: 25                                   │
│  • Interviews scheduled: 5                                      │
│                                                                  │
│  🏢 Top Hiring Companies                                        │
│  • CrowdStrike (45 openings)                                    │
│  • Palo Alto (38 openings)                                      │
│  • Cloudflare (32 openings)                                     │
│                                                                  │
│  📈 Hiring Trends                                               │
│  • SOC roles ↑20%                                               │
│  • Cloud Security ↑35%                                          │
│  • DevSecOps ↑15%                                               │
│                                                                  │
│  💰 Salary Trends                                               │
│  • Average intern stipend: ₹35,000/month                        │
│  • Average entry salary: ₹8,50,000/year                         │
│                                                                  │
│  🌍 Top Cities                                                  │
│  • Bangalore (120 jobs)                                         │
│  • Hyderabad (85 jobs)                                          │
│  • San Francisco (65 jobs)                                      │
│                                                                  │
│  🔮 Upcoming Hiring                                              │
│  • Google - Summer internships (Aug deadline)                   │
│  • Microsoft - Security rotations (Sept start)                  │
│                                                                  │
│  📜 New Certifications                                           │
│  • AWS Security Specialty - Free voucher available              │
│                                                                  │
│  🏆 Upcoming CTFs                                                │
│  • picoCTF 2026 - Registration open                             │
│  • DEF CON CTF - Qualifiers next week                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 8. Monthly Report Generation

| Property | Value |
|----------|-------|
| **Job ID** | `monthly_report` |
| **Trigger** | Cron (1st of month, 9:00 AM) |
| **Priority** | High |
| **Timeout** | 15 minutes |

**Description:** Generates comprehensive monthly analytics report.

---

### 9. Hiring Calendar Update

| Property | Value |
|----------|-------|
| **Job ID** | `hiring_calendar` |
| **Trigger** | Cron (1st of month, 12:00 AM) |
| **Priority** | Medium |
| **Timeout** | 10 minutes |

**Description:** Updates hiring predictions based on historical data.

---

### 10. Resume Match Refresh

| Property | Value |
|----------|-------|
| **Job ID** | `resume_match_refresh` |
| **Trigger** | Interval (every 6 hours) |
| **Priority** | Medium |
| **Timeout** | 10 minutes |

**Description:** Refreshes resume-job match scores for new jobs.

---

## Task Configuration

### Environment Variables

```env
# Scheduler Settings
SCRAPE_INTERVAL_MINUTES=30
REPORT_TIME_DAILY=06:00
REPORT_TIME_WEEKLY=08:00
REPORT_TIME_MONTHLY=09:00

# Task Timeouts
DISCOVERY_TIMEOUT_SECONDS=600
VERIFICATION_TIMEOUT_SECONDS=900
REPORT_TIMEOUT_SECONDS=300

# Concurrency
MAX_CONCURRENT_TASKS=5
MAX_CONCURRENT_SCRAPERS=3
```

### Task Priority Levels

| Priority | Value | Tasks |
|----------|-------|-------|
| Critical | 1 | Instant notifications, scam alerts |
| High | 2 | Job discovery, reports |
| Medium | 3 | Verification, trend updates |
| Low | 4 | News analysis, cleanup |

---

## Error Handling

### Retry Strategy

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(ScrapingError),
)
async def run_job_discovery():
    # Task implementation
    pass
```

### Dead Letter Queue

Failed tasks are logged and can be retried manually:

```bash
# Retry failed tasks
python -m cybershield.worker retry-failed

# View failed tasks
python -m cybershield.worker list-failed
```

---

## Monitoring

### Task Metrics

| Metric | Description |
|--------|-------------|
| `task_duration_seconds` | Task execution time |
| `task_success_count` | Successful executions |
| `task_failure_count` | Failed executions |
| `task_last_run_timestamp` | Last execution time |
| `jobs_discovered_total` | Total jobs discovered |
| `notifications_sent_total` | Total notifications sent |

### Health Check

```
GET /api/v1/scheduler/health
```

**Response:**
```json
{
    "status": "healthy",
    "scheduler_running": true,
    "tasks": {
        "job_discovery": {
            "status": "running",
            "last_run": "2026-07-30T10:30:00Z",
            "next_run": "2026-07-30T11:00:00Z",
            "run_count": 150,
            "failure_count": 2
        },
        "daily_report": {
            "status": "scheduled",
            "last_run": "2026-07-30T06:00:00Z",
            "next_run": "2026-07-31T06:00:00Z",
            "run_count": 30,
            "failure_count": 0
        }
    }
}
```

---

## Manual Task Execution

### API Endpoints

```bash
# Trigger job discovery manually
POST /api/v1/scheduler/trigger/job_discovery

# Trigger report generation
POST /api/v1/scheduler/trigger/daily_report

# Pause a task
POST /api/v1/scheduler/pause/{task_id}

# Resume a task
POST /api/v1/scheduler/resume/{task_id}
```

### CLI Commands

```bash
# Run all scheduled tasks once
python -m cybershield.worker run-all

# Run specific task
python -m cybershield.worker run job_discovery

# View task status
python -m cybershield.worker status

# Pause scheduler
python -m cybershield.worker pause

# Resume scheduler
python -m cybershield.worker resume
```

---

## Implementation Code

### Scheduler Setup

```python
# src/cybershield/scheduler/setup.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from cybershield.config import get_settings
from cybershield.scheduler.jobs import (
    run_job_discovery,
    verify_job_links,
    analyze_scams,
    update_skill_trends,
    analyze_news,
    generate_daily_report,
    generate_weekly_report,
    generate_monthly_report,
    update_hiring_calendar,
    refresh_resume_matches,
)

settings = get_settings()
scheduler = AsyncIOScheduler()


def setup_scheduler():
    """Configure and start the scheduler."""
    
    # Job Discovery - Every 30 minutes
    scheduler.add_job(
        run_job_discovery,
        IntervalTrigger(minutes=settings.scrape_interval_minutes),
        id="job_discovery",
        name="Job Discovery",
        priority=2,
        replace_existing=True,
    )
    
    # Link Verification - Every 6 hours
    scheduler.add_job(
        verify_job_links,
        IntervalTrigger(hours=6),
        id="link_verification",
        name="Link Verification",
        priority=3,
        replace_existing=True,
    )
    
    # Scam Re-analysis - Every 12 hours
    scheduler.add_job(
        analyze_scams,
        IntervalTrigger(hours=12),
        id="scam_reanalysis",
        name="Scam Re-analysis",
        priority=3,
        replace_existing=True,
    )
    
    # Skill Trends - Daily at 2 AM
    scheduler.add_job(
        update_skill_trends,
        CronTrigger(hour=2, minute=0),
        id="skill_trends",
        name="Skill Trends Update",
        priority=4,
        replace_existing=True,
    )
    
    # News Analysis - Every 4 hours
    scheduler.add_job(
        analyze_news,
        IntervalTrigger(hours=4),
        id="news_analysis",
        name="News Analysis",
        priority=4,
        replace_existing=True,
    )
    
    # Daily Report - 6 AM
    scheduler.add_job(
        generate_daily_report,
        CronTrigger(hour=6, minute=0),
        id="daily_report",
        name="Daily Report",
        priority=2,
        replace_existing=True,
    )
    
    # Weekly Report - Monday 8 AM
    scheduler.add_job(
        generate_weekly_report,
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="weekly_report",
        name="Weekly Report",
        priority=2,
        replace_existing=True,
    )
    
    # Monthly Report - 1st of month 9 AM
    scheduler.add_job(
        generate_monthly_report,
        CronTrigger(day=1, hour=9, minute=0),
        id="monthly_report",
        name="Monthly Report",
        priority=2,
        replace_existing=True,
    )
    
    # Hiring Calendar - 1st of month
    scheduler.add_job(
        update_hiring_calendar,
        CronTrigger(day=1, hour=0, minute=0),
        id="hiring_calendar",
        name="Hiring Calendar Update",
        priority=3,
        replace_existing=True,
    )
    
    # Resume Match Refresh - Every 6 hours
    scheduler.add_job(
        refresh_resume_matches,
        IntervalTrigger(hours=6),
        id="resume_match_refresh",
        name="Resume Match Refresh",
        priority=3,
        replace_existing=True,
    )
    
    return scheduler
```

### Worker Process

```python
# src/cybershield/worker.py

import asyncio
import signal
import sys

from cybershield.scheduler.setup import setup_scheduler, scheduler
from cybershield.utils.logger import setup_logging, get_logger

logger = get_logger(__name__)


async def main():
    """Main worker loop."""
    setup_logging()
    logger.info("Starting CSCIP worker...")
    
    # Setup scheduler
    scheduler_instance = setup_scheduler()
    scheduler_instance.start()
    
    logger.info("Worker started. Press Ctrl+C to stop.")
    
    # Handle shutdown
    def shutdown_handler(signum, frame):
        logger.info("Shutting down worker...")
        scheduler_instance.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        scheduler_instance.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

---

**Module Status**: ✅ Complete

**Next Module**: [Module 7: Discovery Engine](./07-discovery-engine.md)
