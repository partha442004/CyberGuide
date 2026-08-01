"""
Users API Router

Endpoints for user management and watchlists.
"""

from typing import List

import bcrypt
from fastapi import APIRouter, Depends, HTTPException

from cybershield.dependencies import get_user_repository
from cybershield.domain.models import User as UserModel
from cybershield.repositories.user_repository import UserRepository
from cybershield.schemas.user import (
    CompanyWatchlistCreate,
    KeywordWatchlistCreate,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


def _serialize_watchlist(w) -> dict:
    """Serialize a Watchlist ORM object to dict."""
    return {
        "id": w.id,
        "user_id": w.user_id,
        "watch_type": w.watch_type,
        "value": w.value,
        "is_active": w.is_active,
        "match_count": w.match_count,
        "created_at": str(w.created_at) if w.created_at else None,
        "updated_at": str(w.updated_at) if w.updated_at else None,
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    repo: UserRepository = Depends(get_user_repository),
):
    """Get user by ID with preferences."""
    user = await repo.get_with_preferences(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    user_data: UserCreate,
    repo: UserRepository = Depends(get_user_repository),
):
    """Create a new user."""
    data = user_data.model_dump()
    password = data.pop("password", None)
    if password:
        data["hashed_password"] = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    else:
        data["hashed_password"] = ""
    # Filter to only fields that exist on the User model
    data = {k: v for k, v in data.items() if hasattr(UserModel, k)}
    user = await repo.create(data)
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    repo: UserRepository = Depends(get_user_repository),
):
    """Update user profile."""
    user = await repo.update(user_id, user_data.model_dump(exclude_unset=True))
    return user


@router.get("/{user_id}/company-watchlist", response_model=List[dict])
async def get_company_watchlist(
    user_id: str,
    repo: UserRepository = Depends(get_user_repository),
):
    """Get user's company watchlist."""
    watchlist = await repo.get_company_watchlist(user_id)
    return [_serialize_watchlist(w) for w in watchlist]


@router.post("/{user_id}/company-watchlist", status_code=201)
async def add_company_watchlist(
    user_id: str,
    watchlist_data: CompanyWatchlistCreate,
    repo: UserRepository = Depends(get_user_repository),
):
    """Add a company to user's watchlist."""
    try:
        watchlist = await repo.add_company_watchlist(
            user_id=user_id,
            company_id=watchlist_data.company_id,
        )
        return {"message": "Company added to watchlist", "id": watchlist.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{user_id}/company-watchlist/{company_id}")
async def remove_company_watchlist(
    user_id: str,
    company_id: str,
    repo: UserRepository = Depends(get_user_repository),
):
    """Remove a company from user's watchlist."""
    removed = await repo.remove_company_watchlist(user_id, company_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return {"message": "Company removed from watchlist"}


@router.get("/{user_id}/keyword-watchlist", response_model=List[dict])
async def get_keyword_watchlist(
    user_id: str,
    repo: UserRepository = Depends(get_user_repository),
):
    """Get user's keyword watchlist."""
    watchlist = await repo.get_keyword_watchlist(user_id)
    return [_serialize_watchlist(w) for w in watchlist]


@router.post("/{user_id}/keyword-watchlist", status_code=201)
async def add_keyword_watchlist(
    user_id: str,
    watchlist_data: KeywordWatchlistCreate,
    repo: UserRepository = Depends(get_user_repository),
):
    """Add a keyword to user's watchlist."""
    try:
        watchlist = await repo.add_keyword_watchlist(
            user_id=user_id,
            keyword=watchlist_data.keyword,
            category=watchlist_data.category,
        )
        return {"message": "Keyword added to watchlist", "id": watchlist.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{user_id}/keyword-watchlist/{keyword}")
async def remove_keyword_watchlist(
    user_id: str,
    keyword: str,
    repo: UserRepository = Depends(get_user_repository),
):
    """Remove a keyword from user's watchlist."""
    removed = await repo.remove_keyword_watchlist(user_id, keyword)
    if not removed:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return {"message": "Keyword removed from watchlist"}
