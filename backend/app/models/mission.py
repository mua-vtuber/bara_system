from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from app.models.base import BaseModel


class MissionStatus(str, Enum):
    PENDING = "pending"
    WARMUP = "warmup"
    ACTIVE = "active"
    POSTED = "posted"
    COLLECTING = "collecting"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class MissionCreate(BaseModel):
    """Data needed to create a new mission."""

    topic: str
    question_hint: str = ""
    urgency: str = "normal"
    target_platform: str = ""
    target_community: str = ""
    user_notes: str = ""


class Mission(BaseModel):
    """Full mission record from the database."""

    id: int
    created_at: datetime
    topic: str
    question_hint: str = ""
    urgency: str = "normal"
    status: str = "pending"
    target_platform: str = ""
    target_community: str = ""
    warmup_count: int = 0
    warmup_target: int = 3
    post_id: str = ""
    post_platform: str = ""
    collected_responses: list[dict] = []
    summary: str = ""
    completed_at: Optional[datetime] = None
    user_notes: str = ""
