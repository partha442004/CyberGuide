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
from interntrack.api.v1.ai_tools import router as ai_tools_router
from interntrack.api.v1.applications_v2 import router as applications_v2_router
from interntrack.api.v1.bookmarks import router as bookmarks_router
from interntrack.api.v1.domains import router as domains_router
from interntrack.api.v1.observability import router as observability_router
from interntrack.api.v1.resume_parser import router as resume_parser_router
from interntrack.api.v1.salary_insights import router as salary_insights_router
from interntrack.api.v1.usage import router as usage_router
from interntrack.api.v1.weekly_digest import router as weekly_digest_router

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
api_router.include_router(
    resume_parser_router, prefix="/v1/resume", tags=["Resume Parser"]
)
api_router.include_router(
    applications_v2_router, prefix="/v1/applications/v2", tags=["Applications V2"]
)
api_router.include_router(
    salary_insights_router, prefix="/v1/salary", tags=["Salary Insights"]
)
api_router.include_router(
    weekly_digest_router, prefix="/v1/digest", tags=["Weekly Digest"]
)
api_router.include_router(bookmarks_router, prefix="/v1/bookmarks", tags=["Bookmarks"])
api_router.include_router(ai_tools_router, prefix="/v1/ai", tags=["AI Tools"])
