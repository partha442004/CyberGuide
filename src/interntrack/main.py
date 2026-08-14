"""
InternTrack - Main FastAPI Application
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from interntrack.api.router import api_router
from interntrack.api.v1.pwa import router as pwa_router
from interntrack.config import get_settings
from interntrack.database.session import close_db, init_db
from interntrack.domain.exceptions import AppException
from interntrack.metrics import (
    MetricsMiddleware,
    business_metrics_store,
    metrics_store,
)
from interntrack.middleware.rate_limit import RateLimitMiddleware, get_rate_limit_store
from interntrack.utils.logger import get_logger

settings = get_settings()
logger = get_logger("interntrack.main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_db()
    for warning in settings.validate_security():
        logger.warning(warning)
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title=settings.app_name,
    description="Internship & Job Tracker with AI-powered Discovery",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Rate limiting middleware - limits configurable via env vars.
# Registered BEFORE CORS so that CORS wraps it: rate-limited 429 responses
# still pass through CORS and carry the allow-origin headers for browser clients.
if settings.rate_limit_enabled:
    app.add_middleware(
        RateLimitMiddleware,
        default_limit=settings.rate_limit_per_minute,
        api_key_limit=settings.rate_limit_api_key_per_minute,
        api_key_header=settings.api_key_header,
        # Redis-backed when REDIS_URL is configured (shared across replicas),
        # in-memory otherwise; falls back gracefully on a Redis outage.
        store=get_rate_limit_store(),
    )

# Metrics middleware - records request counts/errors/latency for /metrics.
# Registered after the rate limiter so it also captures 429 responses (the
# rate limiter's own rejections are part of the error picture). /metrics itself
# is exempt from recording.
app.add_middleware(MetricsMiddleware)

# CORS middleware - origins configurable via CORS_ORIGINS env var (comma-separated)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=not settings.cors_allow_all,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

# Include API router
app.include_router(api_router, prefix="/api")

# PWA install shell (root-level /app routes, outside the /api prefix).
app.include_router(pwa_router)

# Brand assets (logo) served at /static/logo.png so emails can embed a
# public URL. Uses a package-relative path so it works from any CWD.
_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.exception_handler(AppException)
async def domain_exception_handler(_request: Request, exc: AppException):
    """Handle domain exceptions using their status codes and error payloads."""
    return JSONResponse(status_code=exc.status, content=exc.to_dict())


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception):
    """Global fallback exception handler."""
    payload: dict[str, Any] = {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An error occurred",
            "details": {"debug": str(exc)} if settings.debug else {},
        },
    }
    return JSONResponse(status_code=500, content=payload)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs" if settings.debug else None,
    }


@app.get("/health")
async def health():
    """Health check endpoint with a database connectivity probe.

    Creates its own session via ``async_session_factory`` inside the handler so
    that a fully unreachable database engine still returns 503 ``degraded``
    (a dependency-injected session would fail before the handler runs and
    surface as a 500). Returns 200 with ``status: healthy`` when the database
    responds, or 503 with ``status: degraded`` when session creation or the
    ``SELECT 1`` probe fails.
    """
    from interntrack.database.session import async_session_factory

    db_ok = False
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    payload = {
        "status": "healthy" if db_ok else "degraded",
        "version": settings.app_version,
        "database": "ok" if db_ok else "error",
    }
    if not db_ok:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.get("/metrics")
async def metrics():
    """Expose in-memory request + business metrics for monitoring.

    Returns request counts per path, error counts/rate (HTTP >= 500), average
    latency, a status-code histogram, plus the business metrics (DB query
    times, scraper success rates, notification delivery rates) under the
    ``business`` key. The metrics endpoint itself is not recorded, and it is
    exempt from rate limiting so scrapers stay reliable.
    """
    snapshot = metrics_store.snapshot()
    snapshot["business"] = business_metrics_store.snapshot()
    return snapshot


@app.get("/metrics/prometheus")
async def metrics_prometheus():
    """Expose metrics in Prometheus text exposition format.

    Lets a Prometheus server scrape the same in-memory counters via the
    standard text format (``# HELP`` / ``# TYPE`` + samples) without pulling
    in ``prometheus_client``. Includes both HTTP metrics and the business
    metrics (``interntrack_db_*``, ``interntrack_scraper_*``,
    ``interntrack_notification_*``). Like ``/metrics`` it is not recorded and
    is exempt from rate limiting so scrapers stay reliable.
    """
    body = (
        metrics_store.render_prometheus() + business_metrics_store.render_prometheus()
    )
    return Response(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


def cli():
    """CLI entry point."""
    import uvicorn

    uvicorn.run(
        "interntrack.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    cli()
