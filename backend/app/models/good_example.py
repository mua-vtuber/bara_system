from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.base import BaseModel


class GoodExampleCreate(BaseModel):
    """Data needed to create a good example entry."""

    platform: str
    action_type: str = "comment"
    context_title: str = ""
    context_content: str = ""
    bot_response: str
    engagement_score: float = 0.0
    reply_count: int = 0
    upvote_count: int = 0
    activity_id: Optional[int] = None
    post_id: str = ""
    embedding: Optional[bytes] = None


class GoodExample(BaseModel):
    """Full good example record from the database."""

    id: int
    created_at: datetime
    platform: str
    action_type: str = "comment"
    context_title: str = ""
    context_content: str = ""
    bot_response: str
    engagement_score: float = 0.0
    reply_count: int = 0
    upvote_count: int = 0
    activity_id: Optional[int] = None
    post_id: str = ""
    embedding: Optional[bytes] = None
