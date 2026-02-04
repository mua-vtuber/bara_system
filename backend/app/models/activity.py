from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.core.constants import ActivityStatus, ActivityType, Platform
from app.models.base import BaseModel


class ActivityCreate(BaseModel):
    type: ActivityType
    platform: Platform
    platform_post_id: Optional[str] = None
    platform_comment_id: Optional[str] = None
    parent_id: Optional[str] = None
    url: Optional[str] = None
    original_content: Optional[str] = None
    bot_response: Optional[str] = None
    translated_content: Optional[str] = None
    translation_direction: Optional[str] = None
    llm_prompt: Optional[str] = None
    status: ActivityStatus = ActivityStatus.PENDING


class Activity(BaseModel):
    id: int
    timestamp: datetime
    type: ActivityType
    platform: Platform
    platform_post_id: Optional[str] = None
    platform_comment_id: Optional[str] = None
    parent_id: Optional[str] = None
    url: Optional[str] = None
    original_content: Optional[str] = None
    bot_response: Optional[str] = None
    translated_content: Optional[str] = None
    translation_direction: Optional[str] = None
    llm_prompt: Optional[str] = None
    status: ActivityStatus = ActivityStatus.PENDING
    error_message: Optional[str] = None


class DailyCounts(BaseModel):
    comments: int = 0
    posts: int = 0
    upvotes: int = 0
    downvotes: int = 0
    follows: int = 0


class DailyLimits(BaseModel):
    max_comments: int = 20
    max_posts: int = 3
    max_upvotes: int = 30
