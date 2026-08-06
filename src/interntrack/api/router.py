"""
Main API router.
"""

from fastapi import APIRouter

from interntrack.api.v1 import (
    applications,
    dashboard,
    jobs,
    notifications,
    reports,
    skills,
    users,
    watchlists,
)
from interntrack.api.v1.domains import router as domains_router
from interntrack.api.v1.observability import router as observability_router
from interntrack.api.v1.usage import router as usage_router

api_router = APIRouter()

# Include versioned routers
api_router.include_router(jobs.router, prefix="/v1/jobs", tags=["Jobs"])
api_router.include_router(users.router, prefix="/v1/users", tags=["Users"])
api_router.include_router(
    applications.router,
    prefix="/v1/applications",
    tags=["Applications"],
)
api_router.include_router(reports.router, prefix="/v1/reports", tags=["Reports"])
api_router.include_router(
    notifications.router,
    prefix="/v1/notifications",
    tags=["Notifications"],
)
api_router.include_router(skills.router, prefix="/v1/skills", tags=["Skills"])
api_router.include_router(dashboard.router, prefix="/v1/dashboard", tags=["Dashboard"])
api_router.include_router(
    watchlists.router,
    prefix="/v1/watchlists",
    tags=["Watchlists"],
)

# New feature routers
api_router.include_router(usage_router, prefix="/v1/usage", tags=["Usage"])
api_router.include_router(domains_router, prefix="/v1/domains", tags=["Domains"])
api_router.include_router(
    observability_router, prefix="/v1/observability", tags=["Observability"]
)
