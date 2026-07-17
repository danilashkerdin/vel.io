from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import mapping

from models import Territory, User, Notification


def _active_territories():
    return (Territory.expires_at.is_(None)) | (Territory.expires_at > datetime.now(timezone.utc))


class TerritoryFullyOccupiedError(Exception):
    pass


def subtract_occupied(db: Session, new_geom, user_id):
    """Вычитает чужие активные территории из новой. Один запрос через CTE."""
    occupied_cte = (
        db.query(func.ST_Union(Territory.polygon).label("occupied"))
        .filter(
            Territory.user_id != user_id,
            _active_territories(),
            func.ST_Intersects(Territory.polygon, new_geom),
        )
        .cte("occupied_cte")
    )

    # Всё в одном запросе: diff + emptiness + area
    result = db.query(
        func.ST_Difference(new_geom, occupied_cte.c.occupied).label("diff"),
        func.ST_IsEmpty(func.ST_Difference(new_geom, occupied_cte.c.occupied)).label("is_empty"),
        func.ST_Area(func.ST_Transform(
            func.ST_Difference(new_geom, occupied_cte.c.occupied), 3857
        )).label("area"),
    ).first()

    if result is None or result.diff is None:
        # Нет пересечений — возвращаем исходную геометрию
        return new_geom, None

    if result.is_empty:
        raise TerritoryFullyOccupiedError()

    return result.diff, result.area or 0


def create_nearby_notifications(db: Session, territory_id, new_geom, current_user):
    """Создаёт уведомления для пользователей рядом с новой территорией."""
    nearby_users = (
        db.query(Territory.user_id, User.username)
        .join(User, Territory.user_id == User.id)
        .filter(
            Territory.user_id != current_user.id,
            _active_territories(),
            func.ST_DWithin(
                Territory.polygon,
                new_geom,
                0.005,  # примерно 500м в градусах
            ),
        )
        .distinct()
        .all()
    )

    for uid, username in nearby_users:
        notif = Notification(
            user_id=uid,
            type="nearby",
            message=f"🚴 {current_user.username} захватил территорию рядом с вами!",
            territory_id=territory_id,
        )
        db.add(notif)


def get_territories_in_bbox(db: Session, north: float, south: float, east: float, west: float, limit: int = 100, offset: int = 0):
    """Возвращает территории в bounding box. Использует ST_MakeEnvelope вместо строковой сборки."""
    envelope = func.ST_MakeEnvelope(west, south, east, north, 4326)

    territories = (
        db.query(Territory, User.username)
        .join(User, Territory.user_id == User.id, isouter=True)
        .filter(
            _active_territories(),
            func.ST_Intersects(Territory.polygon, envelope),
        )
        .order_by(Territory.created_at.asc())
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
            "image_url": t.image_url,
            "description": t.description,
            "link_url": t.link_url,
            "polygon": mapping(to_shape(t.polygon)),
            "created_at": t.created_at.isoformat(),
            "expires_at": t.expires_at.isoformat() if t.expires_at else None,
            "user_id": str(t.user_id) if t.user_id else None,
            "username": username or "Неизвестный",
        }
        for t, username in territories
    ]


def format_territory_response(territory, current_user):
    """Форматирует территорию для ответа API."""
    return {
        "id": str(territory.id),
        "name": territory.name,
        "area": territory.area,
        "closures_found": territory.closures_count,
        "parts_count": territory.parts_count,
        "polygon": mapping(to_shape(territory.polygon)),
        "created_at": territory.created_at.isoformat(),
        "expires_at": territory.expires_at.isoformat() if territory.expires_at else None,
        "user": {
            "id": str(current_user.id),
            "username": current_user.username,
        },
    }


def get_public_territory(db: Session, territory_id: str):
    """Возвращает публичную информацию о территории. Один запрос с joinedload."""
    result = (
        db.query(Territory, User.username)
        .join(User, Territory.user_id == User.id, isouter=True)
        .filter(Territory.id == territory_id)
        .first()
    )

    if not result:
        raise HTTPException(404, "Территория не найдена")

    t, username = result
    return {
        "id": str(t.id),
        "name": t.name,
        "area": t.area,
        "color": t.color,
        "image_url": t.image_url,
        "description": t.description,
        "link_url": t.link_url,
        "polygon": mapping(to_shape(t.polygon)),
        "created_at": t.created_at.isoformat(),
        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        "username": username or "Неизвестный",
    }


def get_my_territories(db: Session, current_user, limit: int = 100, offset: int = 0):
    """Возвращает список территорий пользователя с пагинацией."""
    territories = (
        db.query(Territory)
        .filter(Territory.user_id == current_user.id)
        .order_by(Territory.created_at.desc())
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
            "created_at": t.created_at.isoformat(),
            "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        }
        for t in territories
    ]


def update_territory(db: Session, territory_id: str, data, current_user):
    """Обновляет территорию."""
    t = db.query(Territory).filter(Territory.id == territory_id).first()
    if not t:
        raise HTTPException(404, "Территория не найдена")
    if str(t.user_id) != str(current_user.id):
        raise HTTPException(403, "Это не ваша территория")

    if data.name is not None:
        t.name = data.name
    if data.color is not None:
        t.color = data.color
    if data.image_url is not None:
        t.image_url = data.image_url
    if data.description is not None:
        t.description = data.description
    if data.link_url is not None:
        t.link_url = data.link_url

    db.commit()
    db.refresh(t)

    return {
        "id": str(t.id),
        "name": t.name,
        "color": t.color,
        "image_url": t.image_url,
        "description": t.description,
        "link_url": t.link_url,
        "area": t.area,
        "polygon": mapping(to_shape(t.polygon)),
    }


def delete_territory(db: Session, territory_id: str, current_user):
    """Удаляет территорию."""
    t = db.query(Territory).filter(Territory.id == territory_id).first()
    if not t:
        raise HTTPException(404, "Территория не найдена")
    if str(t.user_id) != str(current_user.id):
        raise HTTPException(403, "Это не ваша территория")
    db.delete(t)
    db.commit()
    return {"status": "deleted"}
