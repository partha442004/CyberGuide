"""
Analytics Schemas

Pydantic models for analytics and insights API operations.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class SkillTrendResponse(BaseModel):
    """Schema for skill trend data."""
    skill_name: str
    category: Optional[str] = None
    job_count: int
    growth_rate: Optional[float] = None
    trend_direction: Optional[str] = None  # "rising", "stable", "declining"


class MarketInsight(BaseModel):
    """Schema for market insights."""
    total_skills_tracked: int
    top_demanding_skills: List[str]
    trending_skills: List[str]
    market_health: str
    last_updated: Optional[datetime] = None


class SalaryInsight(BaseModel):
    """Schema for salary insights."""
    skill_name: str
    avg_salary: float
    min_salary: float
    max_salary: float
    currency: str = "USD"
    sample_size: int


class HiringTrend(BaseModel):
    """Schema for hiring trends."""
    company_name: str
    job_count: int
    growth_rate: Optional[float] = None
    top_skills: List[str]


class GeographicInsight(BaseModel):
    """Schema for geographic insights."""
    country: str
    city: Optional[str] = None
    job_count: int
    avg_salary: Optional[float] = None
    top_companies: List[str]


class PredictionResponse(BaseModel):
    """Schema for prediction results."""
    prediction_type: str
    confidence: float
    details: dict
    valid_until: Optional[datetime] = None
