"""
User Schemas

Pydantic models for user management API operations.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    """Base user schema with common fields."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=255)
    full_name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user."""
    id: Optional[str] = None
    password: str = Field(..., min_length=6, max_length=128)
    headline: Optional[str] = None
    target_roles: Optional[List[str]] = []
    target_locations: Optional[List[str]] = []
    target_companies: Optional[List[str]] = []


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    headline: Optional[str] = None
    target_roles: Optional[List[str]] = None
    target_locations: Optional[List[str]] = None
    target_companies: Optional[List[str]] = None


class UserResponse(UserBase):
    """Schema for user response."""
    id: str
    is_active: bool = True
    is_verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CompanyWatchlistCreate(BaseModel):
    """Schema for adding company to watchlist."""
    company_id: str = Field(..., min_length=1)
    notify_new_jobs: bool = True
    notify_any_role: bool = True
    specific_roles: Optional[List[str]] = []
    specific_locations: Optional[List[str]] = []


class KeywordWatchlistCreate(BaseModel):
    """Schema for adding keyword to watchlist."""
    keyword: str = Field(..., min_length=1, max_length=100)
    category: Optional[str] = None
    notify_new_matches: bool = True
    min_match_score: float = 0.7
