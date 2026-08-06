"""
API Usage tracking and quota management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException

from interntrack.auth.jwt import get_current_user, get_usage_stats, track_api_usage

router = APIRouter()


@router.get("/stats")
async def usage_stats(
    current_user: dict = Depends(get_current_user),
):
    """Get current API usage stats for the authenticated user."""
    user_id = current_user.get("sub", "anonymous")
    return get_usage_stats(user_id)


@router.post("/check")
async def check_quota(
    current_user: dict = Depends(get_current_user),
):
    """Check if the user has remaining quota. Returns 429 if exceeded."""
    user_id = current_user.get("sub", "anonymous")
    if not track_api_usage(user_id):
        raise HTTPException(
            status_code=429,
            detail="API quota exceeded. Please try again later.",
        )
    return {"status": "ok", **get_usage_stats(user_id)}
