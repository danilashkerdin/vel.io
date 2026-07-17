import hashlib
import hmac
import json
import logging
from typing import Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import User, Territory
from auth import get_current_user, create_access_token
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telegram"])

BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN


def _send_telegram(chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
    if not BOT_TOKEN:
        return
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json=payload, timeout=10,
        )
        if not r.is_success:
            logger.error("Telegram send error: %s %s", r.status_code, r.text)
    except Exception as e:
        logger.error("Telegram send exception: %s", e)


def _get_telegram_id(user: User) -> Optional[int]:
    if user.email and user.email.startswith("tg_"):
        try:
            return int(user.email.split("@")[0].split("_")[1])
        except (IndexError, ValueError):
            return None
    return None


def _make_deep_link() -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}"


def notify_recapture(db: Session, territory_name: str, old_owner: User, new_owner: User) -> None:
    tg_id = _get_telegram_id(old_owner)
    if not tg_id:
        return
    _send_telegram(
        tg_id,
        f"⚠️ *Территория захвачена!*\n\n"
        f"📍 *{territory_name}*\n"
        f"👤 Перехвачена пользователем *{new_owner.username}*\n\n"
        f"Верни её — прокатись по тому же маршруту! 🚴",
        {"inline_keyboard": [[
            {"text": "🗺 Открыть карту", "web_app": {"url": _make_deep_link()}}
        ]]},
    )


@router.post("/api/telegram/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    if not BOT_TOKEN:
        raise HTTPException(503, "Telegram bot not configured")

    # Verify X-Telegram-Bot-Api-Secret-Token
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    expected = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]
    if not secret_token or secret_token != expected:
        raise HTTPException(403, "Invalid webhook secret")

    body = await request.json()
    logger.info("Telegram update: %s", json.dumps(body, ensure_ascii=False)[:300])

    # Telegram Stars — pre_checkout_query (обязательно ответить, иначе платёж упадёт)
    pre_checkout = body.get("pre_checkout_query")
    if pre_checkout:
        query_id = pre_checkout.get("id")
        if query_id:
            try:
                r = await httpx.AsyncClient().post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/answerPreCheckoutQuery",
                    json={"pre_checkout_query_id": query_id, "ok": True},
                    timeout=10,
                )
                logger.info("answerPreCheckoutQuery: %s", r.json())
            except Exception as e:
                logger.error("answerPreCheckoutQuery error: %s", e)
        return {"ok": True}

    message = body.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if not chat_id:
        return {"ok": True}

    # Telegram Stars — успешная оплата
    successful_payment = message.get("successful_payment")
    if successful_payment:
        payload_str = successful_payment.get("invoice_payload", "")
        try:
            payload = json.loads(payload_str)
        except (json.JSONDecodeError, TypeError):
            payload = {}
        # поддержка новых (коротких) и старых ключей
        pay_type = payload.get("t") or payload.get("type")
        user_id = payload.get("u") or payload.get("user_id")

        if user_id:
            if pay_type in ("p", "premium"):
                from routers.payment_router import activate_premium
                if activate_premium(user_id, db):
                    logger.info("Premium activated for user %s via Stars", user_id)
                    _send_telegram(chat_id, "⭐ *Premium активирован!*\n\nТебе доступен безлимитный захват территорий! 🚴")

        if pay_type in ("s", "sponsored", "t", "top_up"):
            from routers.payment_router import activate_sponsored_zone
            zone = activate_sponsored_zone(payload, db)
            top_up_stars = payload.get("s") or payload.get("top_up_stars", 0)
            if pay_type in ("t", "top_up"):
                logger.info("Sponsored zone %s topped up via Stars", zone.id)
                _send_telegram(chat_id, f"📈 *Бюджет зоны пополнен!*\n\n«{zone.business_name}» получила +{top_up_stars} ⭐")
            else:
                logger.info("Sponsored zone %s created via Stars", zone.id)
                _send_telegram(chat_id, f"🏪 *Спонсорская зона создана!*\n\n«{zone.business_name}» активна на карте 🗺")

        return {"ok": True}

    if text.startswith("/start"):
        args = text.replace("/start", "").strip()
        ref_user_id = None
        if args.startswith("ref_"):
            ref_user_id = args[4:]

        user = db.query(User).filter(User.email == f"tg_{chat_id}@telegram").first()
        is_new = False

        if not user:
            is_new = True
            user = User(
                email=f"tg_{chat_id}@telegram",
                username=f"TG_{chat_id}",
                hashed_password="",
            )
            db.add(user)
            db.flush()

        user.telegram_chat_id = str(chat_id)

        if ref_user_id:
            try:
                ref_uuid = UUID(ref_user_id)
                referrer = db.query(User).filter(User.id == ref_uuid).first()
                if referrer and referrer.id != user.id:
                    user.referred_by = referrer.id
                    referrer.referral_bonuses = (referrer.referral_bonuses or 0) + 1
            except Exception:
                pass

        db.commit()
        db.refresh(user)

        token = create_access_token({"sub": str(user.id)})
        deep_link = f"{_make_deep_link()}/?token={token}"

        _send_telegram(
            chat_id,
            "🚴 *Добро пожаловать в Velo.io!*\n\n"
            "Захватывай территории, зарабатывай на спонсорских зонах, "
            "соревнуйся с друзьями.\n\n"
            "👇 *Нажми, чтобы открыть карту:*",
            {"inline_keyboard": [[
                {"text": "🚴 Открыть Velo.io", "web_app": {"url": deep_link}}
            ]]},
        )

        if ref_user_id and is_new:
            _send_telegram(chat_id, "🎉 *Бонус!* Пригласивший получил +1 захват за тебя!")

        return {"ok": True}

    elif text == "/my":
        user = db.query(User).filter(User.email == f"tg_{chat_id}@telegram").first()
        if not user:
            _send_telegram(chat_id, "❌ Ты ещё не заходил в Velo.io. Нажми /start")
            return {"ok": True}

        total_area = db.query(func.sum(Territory.area)).filter(Territory.user_id == user.id).scalar() or 0
        count = db.query(func.count(Territory.id)).filter(Territory.user_id == user.id).scalar() or 0
        deep_link = f"{_make_deep_link()}/?token={create_access_token({'sub': str(user.id)})}"

        _send_telegram(
            chat_id,
            f"📋 *Твои территории*\n\n"
            f"📌 Захвачено: *{count}*\n"
            f"📐 Площадь: *{total_area / 1_000_000:.2f} км²*\n"
            f"⭐ Premium: {'✅' if user.is_premium else '❌'}\n\n"
            f"👇 Открой карту:",
            {"inline_keyboard": [[
                {"text": "🗺 Открыть карту", "web_app": {"url": deep_link}}
            ]]},
        )

    elif text == "/top":
        results = (
            db.query(User.username, func.sum(Territory.area).label("total_area"), func.count(Territory.id).label("count"))
            .join(Territory, Territory.user_id == User.id)
            .group_by(User.id, User.username)
            .order_by(func.sum(Territory.area).desc())
            .limit(10)
            .all()
        )
        lines = ["🏆 *Топ велосипедистов*\n"]
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for i, r in enumerate(results, 1):
            prefix = medals.get(i, f"{i}.")
            area_km2 = (r.total_area or 0) / 1_000_000
            lines.append(f"{prefix} *{r.username}* — {area_km2:.2f} км² ({r.count} тер.)")
        _send_telegram(chat_id, "\n".join(lines))

    else:
        _send_telegram(
            chat_id,
            "🤖 *Команды:*\n"
            "/start — начать\n"
            "/my — мои территории\n"
            "/top — топ велосипедистов",
        )

    return {"ok": True}


@router.get("/api/referral/link")
def get_referral_link(current_user: User = Depends(get_current_user)):
    ref_param = str(current_user.id)
    frontend = settings.FRONTEND_URL.rstrip("/")
    return {
        "link": f"{frontend}/?ref={ref_param}",
        "telegram_link": f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start=ref_{ref_param}" if BOT_TOKEN and settings.TELEGRAM_BOT_USERNAME else None,
    }


@router.get("/api/telegram/set-webhook")
async def set_telegram_webhook_get(request: Request):
    return await _do_set_webhook(request)

@router.post("/api/telegram/set-webhook")
async def set_telegram_webhook_post(request: Request):
    return await _do_set_webhook(request)

async def _do_set_webhook(request: Request):
    """Register Telegram webhook (call once after deploy)."""
    if not BOT_TOKEN:
        raise HTTPException(503, "Telegram bot not configured")
    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/telegram/webhook"
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            json={"url": webhook_url},
            timeout=15,
        )
        data = r.json()
        if not data.get("ok"):
            raise HTTPException(400, f"Telegram error: {data.get('description', 'unknown')}")
        return {"status": "ok", "webhook_url": webhook_url, "result": data}


@router.get("/api/referral/bonuses")
def get_referral_bonuses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = db.query(func.count(User.id)).filter(User.referred_by == current_user.id).scalar() or 0
    return {
        "referrals_count": count,
        "bonus_captures": current_user.referral_bonuses or 0,
    }
