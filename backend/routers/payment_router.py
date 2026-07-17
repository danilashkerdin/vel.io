import json
import logging
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from config import settings
from database import get_db
from models import User, UserBalance, Transaction, SponsoredTerritory, Territory, AdvertiserPayment
from auth import get_current_user
from services.sponsored_service import get_owned_sponsored

logger = logging.getLogger("velo_io")
router = APIRouter(tags=["payment"])

FREE_LIMIT = settings.FREE_CAPTURES_LIMIT


# ─── Telegram Stars — Invoice ───


@router.post("/api/payment/create-star-invoice")
def create_star_invoice(
    purpose: str = Query(...),  # "premium" | "sponsored" | "top_up"
    business_name: str = Query(None),
    monthly_budget_stars: int = Query(None),
    polygon: str = Query(None),  # GeoJSON polygon as string
    zone_id: str = Query(None),  # for top_up
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Создаёт счёт в Telegram Stars. После оплаты вебхук активирует услугу."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(503, "Telegram бот не настроен")

    if purpose == "premium":
        if current_user.is_premium:
            raise HTTPException(400, "Вы уже Premium")
        stars = settings.PREMIUM_PRICE_STARS
        title = "Velo.io Premium"
        description = "Безлимитный захват территорий"
        payload = json.dumps({"u": str(current_user.id), "t": "p"})
        return _create_stars_invoice(title, description, stars, payload)

    if purpose not in {"sponsored", "top_up"}:
        raise HTTPException(400, "Неверный purpose. Допустимо: premium, sponsored, top_up")

    if not current_user.is_advertiser:
        raise HTTPException(403, "Только для рекламодателей")

    if purpose == "sponsored":
        if not business_name or not monthly_budget_stars:
            raise HTTPException(400, "Укажите business_name и monthly_budget_stars")
        stars = monthly_budget_stars
        geom = None
        if polygon:
            from geoalchemy2.shape import from_shape
            from shapely.geometry import shape as shapely_shape
            try:
                geom = from_shape(shapely_shape(json.loads(polygon)), srid=4326)
            except Exception:
                raise HTTPException(400, "Некорректный полигон")
        zone = SponsoredTerritory(
            business_name=business_name,
            monthly_budget_rub=stars * 10,
            monthly_budget_stars=stars,
            polygon=geom,
            is_active=False,
            owner_id=current_user.id,
        )
        db.add(zone)
        db.commit()
        db.refresh(zone)

        payment = AdvertiserPayment(
            user_id=current_user.id,
            sponsored_territory_id=zone.id,
            amount_stars=stars,
            purpose="create_zone",
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        payload = json.dumps({
            "p": str(payment.id),
            "t": "s",
            "z": str(zone.id),
            "s": monthly_budget_stars,
        })
        title = f"Зона {business_name[:20]}"
        description = f"Реклама Velo.io - {monthly_budget_stars} stars"
        return _create_stars_invoice(title, description, stars, payload)

    # purpose == "top_up"
    if not zone_id or not monthly_budget_stars:
        raise HTTPException(400, "Укажите zone_id и monthly_budget_stars")
    from uuid import UUID
    zone = db.query(SponsoredTerritory).filter(SponsoredTerritory.id == UUID(zone_id)).first()
    if not zone:
        raise HTTPException(404, "Зона не найдена")
    if zone.owner_id != current_user.id:
        raise HTTPException(403, "Это не ваша зона")

    stars = monthly_budget_stars
    payment = AdvertiserPayment(
        user_id=current_user.id,
        sponsored_territory_id=zone.id,
        amount_stars=stars,
        purpose="top_up",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    payload = json.dumps({
        "p": str(payment.id),
        "t": "t",
        "z": str(zone.id),
        "s": stars,
    })
    title = "Пополнение зоны"
    description = f"Добавить {stars} stars к бюджету зоны"
    return _create_stars_invoice(title, description, stars, payload)


def _create_stars_invoice(title: str, description: str, stars: int, payload: str):
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/createInvoiceLink",
            json={
                "title": title,
                "description": description,
                "payload": payload,
                "currency": "XTR",
                "prices": [{"label": title, "amount": stars}],
            },
            timeout=15,
        )
        data = r.json()
    except Exception as e:
        raise HTTPException(502, f"Ошибка Telegram API: {e}")

    if not data.get("ok"):
        raise HTTPException(502, f"Telegram API: {data.get('description', 'unknown')}")

    return {"url": data["result"]}


# ─── Premium активация (вызывается из telegram_router.webhook) ───


def activate_premium(user_id: str, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if user and not user.is_premium:
        user.is_premium = True
        db.commit()
        return True
    return False


def activate_sponsored_zone(payload: dict, db: Session):
    """Активирует или пополняет спонсорскую зону после оплаты Stars."""
    from uuid import UUID

    # поддержка новых (коротких) и старых ключей
    payment_id = payload.get("p") or payload.get("payment_id")
    zone_id = payload.get("z") or payload.get("sponsored_id")
    pay_type = payload.get("t") or payload.get("type")
    stars = (payload.get("s") or payload.get("monthly_budget_stars") or payload.get("top_up_stars") or 0)
    business_name = payload.get("b") or payload.get("business_name", "Спонсор")

    if payment_id:
        payment = db.query(AdvertiserPayment).filter(AdvertiserPayment.id == UUID(payment_id)).first()
        if payment:
            payment.status = "completed"

    zone = None
    if zone_id:
        zone = db.query(SponsoredTerritory).filter(SponsoredTerritory.id == UUID(zone_id)).first()

    if zone:
        if pay_type in ("s", "sponsored"):
            zone.monthly_budget_rub = stars * 10
            zone.monthly_budget_stars = stars
            zone.is_active = True
            if not zone.expires_at:
                from datetime import timedelta
                zone.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        elif pay_type in ("t", "top_up"):
            zone.monthly_budget_rub = (zone.monthly_budget_rub or 0) + stars * 10
            zone.monthly_budget_stars = (zone.monthly_budget_stars or 0) + stars
            zone.is_active = True
            if not zone.expires_at:
                from datetime import timedelta
                zone.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            else:
                zone.expires_at = max(zone.expires_at, datetime.now(timezone.utc)) + timedelta(days=30)
        db.commit()
        return zone

    # fallback для старых payload (без zone_id) — создать новую
    budget_rub = int(stars) * 10
    zone = SponsoredTerritory(
        business_name=business_name,
        monthly_budget_rub=budget_rub,
        is_active=True,
    )
    db.add(zone)
    db.commit()
    return zone


# ─── Выплаты ───


@router.post("/api/payment/request-payout")
def request_payout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Запрос на выплату."""
    balance = db.query(UserBalance).filter(
        UserBalance.user_id == current_user.id
    ).first()

    if not balance or balance.balance_rub < 500:
        raise HTTPException(400, "Минимальная сумма для вывода — 500₽")

    wallet = current_user.ton_wallet
    if not wallet:
        raise HTTPException(400, "Сначала укажите TON-кошелёк в профиле")

    # Проверяем, нет ли уже ожидающей выплаты
    existing = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "payout",
        Transaction.status == "pending",
    ).first()
    if existing:
        raise HTTPException(400, "У вас уже есть запрос на выплату. Дождитесь обработки.")

    amount_rub = balance.balance_rub
    tx = Transaction(
        user_id=current_user.id,
        amount_rub=-amount_rub,
        type="payout",
        description=f"Запрос выплаты {amount_rub}₽ на TON {wallet[:6]}*** — ожидает администратора",
        status="pending",
    )
    db.add(tx)
    db.commit()

    return {
        "success": True,
        "amount_rub": amount_rub,
        "status": "pending",
    }


# ─── Статус ───


@router.get("/api/payment/status")
def payment_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    is_unlimited = current_user.is_premium or settings.is_vip(current_user.email)
    if is_unlimited:
        return {
            "is_premium": is_unlimited,
            "captures_count": current_user.captures_count,
            "free_limit": FREE_LIMIT,
            "captures_remaining": -1,
        }
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_count = db.query(func.count(Territory.id)).filter(
        Territory.user_id == current_user.id,
        Territory.created_at >= week_ago,
    ).scalar() or 0
    return {
        "is_premium": False,
        "captures_count": current_user.captures_count,
        "free_limit": FREE_LIMIT,
        "captures_remaining": max(0, FREE_LIMIT - recent_count),
    }


# ─── Баланс и транзакции ───


@router.get("/api/balance")
def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    balance = db.query(UserBalance).filter(
        UserBalance.user_id == current_user.id
    ).first()
    sponsored = get_owned_sponsored(db, current_user.id)
    return {
        "balance_rub": balance.balance_rub if balance else 0,
        "total_earned_rub": balance.total_earned_rub if balance else 0,
        "sponsored_territories": sponsored,
    }


@router.get("/api/transactions")
def get_transactions(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    txns = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
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


@router.get("/api/my-sponsored")
def my_sponsored(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_owned_sponsored(db, current_user.id)


