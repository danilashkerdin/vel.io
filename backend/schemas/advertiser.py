from pydantic import BaseModel, HttpUrl, Field
from typing import Optional


class AdvertiserProfileSchema(BaseModel):
    business_name: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    contact_telegram: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None


class AdvertiserDashboardStats(BaseModel):
    active_zones: int
    total_zones: int
    total_spent_stars: int
    total_impressions: int
    total_clicks: int
