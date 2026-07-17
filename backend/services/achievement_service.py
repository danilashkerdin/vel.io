"""Сервис ачивок: проверка условий и выдача."""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import UserAchievement, Territory, Transaction, User

logger = logging.getLogger(__name__)


def _unlock(user_id, achievement_type, db) -> bool:
    """Выдаёт ачивку, если ещё не выдана. Возвращает True если только что получил."""
    existing = db.query(UserAchievement).filter(
        UserAchievement.user_id == user_id,
        UserAchievement.achievement_type == achievement_type,
    ).first()
    if existing:
        return False
    db.add(UserAchievement(user_id=user_id, achievement_type=achievement_type))
    db.commit()
    logger.info("Achievement unlocked: user=%s type=%s", user_id, achievement_type)
    return True


def check_achievements_on_capture(db: Session, user_id, new_area: float, sponsored_rewards: list, previous_owner_id=None):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return

    # first_capture
    _unlock(user_id, "first_capture", db)

    # territories_X
    t_count = db.query(func.count(Territory.id)).filter(Territory.user_id == user_id).scalar() or 0
    for thresh, ach in [(5, "territories_5"), (10, "territories_10"), (25, "territories_25")]:
        if t_count >= thresh:
            _unlock(user_id, ach, db)

    # area_X
    total_area = db.query(func.coalesce(func.sum(Territory.area), 0)).filter(Territory.user_id == user_id).scalar() or 0
    total_area_km2 = total_area / 1_000_000
    for thresh, ach in [(1, "area_1"), (10, "area_10"), (100, "area_100")]:
        if total_area_km2 >= thresh:
            _unlock(user_id, ach, db)

    # sponsored_capture
    if sponsored_rewards:
        _unlock(user_id, "sponsored_capture", db)

    # comeback
    if previous_owner_id and str(previous_owner_id) != str(user_id):
        # проверяем, что этот пользователь раньше владел этой территорией (любой)
        prev_owned = db.query(Territory).filter(
            Territory.user_id == user_id,
            Territory.id.in_(
                db.query(Territory.id).filter(Territory.user_id == previous_owner_id)
            ),
        ).first()
        if prev_owned:
            _unlock(user_id, "comeback", db)


def check_achievements_on_premium(db: Session, user_id):
    _unlock(user_id, "premium", db)


def check_achievements_on_referral(db: Session, user_id):
    _unlock(user_id, "invite_friend", db)


def check_achievements_on_share(db: Session, user_id):
    _unlock(user_id, "first_share", db)


def get_user_achievements(db: Session, user_id) -> list:
    from models import ACHIEVEMENT_TYPES
    rows = db.query(UserAchievement).filter(
        UserAchievement.user_id == user_id
    ).order_by(UserAchievement.created_at.desc()).all()
    return [
        {
            "type": r.achievement_type,
            "title": ACHIEVEMENT_TYPES.get(r.achievement_type, r.achievement_type),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


def get_achievements_with_progress(db: Session, user_id) -> list:
    from models import ACHIEVEMENT_TYPES

    unlocked_set = set(
        db.query(UserAchievement.achievement_type).filter(
            UserAchievement.user_id == user_id
        ).all()
    )
    unlocked_set = {r[0] for r in unlocked_set}

    # current stats
    t_count = db.query(func.count(Territory.id)).filter(Territory.user_id == user_id).scalar() or 0
    total_area = db.query(func.coalesce(func.sum(Territory.area), 0)).filter(Territory.user_id == user_id).scalar() or 0
    total_area_km2 = total_area / 1_000_000

    # прогресс для типов с порогами
    progress_map = {
        "territories_5": min(t_count / 5, 1),
        "territories_10": min(t_count / 10, 1),
        "territories_25": min(t_count / 25, 1),
        "area_1": min(total_area_km2 / 1, 1),
        "area_10": min(total_area_km2 / 10, 1),
        "area_100": min(total_area_km2 / 100, 1),
    }
    progress_labels = {
        "territories_5": f"{t_count}/5",
        "territories_10": f"{t_count}/10",
        "territories_25": f"{t_count}/25",
        "area_1": f"{total_area_km2:.1f}/1 км²",
        "area_10": f"{total_area_km2:.1f}/10 км²",
        "area_100": f"{total_area_km2:.1f}/100 км²",
    }

    unlocked_types = [r[0] for r in db.query(UserAchievement.achievement_type).filter(
        UserAchievement.user_id == user_id
    ).all()]

    result = []
    for ach_type, title in ACHIEVEMENT_TYPES.items():
        is_unlocked = ach_type in unlocked_set
        progress = progress_map.get(ach_type)
        label = progress_labels.get(ach_type)
        result.append({
            "type": ach_type,
            "title": title,
            "unlocked": is_unlocked,
            "progress": round(progress, 2) if progress is not None else (1 if is_unlocked else 0),
            "progress_label": label or ("✓" if is_unlocked else "—"),
        })
    return result