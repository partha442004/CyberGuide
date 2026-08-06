"""
Bookmark API — save interesting jobs for later with reminders.
"""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interntrack.database.session import get_db
from interntrack.domain.models import Bookmark, Job

router = APIRouter()


class BookmarkCreate(BaseModel):
    """Create a bookmark."""

    item_type: str = "job"  # job, company, skill
    item_id: str
    notes: str | None = None
    tags: list[str] = []


class BookmarkUpdate(BaseModel):
    """Update a bookmark."""

    notes: str | None = None
    tags: list[str] | None = None


@router.get("/")
async def list_bookmarks(
    item_type: str | None = None,
    tag: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all bookmarks with optional type/tag filter."""
    query = select(Bookmark)
    if item_type:
        query = query.where(Bookmark.item_type == item_type)
    query = query.order_by(Bookmark.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    bookmarks = result.scalars().all()

    # Filter by tag if provided
    if tag:
        bookmarks = [b for b in bookmarks if tag in (b.tags or [])]

    # Enrich job bookmarks with job details
    enriched = []
    for bm in bookmarks:
        item: dict[str, Any] = {
            "id": bm.id,
            "item_type": bm.item_type,
            "item_id": bm.item_id,
            "notes": bm.notes,
            "tags": bm.tags or [],
            "created_at": str(bm.created_at) if bm.created_at else None,
        }

        # Fetch job details if it's a job bookmark
        if bm.item_type == "job":
            job_result = await db.execute(select(Job).where(Job.id == bm.item_id))
            job = job_result.scalar_one_or_none()
            if job:
                item["job"] = {
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "url": job.url,
                    "source": job.source.value if job.source else "unknown",
                }

        enriched.append(item)

    return {
        "bookmarks": enriched,
        "total": len(enriched),
    }


@router.post("/")
async def create_bookmark(
    payload: BookmarkCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new bookmark."""
    # Check if already bookmarked
    existing = await db.execute(
        select(Bookmark).where(
            Bookmark.item_type == payload.item_type,
            Bookmark.item_id == payload.item_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already bookmarked")

    # Validate item exists
    if payload.item_type == "job":
        job_result = await db.execute(select(Job).where(Job.id == payload.item_id))
        if not job_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Job not found")

    bookmark = Bookmark(
        id=str(uuid4()),
        item_type=payload.item_type,
        item_id=payload.item_id,
        notes=payload.notes,
        tags=payload.tags,
    )
    db.add(bookmark)
    await db.commit()

    return {
        "id": bookmark.id,
        "message": f"Bookmarked {payload.item_type}",
    }


@router.delete("/{bookmark_id}")
async def delete_bookmark(
    bookmark_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove a bookmark."""
    result = await db.execute(select(Bookmark).where(Bookmark.id == bookmark_id))
    bookmark = result.scalar_one_or_none()
    if not bookmark:
        raise HTTPException(status_code=404, detail="Bookmark not found")

    await db.delete(bookmark)
    await db.commit()

    return {"message": "Bookmark removed"}


@router.put("/{bookmark_id}")
async def update_bookmark(
    bookmark_id: str,
    payload: BookmarkUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update bookmark notes or tags."""
    result = await db.execute(select(Bookmark).where(Bookmark.id == bookmark_id))
    bookmark = result.scalar_one_or_none()
    if not bookmark:
        raise HTTPException(status_code=404, detail="Bookmark not found")

    if payload.notes is not None:
        bookmark.notes = payload.notes  # type: ignore[assignment]
    if payload.tags is not None:
        bookmark.tags = payload.tags  # type: ignore[assignment]

    await db.commit()

    return {"message": "Bookmark updated"}


@router.get("/tags")
async def list_tags(db: AsyncSession = Depends(get_db)):
    """List all unique tags across bookmarks."""
    result = await db.execute(select(Bookmark))
    bookmarks = result.scalars().all()

    all_tags: set[str] = set()
    for bm in bookmarks:
        if bm.tags:
            all_tags.update(bm.tags)

    return {"tags": sorted(all_tags)}
