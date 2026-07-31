"""
Main API router.
"""

from fastapi import APIRouter

from interntrack.api.v1 import jobs, applications, reports, notifications, skills, dashboard

api_router = APIRouter()

# Include versioned routers
api_router.include_router(jobs.router, prefix="/v1/jobs", tags=["Jobs"])
api_router.include_router(applications.router, prefix="/v1/applications", tags=["Applications"])
api_router.include_router(reports.router, prefix="/v1/reports", tags=["Reports"])
api_router.include_router(notifications.router, prefix="/v1/notifications", tags=["Notifications"])
api_router.include_router(skills.router, prefix="/v1/skills", tags=["Skills"])
api_router.include_router(dashboard.router, prefix="/v1/dashboard", tags=["Dashboard"])
