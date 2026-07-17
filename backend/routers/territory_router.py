import asyncio
import hashlib
import time
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import mapping

from database import get_db
from models import User, Territory, GpxHash
from auth import get_current_user
from config import settings
from pipeline import TerritoryPipeline
from schemas.territory import TerritoryUpdateRequest
from services.territory_service import (
    TerritoryFullyOccupiedError,
    subtract_occupied,
    create_nearby_notifications,
    get_territories_in_bbox,
    get_my_territories,
    format_territory_response,
    get_public_territory,
    update_territory,
    delete_territory,
)
from services.sponsored_service import process_capture_rewards, get_sponsored_in_bbox
from limiter import limiter

router = APIRouter(tags=["territories"])

pipeline = TerritoryPipeline()

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
FREE_LIMIT = settings.FREE_CAPTURES_LIMIT
TERRITORY_TTL_DAYS = 14


from pydantic import BaseModel


class CaptureRideRequest(BaseModel):
    points: list[list[float]]


def _get_using_bonus(current_user, db) -> bool:
    if current_user.is_premium or settings.is_vip(current_user.email):
        return False
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_count = db.query(func.count(Territory.id)).filter(
        Territory.user_id == current_user.id,
        Territory.created_at >= week_ago,
    ).scalar() or 0
    if recent_count >= FREE_LIMIT:
        if (current_user.referral_bonuses or 0) > 0:
            return True
        raise HTTPException(
            402,
            "Бесплатный лимит: 1 захват в неделю. "
            "Оформите Premium для безлимитных захватов. "
            "Приводите друзей — получайте бонусные захваты!",
        )
    return False

# Leaderboard cache (30s TTL)
_leaderboard_cache = {"data": None, "ts": 0}
LEADERBOARD_TTL = 30


def _save_and_return(
    result, db, current_user, name, using_bonus, sha256=None,
):
    new_geom = from_shape(result["geometry"], srid=4326)

    try:
        new_geom, area = subtract_occupied(db, new_geom, current_user.id)
    except TerritoryFullyOccupiedError:
        raise HTTPException(400, "Вся территория уже занята другими пользователями")

    if area is not None:
        result["area_sqm"] = area

    territory = Territory(
        user_id=current_user.id,
        name=name,
        polygon=new_geom,
        area=result["area_sqm"],
        closures_count=result["closures_found"],
        parts_count=result["parts_count"],
        expires_at=datetime.now(timezone.utc) + timedelta(days=14),
    )

    db.add(territory)
    db.flush()

    current_user.captures_count = User.captures_count + 1
    db.add(current_user)
    db.commit()
    db.refresh(territory)

    create_nearby_notifications(db, territory.id, new_geom, current_user)

    sponsored_rewards = process_capture_rewards(db, new_geom, current_user)

    if using_bonus:
        current_user.referral_bonuses = (current_user.referral_bonuses or 1) - 1
        db.add(current_user)

    if sha256:
        db.execute(
            text("""
                INSERT INTO gpx_hashes (sha256, user_id, territory_id)
                VALUES (:sha256, :user_id, :territory_id)
                ON CONFLICT (sha256) DO NOTHING
            """),
            {"sha256": sha256, "user_id": current_user.id, "territory_id": territory.id},
        )
    db.commit()

    response = format_territory_response(territory, current_user)
    if sponsored_rewards:
        response["sponsored_rewards"] = sponsored_rewards
    return response


@router.post("/api/capture-ride")
@limiter.limit("10/minute")
async def capture_ride(
    request: Request,
    body: CaptureRideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if len(body.points) < 5:
        raise HTTPException(400, "Слишком мало точек. Нужно минимум 5.")

    using_bonus = _get_using_bonus(current_user, db)

    pts = [(p[0], p[1], p[2] if len(p) > 2 else 0) for p in body.points]
    result = await asyncio.to_thread(pipeline.process_raw_points, pts)

    if not result["success"]:
        if result["error"] == "too_few_points":
            raise HTTPException(400, "Слишком мало точек. Минимум 5.")
        elif result["error"] == "no_closures":
            raise HTTPException(400, "Маршрут не замкнут. Вернитесь к начальной точке.")
        else:
            raise HTTPException(400, "Не удалось обработать маршрут")

    return _save_and_return(result, db, current_user, "Поездка", using_bonus)


@router.post("/api/upload-gpx")
@limiter.limit("10/minute")
async def upload_gpx(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".gpx"):
        raise HTTPException(400, "Поддерживаются только .gpx файлы")

    content = await file.read()

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "Файл слишком большой. Максимум 10MB.")

    try:
        gpx_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "Невалидный GPX файл")

    sha256 = hashlib.sha256(content).hexdigest()

    using_bonus = _get_using_bonus(current_user, db)

    existing = db.query(GpxHash).filter(
        GpxHash.sha256 == sha256,
        GpxHash.user_id != current_user.id,
    ).first()
    if existing:
        raise HTTPException(400, "Этот GPX-файл уже использован другим пользователем")

    del content

    result = await asyncio.to_thread(pipeline.process_gpx_string, gpx_str)
    del gpx_str

    if not result["success"]:
        if result["error"] == "too_few_points":
            raise HTTPException(400, "Слишком мало точек. Минимум 5.")
        elif result["error"] == "no_closures":
            raise HTTPException(400, "Замкнутых контуров не найдено. Вернитесь к начальной точке маршрута.")
        elif result["error"] == "validation":
            raise HTTPException(400, result["detail"])
        else:
            raise HTTPException(400, "Не удалось обработать маршрут")

    return _save_and_return(
        result, db, current_user,
        file.filename.replace(".gpx", ""),
        using_bonus, sha256,
    )


@router.get("/api/leaderboard")
def leaderboard(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    period: str = Query("all", regex="^(week|month|all)$"),
    sort: str = Query("area", regex="^(area|count)$"),
    db: Session = Depends(get_db),
):
    now = time.time()
    cache_key = f"{period}_{sort}_{limit}_{offset}"
    if _leaderboard_cache["data"] is not None and _leaderboard_cache["ts"] == cache_key and now - _leaderboard_cache["ts"] < LEADERBOARD_TTL:
        return _leaderboard_cache["data"]
    from services.territory_service import _active_territories

    filters = [_active_territories()]
    if period == "week":
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        filters.append(Territory.created_at >= week_ago)
    elif period == "month":
        month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        filters.append(Territory.created_at >= month_ago)

    order = func.sum(Territory.area).desc() if sort == "area" else func.count(Territory.id).desc()

    results = (
        db.query(
            User.username,
            func.sum(Territory.area).label("total_area"),
            func.count(Territory.id).label("count"),
        )
        .join(Territory, Territory.user_id == User.id)
        .filter(*filters)
        .group_by(User.id, User.username)
        .order_by(order)
        .offset(offset)
        .limit(limit)
        .all()
    )

    data = [
        {
            "username": r.username,
            "total_area": float(r.total_area or 0),
            "territories_count": r.count,
        }
        for r in results
    ]

    _leaderboard_cache["data"] = data
    _leaderboard_cache["ts"] = now
    return data


@router.get("/api/activity")
def get_activity(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    from services.territory_service import _active_territories
    results = (
        db.query(Territory, User.username)
        .join(User, Territory.user_id == User.id, isouter=True)
        .filter(_active_territories())
        .order_by(Territory.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(t.id),
            "user_id": str(t.user_id),
            "name": t.name,
            "area": t.area,
            "username": username or "Неизвестный",
            "created_at": t.created_at.isoformat(),
            "polygon": mapping(to_shape(t.polygon)),
        }
        for t, username in results
    ]


@router.get("/api/users/{user_id}/territories")
def get_user_territories(
    user_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    from services.territory_service import _active_territories
    results = (
        db.query(Territory, User.username)
        .join(User, Territory.user_id == User.id, isouter=True)
        .filter(
            Territory.user_id == user_id,
            _active_territories(),
        )
        .order_by(Territory.area.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "area": t.area,
            "color": t.color,
            "polygon": mapping(to_shape(t.polygon)),
            "created_at": t.created_at.isoformat(),
            "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        }
        for t, _ in results
    ]


@router.get("/api/territories/public/{territory_id}")
def get_public_territory_endpoint(territory_id: str, db: Session = Depends(get_db)):
    return get_public_territory(db, territory_id)


@router.get("/api/territories")
def get_territories(
    north: float = Query(90),
    south: float = Query(-90),
    east: float = Query(180),
    west: float = Query(-180),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return get_territories_in_bbox(db, north, south, east, west, limit, offset)


@router.get("/api/sponsored-territories")
def list_sponsored_public(
    north: float = Query(90),
    south: float = Query(-90),
    east: float = Query(180),
    west: float = Query(-180),
    db: Session = Depends(get_db),
):
    return get_sponsored_in_bbox(db, north, south, east, west)


@router.patch("/api/territories/{territory_id}")
def update_territory_endpoint(
    territory_id: str,
    data: TerritoryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_territory(db, territory_id, data, current_user)


@router.delete("/api/territories/{territory_id}")
def delete_territory_endpoint(
    territory_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return delete_territory(db, territory_id, current_user)


@router.get("/api/my-territories")
def my_territories(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_my_territories(db, current_user, limit, offset)


@router.get("/api/initial-view")
def initial_view(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Возвращает центр и зум для начального вида карты.
    Использует SQL-функции вместо загрузки всего полигона.
    """
    result = (
        db.query(
            func.ST_Y(func.ST_Centroid(Territory.polygon)).label("lat"),
            func.ST_X(func.ST_Centroid(Territory.polygon)).label("lon"),
            func.ST_YMin(Territory.polygon).label("south"),
            func.ST_XMin(Territory.polygon).label("west"),
            func.ST_YMax(Territory.polygon).label("north"),
            func.ST_XMax(Territory.polygon).label("east"),
        )
        .filter(Territory.user_id == current_user.id)
        .order_by(Territory.created_at.desc())
        .first()
    )

    if result:
        return {
            "lat": result.lat,
            "lon": result.lon,
            "zoom": 14,
            "bounds": {
                "south": result.south,
                "west": result.west,
                "north": result.north,
                "east": result.east,
            },
        }

    return {"lat": 55.751244, "lon": 37.618423, "zoom": 12}
