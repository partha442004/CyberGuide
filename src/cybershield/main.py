"""
CyberShield Career Intelligence Platform - Main Application

FastAPI application entry point with all routes and middleware.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from cybershield.config import get_settings
from cybershield.middleware import RateLimitMiddleware, APIKeyMiddleware

settings = get_settings()
from cybershield.database.session import init_db
from cybershield.domain.exceptions import CyberShieldException


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Debug mode: {settings.debug}")
    await init_db()
    # Initialize Elasticsearch (optional - graceful fallback if unavailable)
    await es.init_elasticsearch(settings.elasticsearch_url)
    yield
    # Shutdown
    await es.close_elasticsearch()
    print(f"Shutting down {settings.app_name}")


app = FastAPI(
    title=settings.app_name,
    description="AI-powered Cybersecurity Career Intelligence Platform",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting Middleware
app.add_middleware(
    RateLimitMiddleware,
    default_limit=settings.rate_limit_per_minute,
    api_key_limit=settings.rate_limit_api_key_per_minute,
)

# API Key Authentication Middleware (only if enabled)
if settings.require_api_key and settings.api_keys:
    app.add_middleware(APIKeyMiddleware)


@app.exception_handler(CyberShieldException)
async def cybershield_exception_handler(
    request: Request, exc: CyberShieldException
) -> JSONResponse:
    """Handle CyberShield custom exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": str(exc),
            "details": exc.details,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
        },
    )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "AI-powered Cybersecurity Career Intelligence Platform",
        "docs": "/api/docs",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "debug": settings.debug,
    }


# Import and include routers
from cybershield.api.v1 import jobs, applications, users, analytics, notifications, resumes
from cybershield.api.v1.websocket import router as ws_router
from cybershield.api.v1.search import router as search_router
from cybershield.services import elasticsearch_service as es

app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(applications.router, prefix="/api/v1/applications", tags=["Applications"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(resumes.router, prefix="/api/v1/resumes", tags=["Resumes"])
app.include_router(ws_router, prefix="/api/v1", tags=["WebSocket"])
app.include_router(search_router, prefix="/api/v1/search", tags=["Search"])


if __name__ == "__main__":
    uvicorn.run(
        "cybershield.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
