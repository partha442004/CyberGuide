"""
CyberGuide Startup Script

Starts all services:
- API Server (FastAPI)
- Dashboard (Streamlit)
- Scheduler (APScheduler)
"""

import logging
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


def start_api():
    """Start the FastAPI server."""
    logger.info("Starting API server...")
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "cybershield.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--reload",
            ],
            cwd=str(PROJECT_ROOT),
        )
        logger.info(f"API server started (PID: {proc.pid})")
        return proc
    except Exception as e:
        logger.error(f"Failed to start API server: {e}")
        return None


def start_dashboard():
    """Start the Streamlit dashboard."""
    logger.info("Starting dashboard...")
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "cybershield/dashboard/app.py",
                "--server.port",
                "8501",
                "--server.address",
                "0.0.0.0",
            ],
            cwd=str(PROJECT_ROOT),
        )
        logger.info(f"Dashboard started (PID: {proc.pid})")
        return proc
    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}")
        return None


def start_scheduler():
    """Start the scheduler."""
    logger.info("Starting scheduler...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "cybershield.scheduler"],
            cwd=str(PROJECT_ROOT),
        )
        logger.info(f"Scheduler started (PID: {proc.pid})")
        return proc
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        return None


def main():
    """Main entry point - starts all services."""
    logger.info("=" * 60)
    logger.info("🛡️  CyberGuide Career Intelligence Platform")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Starting all services...")
    logger.info("  - API Server:  http://localhost:8000")
    logger.info("  - Dashboard:   http://localhost:8501")
    logger.info("  - API Docs:    http://localhost:8000/api/docs")
    logger.info("")
    logger.info("Press Ctrl+C to stop all services")
    logger.info("=" * 60)

    processes = []

    try:
        # Start API server
        api_proc = start_api()
        if api_proc:
            processes.append(api_proc)
        else:
            logger.error("Cannot continue without API server")
            sys.exit(1)

        time.sleep(2)  # Wait for API to start

        # Start dashboard
        dashboard_proc = start_dashboard()
        if dashboard_proc:
            processes.append(dashboard_proc)

        time.sleep(1)

        # Start scheduler
        scheduler_proc = start_scheduler()
        if scheduler_proc:
            processes.append(scheduler_proc)

        logger.info("All services started successfully!")
        logger.info("")

        # Wait for any process to exit
        while True:
            for proc in processes:
                if proc.poll() is not None:
                    logger.error(f"Process {proc.pid} exited with code {proc.returncode}")
                    # Stop all remaining processes
                    for p in processes:
                        if p.poll() is None:
                            p.terminate()
                    sys.exit(1)
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("")
        logger.info("Shutting down all services...")
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                logger.info(f"Stopped process {proc.pid}")
        logger.info("All services stopped. Goodbye! 👋")
        sys.exit(0)


if __name__ == "__main__":
    main()
