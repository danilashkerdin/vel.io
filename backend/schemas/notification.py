from pydantic import BaseModel
from typing import List


class NotificationItem(BaseModel):
    id: str
    type: str
    message: str
    read: bool
    created_at: str


class NotificationsResponse(BaseModel):
    unread: int
    items: List[NotificationItem]
