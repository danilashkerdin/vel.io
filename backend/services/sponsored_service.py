import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape as shapely_shape
from shapely.geometry import mapping

from models import SponsoredTerritory, UserBalance, Transaction, User, AdvertiserProfile
from config import settings


REVENUE_SHARE = 0.1  # 10% пользователю
SECONDS_IN_MONTH = 28 * 24 * 60 * 60  # 2 419 200 секунд в условном месяце


def _icon_size_for_stars(stars: int) -> int:
    for tier in settings.sponsored_tiers:
        if tier["stars"] == stars:
            return tier.get("icon_size", 32)
    return 32


def get_overlapping_sponsored(db: Session, polygon_geom):
    """Находит активные спонсорские территории, пересекающиеся с полигоном."""
    return (
        db.query(SponsoredTerritory)
        .filter(
            SponsoredTerritory.is_active == True,
            func.ST_Intersects(SponsoredTerritory.polygon, polygon_geom),
        )
        .all()
    )


def get_sponsored_in_bbox(db: Session, north: float, south: float, east: float, west: float):
    """Возвращает активные спонсорские территории в bounding box."""
    envelope = func.ST_MakeEnvelope(west, south, east, north, 4326)
    zones = (
        db.query(SponsoredTerritory)
        .filter(
            SponsoredTerritory.is_active == True,
            func.ST_Intersects(SponsoredTerritory.polygon, envelope),
        )
        .all()
    )

    # Prefetch profiles for 3⭐ zones
    premium_owner_ids = [z.owner_id for z in zones if (z.monthly_budget_stars or 0) >= 3 and z.owner_id]
    profiles: dict[uuid.UUID, AdvertiserProfile] = {}
    if premium_owner_ids:
        for p in db.query(AdvertiserProfile).filter(AdvertiserProfile.user_id.in_(premium_owner_ids)).all():
            profiles[p.user_id] = p

    return [
        {
            "id": str(z.id),
            "business_name": z.business_name,
            "description": z.description,
            "link_url": z.link_url,
            "color": z.color,
            "polygon": mapping(to_shape(z.polygon)),
            "icon_size": _icon_size_for_stars(z.monthly_budget_stars),
            "monthly_budget_stars": z.monthly_budget_stars,
        }
        | (
            # Стандарт (3000⭐)+: image visible in popup
            {"image_url": z.image_url}
            if (z.monthly_budget_stars or 0) >= 3000
            else {}
        )
        | (
            # Премиум (5000⭐)+: contacts from advertiser profile
            {
                "contact_phone": profiles[z.owner_id].contact_phone,
                "contact_telegram": profiles[z.owner_id].contact_telegram,
                "website": profiles[z.owner_id].website,
            }
            if (z.monthly_budget_stars or 0) >= 5000 and z.owner_id and z.owner_id in profiles
            else {}
        )
        for z in zones
    ]


def process_capture_rewards(db: Session, territory_polygon, capturing_user: User):
    """При перехвате спонсорской территории выплачивает предыдущему владельцу
    пропорционально времени владения. Новый владелец начинает копить долю."""
    sponsored_zones = get_overlapping_sponsored(db, territory_polygon)
    if not sponsored_zones:
        return []

    rewards = []

    # Prefetch existing UserBalance для всех участников
    owner_ids = [z.current_owner_id for z in sponsored_zones if z.current_owner_id and z.current_owner_id != capturing_user.id]
    existing_balances: dict[uuid.UUID, UserBalance] = {}
    if owner_ids:
        for b in db.query(UserBalance).filter(UserBalance.user_id.in_(owner_ids)).all():
            existing_balances[b.user_id] = b

    now = datetime.now(timezone.utc)

    for zone in sponsored_zones:
        if zone.current_owner_id == capturing_user.id:
            continue

        # Выплата предыдущему владельцу пропорционально времени владения
        if zone.current_owner_id and zone.owned_since:
            prev_owner_id = zone.current_owner_id
            owned_since = zone.owned_since.replace(tzinfo=timezone.utc)
            seconds_held = (now - owned_since).total_seconds()
            if seconds_held > 0:
                earned = int(zone.monthly_budget_rub * REVENUE_SHARE * (seconds_held / SECONDS_IN_MONTH))
                if earned > 0:
                    balance = existing_balances.get(prev_owner_id)
                    if not balance:
                        balance = UserBalance(user_id=prev_owner_id)
                        existing_balances[prev_owner_id] = balance
                        db.add(balance)

                    balance.balance_rub = (balance.balance_rub or 0) + earned
                    balance.total_earned_rub = (balance.total_earned_rub or 0) + earned
                    balance.updated_at = now

                    tx = Transaction(
                        user_id=prev_owner_id,
                        amount_rub=earned,
                        type="earned",
                        description=f"Доля от спонсорской территории «{zone.business_name}» — {earned}₽ за {int(seconds_held)}с владения",
                        sponsored_territory_id=zone.id,
                    )
                    db.add(tx)

        # Переход владения к захватившему
        zone.current_owner_id = capturing_user.id
        zone.owned_since = now

        rewards.append({
            "business_name": zone.business_name,
            "monthly_budget_rub": zone.monthly_budget_rub,
            "your_share_monthly_rub": int(zone.monthly_budget_rub * REVENUE_SHARE),
        })

    return rewards


def get_user_balance(db: Session, user_id: uuid.UUID):
    """Возвращает баланс пользователя."""
    balance = db.query(UserBalance).filter(
        UserBalance.user_id == user_id
    ).first()
    if not balance:
        return {"balance_rub": 0, "total_earned_rub": 0}
    return {
        "balance_rub": balance.balance_rub,
        "total_earned_rub": balance.total_earned_rub,
    }


def get_user_transactions(db: Session, user_id: uuid.UUID, limit: int = 20, offset: int = 0):
    """Возвращает историю транзакций пользователя."""
    txns = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(t.id),
            "amount_rub": t.amount_rub,
            "type": t.type,
            "description": t.description,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
        }
        for t in txns
    ]


def get_owned_sponsored(db: Session, user_id: uuid.UUID):
    """Возвращает спонсорские территории, принадлежащие пользователю."""
    zones = (
        db.query(SponsoredTerritory)
        .filter(
            SponsoredTerritory.current_owner_id == user_id,
            SponsoredTerritory.is_active == True,
        )
        .all()
    )
    return [
        {
            "id": str(z.id),
            "business_name": z.business_name,
            "description": z.description,
            "monthly_budget_rub": z.monthly_budget_rub,
            "your_share_monthly_rub": int(z.monthly_budget_rub * REVENUE_SHARE),
            "owned_since": z.owned_since.isoformat() if z.owned_since else None,
            "image_url": z.image_url,
            "link_url": z.link_url,
            "color": z.color,
            "polygon": mapping(to_shape(z.polygon)),
        }
        for z in zones
    ]
