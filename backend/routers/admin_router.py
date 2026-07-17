import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape as shapely_shape
from shapely.geometry import mapping

from database import get_db
from models import User, Territory, SponsoredTerritory, UserBalance, Transaction
from auth import get_current_user
from config import settings
from schemas import admin as schemas
from schemas.admin import SponsoredTerritoryCreate, SponsoredTerritoryUpdate

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_EMAIL = settings.ADMIN_EMAIL


def _require_admin(current_user: User = Depends(get_current_user)):
    if current_user.email != ADMIN_EMAIL:
        raise HTTPException(403, "Только для администратора")
    return current_user


@router.get("/tiers")
def get_tiers(_=Depends(_require_admin)):
    return settings.sponsored_tiers


@router.get("/users")
def admin_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(_require_admin),
):
    users = (
        db.query(
            User.id, User.email, User.username, User.is_premium,
            User.is_advertiser, User.captures_count, User.created_at,
            UserBalance.balance_rub,
        )
        .outerjoin(UserBalance, UserBalance.user_id == User.id)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "username": u.username,
            "is_premium": u.is_premium,
            "is_advertiser": u.is_advertiser,
            "captures_count": u.captures_count,
            "balance_rub": u.balance_rub or 0,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.get("/users/{user_id}")
def admin_user_detail(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(_require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
    territory_count = db.query(func.count(Territory.id)).filter(
        Territory.user_id == user_id
    ).scalar() or 0
    total_area = db.query(func.coalesce(func.sum(Territory.area), 0)).filter(
        Territory.user_id == user_id
    ).scalar() or 0

    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "is_premium": user.is_premium,
        "is_advertiser": user.is_advertiser,
        "captures_count": user.captures_count,
        "territory_count": territory_count,
        "total_area": float(total_area),
        "balance_rub": balance.balance_rub if balance else 0,
        "total_earned_rub": balance.total_earned_rub if balance else 0,
        "referral_bonuses": user.referral_bonuses,
        "telegram_chat_id": user.telegram_chat_id,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.patch("/users/{user_id}")
def admin_update_user(
    user_id: uuid.UUID,
    is_premium: bool | None = None,
    db: Session = Depends(get_db),
    _=Depends(_require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    if is_premium is not None:
        user.is_premium = is_premium
    db.commit()
    return {"ok": True, "user_id": str(user.id), "is_premium": user.is_premium}


@router.post("/users/{user_id}/balance")
def admin_set_balance(
    user_id: uuid.UUID,
    body: schemas.AdminBalanceUpdate,
    db: Session = Depends(get_db),
    _=Depends(_require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
    if not balance:
        balance = UserBalance(user_id=user_id, balance_rub=0, total_earned_rub=0)
        db.add(balance)
    balance.balance_rub = max(0, (balance.balance_rub or 0) + body.amount)
    db.commit()
    return {"balance_rub": balance.balance_rub}
def admin_dashboard(db: Session = Depends(get_db), _=Depends(_require_admin)):
    total = db.query(func.count(SponsoredTerritory.id)).scalar() or 0
    active = db.query(func.count(SponsoredTerritory.id)).filter(
        SponsoredTerritory.is_active == True
    ).scalar() or 0

    total_monthly = db.query(func.sum(SponsoredTerritory.monthly_budget_rub)).filter(
        SponsoredTerritory.is_active == True
    ).scalar() or 0

    total_earned = db.query(func.sum(UserBalance.total_earned_rub)).scalar() or 0

    total_paid_out = db.query(func.coalesce(func.sum(Transaction.amount_rub), 0)).filter(
        Transaction.type == "payout",
        Transaction.status == "completed",
    ).scalar() or 0

    pending_payouts = db.query(func.count(UserBalance.id)).filter(
        UserBalance.balance_rub > 0
    ).scalar() or 0

    return {
        "total_sponsored": total,
        "active_sponsored": active,
        "total_monthly_revenue_rub": int(total_monthly),
        "total_earned_by_users_rub": int(total_earned),
        "total_paid_out_rub": abs(int(total_paid_out)),
        "pending_payouts": pending_payouts,
    }


@router.get("/sponsored-territories")
def list_sponsored(
    db: Session = Depends(get_db),
    _=Depends(_require_admin),
):
    zones = db.query(SponsoredTerritory).order_by(
        SponsoredTerritory.created_at.desc()
    ).all()

    def _icon_size(stars):
        if not stars:
            return 32
        for t in settings.sponsored_tiers:
            if t["stars"] == stars:
                return t.get("icon_size", 32)
        return 32

    result = []
    for z in zones:
        owner_name = None
        if z.current_owner_id:
            owner = db.query(User).filter(User.id == z.current_owner_id).first()
            owner_name = owner.username if owner else None

        result.append({
            "id": str(z.id),
            "business_name": z.business_name,
            "description": z.description,
            "monthly_budget_rub": z.monthly_budget_rub,
            "is_active": z.is_active,
            "color": z.color,
            "image_url": z.image_url,
            "link_url": z.link_url,
            "polygon": mapping(to_shape(z.polygon)),
            "current_owner_id": str(z.current_owner_id) if z.current_owner_id else None,
            "current_owner_name": owner_name,
            "owned_since": z.owned_since.isoformat() if z.owned_since else None,
            "created_at": z.created_at.isoformat(),
            "icon_size": _icon_size(z.monthly_budget_stars),
        })
    return result


@router.post("/sponsored-territories")
def create_sponsored(
    data: SponsoredTerritoryCreate,
    db: Session = Depends(get_db),
    _=Depends(_require_admin),
):
    polygon = from_shape(shapely_shape(data.polygon), srid=4326)
    zone = SponsoredTerritory(
        business_name=data.business_name,
        description=data.description,
        polygon=polygon,
        monthly_budget_rub=data.monthly_budget_rub,
        image_url=data.image_url,
        link_url=data.link_url,
        color=data.color,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return {"id": str(zone.id), "status": "created"}


@router.patch("/sponsored-territories/{zone_id}")
def update_sponsored(
    zone_id: str,
    data: SponsoredTerritoryUpdate,
    db: Session = Depends(get_db),
    _=Depends(_require_admin),
):
    zone = db.query(SponsoredTerritory).filter(
        SponsoredTerritory.id == zone_id
    ).first()
    if not zone:
        raise HTTPException(404, "Спонсорская территория не найдена")

    if data.business_name is not None:
        zone.business_name = data.business_name
    if data.description is not None:
        zone.description = data.description
    if data.monthly_budget_rub is not None:
        zone.monthly_budget_rub = data.monthly_budget_rub
    if data.is_active is not None:
        zone.is_active = data.is_active
    if data.image_url is not None:
        zone.image_url = data.image_url
    if data.link_url is not None:
        zone.link_url = data.link_url
    if data.color is not None:
        zone.color = data.color
    if data.polygon is not None:
        zone.polygon = from_shape(shapely_shape(data.polygon), srid=4326)

    db.commit()
    return {"status": "updated"}


@router.delete("/sponsored-territories/{zone_id}")
def delete_sponsored(
    zone_id: str,
    db: Session = Depends(get_db),
    _=Depends(_require_admin),
):
    zone = db.query(SponsoredTerritory).filter(
        SponsoredTerritory.id == zone_id
    ).first()
    if not zone:
        raise HTTPException(404, "Спонсорская территория не найдена")
    db.delete(zone)
    db.commit()
    return {"status": "deleted"}


# ─── Выплаты (админ) ───


@router.get("/payouts/pending")
def pending_payouts(
    db: Session = Depends(get_db),
    _=Depends(_require_admin),
):
    """Пользователи с накопленным балансом, готовые к выплате."""
    balances = (
        db.query(UserBalance, User.username)
        .join(User, UserBalance.user_id == User.id)
        .filter(UserBalance.balance_rub > 0)
        .order_by(UserBalance.updated_at.asc())
        .all()
    )
    return [
        {
            "user_id": str(b.user_id),
            "username": username,
            "balance_rub": b.balance_rub,
            "total_earned_rub": b.total_earned_rub,
            "updated_at": b.updated_at.isoformat() if b.updated_at else None,
        }
        for b, username in balances
    ]


@router.get("/payouts/history")
def payout_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(_require_admin),
):
    """История выплат."""
    txns = (
        db.query(Transaction, User.username)
        .join(User, Transaction.user_id == User.id)
        .filter(Transaction.type == "payout")
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(t.id),
            "user_id": str(t.user_id),
            "username": username,
            "amount_rub": abs(t.amount_rub),
            "status": t.status,
            "description": t.description,
            "created_at": t.created_at.isoformat(),
        }
        for t, username in txns
    ]


@router.post("/payouts/process/{user_id}")
def process_payout(
    user_id: str,
    db: Session = Depends(get_db),
    _=Depends(_require_admin),
):
    """Админ подтверждает выплату пользователю (ручная отметка)."""
    balance = db.query(UserBalance).filter(
        UserBalance.user_id == user_id
    ).first()
    if not balance or balance.balance_rub <= 0:
        raise HTTPException(400, "Нет средств для выплаты")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    amount_rub = balance.balance_rub
    wallet = user.ton_wallet or "—"
    description = f"Выплата {amount_rub}₽ на TON {wallet[:6]}*** — обработана администратором"

    tx = Transaction(
        user_id=user.id,
        amount_rub=-amount_rub,
        type="payout",
        description=description,
        status="completed",
    )
    db.add(tx)
    balance.balance_rub = 0
    balance.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "success": True,
        "user_id": user_id,
        "username": user.username,
        "amount_rub": amount_rub,
        "wallet": wallet,
        "method": "manual",
    }
