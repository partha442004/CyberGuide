"""
Reports API endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.report import ReportResponse
from interntrack.database.session import get_db
from interntrack.services.report_service import ReportService

router = APIRouter()


@router.get("/daily", response_model=ReportResponse)
async def get_daily_report(
    db: AsyncSession = Depends(get_db),
):
    """Get daily report."""
    service = ReportService(db)
    return await service.generate_daily_report()


@router.get("/weekly", response_model=ReportResponse)
async def get_weekly_report(
    db: AsyncSession = Depends(get_db),
):
    """Get weekly report."""
    service = ReportService(db)
    return await service.generate_weekly_report()


@router.get("/monthly", response_model=ReportResponse)
async def get_monthly_report(
    db: AsyncSession = Depends(get_db),
):
    """Get monthly report."""
    service = ReportService(db)
    return await service.generate_monthly_report()


@router.get("/{report_type}/html")
async def get_report_html(
    report_type: str,
    db: AsyncSession = Depends(get_db),
):
    """Get report as HTML."""
    from fastapi.responses import HTMLResponse

    service = ReportService(db)

    if report_type == "daily":
        data = await service.generate_daily_report()
    elif report_type == "weekly":
        data = await service.generate_weekly_report()
    elif report_type == "monthly":
        data = await service.generate_monthly_report()
    else:
        return HTMLResponse("Invalid report type", status_code=400)

    html = await service.render_report(data)
    return HTMLResponse(html)
