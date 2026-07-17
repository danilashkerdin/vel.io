from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User
from auth import get_current_user
from services.notification_service import get_user_notifications, mark_all_read

router = APIRouter(tags=["notifications"])


@router.get("/api/notifications")
def get_notifications(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_user_notifications(db, current_user.id, limit=limit, offset=offset)


@router.post("/api/notifications/read-all")
def read_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return mark_all_read(db, current_user.id)
