from pydantic import BaseModel
from typing import Optional, List


class SponsoredTerritoryCreate(BaseModel):
    business_name: str
    description: Optional[str] = None
    polygon: dict  # GeoJSON
    monthly_budget_rub: int = 5000
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    color: str = "#FFD700"


class SponsoredTerritoryUpdate(BaseModel):
    business_name: Optional[str] = None
    description: Optional[str] = None
    polygon: Optional[dict] = None
    monthly_budget_rub: Optional[int] = None
    is_active: Optional[bool] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    color: Optional[str] = None


class AdminDashboard(BaseModel):
    total_sponsored: int
    active_sponsored: int
    total_monthly_revenue: int
    total_earned_by_users: int
    pending_payouts: int


class AdminBalanceUpdate(BaseModel):
    amount: int  # положительное — начислить, отрицательное — списать
