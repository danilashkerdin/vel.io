import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

from database import get_db
from models import User, SponsoredTerritory, AdvertiserProfile, AdvertiserPayment
from auth import get_current_user
from schemas.advertiser import AdvertiserProfileSchema

logger = logging.getLogger("velo_io")
router = APIRouter(tags=["advertiser"])


def _ensure_profile(db: Session, user_id: UUID) -> AdvertiserProfile:
    profile = db.query(AdvertiserProfile).filter(AdvertiserProfile.user_id == user_id).first()
    if not profile:
        profile = AdvertiserProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("/api/advertiser/tiers")
def tiers():
    return settings.sponsored_tiers


@router.get("/api/advertiser/profile")
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_advertiser:
        raise HTTPException(403, "Только для рекламодателей")
    profile = _ensure_profile(db, current_user.id)
    return {
        "business_name": profile.business_name,
        "contact_phone": profile.contact_phone,
        "contact_telegram": profile.contact_telegram,
        "website": profile.website,
        "description": profile.description,
        "verified": profile.verified,
        "email": current_user.email,
    }


@router.put("/api/advertiser/profile")
def update_profile(
    data: AdvertiserProfileSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_advertiser:
        raise HTTPException(403, "Только для рекламодателей")
    profile = _ensure_profile(db, current_user.id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return {
        "business_name": profile.business_name,
        "contact_phone": profile.contact_phone,
        "contact_telegram": profile.contact_telegram,
        "website": profile.website,
        "description": profile.description,
        "verified": profile.verified,
    }


@router.get("/api/advertiser/dashboard")
def dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_advertiser:
        raise HTTPException(403, "Только для рекламодателей")

    zones = db.query(SponsoredTerritory).filter(SponsoredTerritory.owner_id == current_user.id).all()
    total_stars = (
        db.query(func.coalesce(func.sum(AdvertiserPayment.amount_stars), 0))
        .filter(AdvertiserPayment.user_id == current_user.id, AdvertiserPayment.status == "completed")
        .scalar()
    )

    return {
        "active_zones": sum(1 for z in zones if z.is_active),
        "total_zones": len(zones),
        "total_spent_stars": int(total_stars),
        "total_impressions": sum(z.impressions or 0 for z in zones),
        "total_clicks": sum(z.clicks or 0 for z in zones),
        "recent_payments": [
            {
                "id": str(p.id),
                "amount_stars": p.amount_stars,
                "purpose": p.purpose,
                "status": p.status,
                "created_at": p.created_at.isoformat(),
            }
            for p in db.query(AdvertiserPayment)
            .filter(AdvertiserPayment.user_id == current_user.id)
            .order_by(AdvertiserPayment.created_at.desc())
            .limit(5)
            .all()
        ],
    }


@router.get("/api/advertiser/payments")
def payments(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_advertiser:
        raise HTTPException(403, "Только для рекламодателей")
    items = (
        db.query(AdvertiserPayment)
        .filter(AdvertiserPayment.user_id == current_user.id)
        .order_by(AdvertiserPayment.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(p.id),
            "sponsored_territory_id": str(p.sponsored_territory_id) if p.sponsored_territory_id else None,
            "amount_stars": p.amount_stars,
            "purpose": p.purpose,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
        }
        for p in items
    ]


@router.get("/api/my-advertiser-zones")
def my_advertiser_zones(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_advertiser:
        raise HTTPException(403, "Только для рекламодателей")
    zones = (
        db.query(SponsoredTerritory)
        .filter(SponsoredTerritory.owner_id == current_user.id)
        .order_by(SponsoredTerritory.created_at.desc())
        .all()
    )
    return [_zone_to_dict(z) for z in zones]


@router.patch("/api/my-advertiser-zones/{zone_id}")
def update_advertiser_zone(
    zone_id: str,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_advertiser:
        raise HTTPException(403, "Только для рекламодателей")
    zone = db.query(SponsoredTerritory).filter(SponsoredTerritory.id == UUID(zone_id)).first()
    if not zone:
        raise HTTPException(404, "Зона не найдена")
    if zone.owner_id != current_user.id:
        raise HTTPException(403, "Это не ваша зона")
    allowed = {"business_name", "description", "image_url", "link_url", "color"}
    for key, value in data.items():
        if key in allowed:
            setattr(zone, key, value)
    db.commit()
    return {"status": "ok"}


def _zone_to_dict(zone: SponsoredTerritory) -> dict:
    return {
        "id": str(zone.id),
        "business_name": zone.business_name,
        "description": zone.description,
        "monthly_budget_rub": zone.monthly_budget_rub,
        "monthly_budget_stars": zone.monthly_budget_stars,
        "is_active": zone.is_active,
        "image_url": zone.image_url,
        "link_url": zone.link_url,
        "color": zone.color,
        "polygon": mapping(to_shape(zone.polygon)) if zone.polygon else None,
        "clicks": zone.clicks or 0,
        "impressions": zone.impressions or 0,
        "expires_at": zone.expires_at.isoformat() if zone.expires_at else None,
        "created_at": zone.created_at.isoformat(),
    }
