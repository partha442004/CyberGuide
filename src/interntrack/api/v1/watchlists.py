"""
Company watchlist API — track companies and surface their new jobs.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.api.schemas.watchlist import (
    CompanyWatchlistCreate,
    CompanyWatchlistItem,
    CompanyWatchlistList,
)
from interntrack.database.session import get_db
from interntrack.domain.models import CompanyWatchlist, Job

router = APIRouter()


@router.get("", response_model=CompanyWatchlistList)
async def list_watchlist(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """A user's watched companies, each with its current active-job count."""
    result = await db.execute(
        select(CompanyWatchlist)
        .where(CompanyWatchlist.user_id == user_id)
        .order_by(CompanyWatchlist.created_at.desc())
    )
    rows = result.scalars().all()
    items: list[CompanyWatchlistItem] = []
    for row in rows:
        count = 0
        try:
            count_result = await db.execute(
                select(func.count(Job.id)).where(
                    Job.company == row.company,
                    Job.is_active.is_(True),
                )
            )
            count = int(count_result.scalar_one() or 0)
        except Exception:
            count = 0
        items.append(
            CompanyWatchlistItem(
                id=row.id,
                company=row.company,
                notes=row.notes,
                active_jobs=count,
            )
        )
    return CompanyWatchlistList(watchlist=items, total=len(items))


@router.post("", status_code=201)
async def add_to_watchlist(
    payload: CompanyWatchlistCreate,
    db: AsyncSession = Depends(get_db),
):
    """Watch a company (dedupe per user — 409 when already watched)."""
    company = payload.company.strip()
    if not company:
        raise HTTPException(status_code=422, detail="Company name is required")
    existing = await db.execute(
        select(CompanyWatchlist).where(
            CompanyWatchlist.user_id == payload.user_id,
            CompanyWatchlist.company == company,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Company already watched")
    row = CompanyWatchlist(
        user_id=payload.user_id,
        company=company,
        notes=payload.notes,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "company": row.company, "notes": row.notes}


@router.delete("/{watch_id}", status_code=204)
async def remove_from_watchlist(
    watch_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Stop watching a company."""
    result = await db.execute(
        select(CompanyWatchlist).where(CompanyWatchlist.id == watch_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")
    await db.delete(row)
    await db.commit()
