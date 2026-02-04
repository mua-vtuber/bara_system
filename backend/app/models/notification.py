from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.base import BaseModel


class NotificationCreate(BaseModel):
    platform: str
    notification_id: str
    notification_type: str
    actor_name: Optional[str] = None
    post_id: Optional[str] = None
    is_read: bool = False


class NotificationLog(BaseModel):
    id: int
    timestamp: datetime
    platform: str
    notification_id: str
    notification_type: str
    actor_name: Optional[str] = None
    post_id: Optional[str] = None
    is_read: bool = False
    response_activity_id: Optional[int] = None
