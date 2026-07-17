from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Notification


def get_user_notifications(db: Session, user_id, limit: int = 50, offset: int = 0):
    """Возвращает уведомления пользователя. Unread count через SQL, не Python."""
    unread = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user_id, Notification.read == False)
        .scalar()
    )

    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "unread": unread,
        "items": [
            {
                "id": str(n.id),
                "type": n.type,
                "message": n.message,
                "read": n.read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
    }


def mark_all_read(db: Session, user_id):
    """Помечает все уведомления как прочитанные."""
    db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.read == False,
    ).update({"read": True})
    db.commit()
    return {"status": "ok"}
