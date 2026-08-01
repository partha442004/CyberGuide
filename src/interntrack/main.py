"""
InternTrack - Main FastAPI Application
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from interntrack.api.router import api_router
from interntrack.config import get_settings
from interntrack.database.session import close_db, init_db
from interntrack.domain.exceptions import AppException
from interntrack.middleware.rate_limit import RateLimitMiddleware
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
    )

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
    """Health check endpoint."""
    return {"status": "healthy"}


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
