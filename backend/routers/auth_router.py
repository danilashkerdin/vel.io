import asyncio
import hashlib
import hmac
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models import User, AdvertiserProfile
from auth import hash_password, verify_password_async, create_access_token, get_current_user
from schemas.auth import RegisterRequest, LoginRequest
from schemas.payment import ProfileUpdateRequest
from config import settings
from limiter import limiter
from services.achievement_service import check_achievements_on_referral

router = APIRouter(prefix="/api/auth", tags=["auth"])

FREE_LIMIT = settings.FREE_CAPTURES_LIMIT


def _user_response(user: User, token: str | None = None):
    unlimited = user.is_premium or settings.is_vip(user.email)
    effective_limit = FREE_LIMIT + (user.referral_bonuses or 0)
    d = {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "is_premium": unlimited,
        "captures_count": user.captures_count,
        "free_limit": effective_limit,
        "captures_remaining": -1 if unlimited else None,
        "ton_wallet": user.ton_wallet,
        "is_advertiser": user.is_advertiser or False,
        "referral_bonuses": user.referral_bonuses or 0,
    }
    if token:
        d["token"] = token
    return d


@router.post("/register")
@limiter.limit("5/minute")
async def register(request: Request, data: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(400, "Email уже занят")

    hashed = await asyncio.to_thread(hash_password, data.password)
    user = User(
        email=data.email,
        username=data.username,
        hashed_password=hashed,
        is_advertiser=data.is_advertiser,
    )

    # Реферальная система: X-Referral-ID = UUID пригласившего
    ref_id = request.headers.get("X-Referral-ID")
    if ref_id:
        try:
            ref_uuid = UUID(ref_id)
            referrer = db.query(User).filter(User.id == ref_uuid).first()
            if referrer and referrer.id != user.id:
                user.referred_by = referrer.id
                referrer.referral_bonuses = (referrer.referral_bonuses or 0) + 1
                db.add(referrer)
                db.commit()
                check_achievements_on_referral(db, referrer.id)
        except Exception:
            pass

    db.add(user)
    db.commit()
    db.refresh(user)

    if data.is_advertiser:
        profile = AdvertiserProfile(user_id=user.id)
        db.add(profile)
        db.commit()

    # Первые N пользователей получают premium бесплатно
    total_users = db.query(User).count()
    if total_users <= settings.FREE_PREMIUM_SLOTS:
        user.is_premium = True
        db.commit()
        db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return _user_response(user, token)


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not await verify_password_async(data.password, user.hashed_password):
        raise HTTPException(401, "Неверный email или пароль")

    token = create_access_token({"sub": str(user.id)})
    return _user_response(user, token)


@router.post("/telegram")
@limiter.limit("10/minute")
async def telegram_auth(request: Request, db: Session = Depends(get_db)):
    """Login via Telegram Mini App init data. No password needed."""
    body = await request.json()
    init_data = body.get("init_data", "")
    if not init_data:
        raise HTTPException(400, "Missing init_data")

    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(503, "Telegram bot not configured")

    # Validate init data
    try:
        parsed = dict(pair.split("=", 1) for pair in init_data.split("&"))
        hash_check = parsed.pop("hash", "")
        items = sorted(f"{k}={v}" for k, v in parsed.items())
        data_check = "\n".join(items)
        secret = hashlib.sha256(settings.TELEGRAM_BOT_TOKEN.encode()).digest()
        computed = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if computed != hash_check:
            raise HTTPException(401, "Invalid Telegram auth")
    except Exception:
        raise HTTPException(400, "Invalid init_data format")

    # Extract user from init data
    user_data = parsed.get("user", "{}")
    try:
        tg_user = json.loads(user_data)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid user data")

    tg_id = tg_user.get("id")
    if not tg_id:
        raise HTTPException(400, "No telegram_id")

    tg_username = tg_user.get("username") or tg_user.get("first_name") or f"TG_{tg_id}"
    tg_email = f"tg_{tg_id}@telegram"

    user = db.query(User).filter(User.email == tg_email).first()
    if not user:
        user = User(
            email=tg_email,
            username=tg_username,
            hashed_password="",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        total_users = db.query(User).count()
        if total_users <= settings.FREE_PREMIUM_SLOTS:
            user.is_premium = True
            db.commit()
            db.refresh(user)

    user.telegram_chat_id = str(tg_id)
    db.commit()

    token = create_access_token({"sub": str(user.id)})
    return _user_response(user, token)


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return _user_response(current_user)


@router.put("/profile")
def update_profile(
    data: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.username is not None:
        current_user.username = data.username
    if data.ton_wallet is not None:
        current_user.ton_wallet = data.ton_wallet
    db.commit()
    return _user_response(current_user)



