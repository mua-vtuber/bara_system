from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.base import BaseModel


class PlatformPost(BaseModel):
    platform: str
    post_id: str
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    community: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[datetime] = None
    score: int = 0
    comment_count: int = 0


class PlatformComment(BaseModel):
    platform: str
    comment_id: str
    post_id: str
    content: Optional[str] = None
    author: Optional[str] = None
    parent_comment_id: Optional[str] = None
    created_at: Optional[datetime] = None


class PlatformNotification(BaseModel):
    platform: str
    notification_id: str
    notification_type: str
    actor_name: Optional[str] = None
    post_id: Optional[str] = None
    post_title: Optional[str] = None
    comment_id: Optional[str] = None
    content_preview: Optional[str] = None
    is_read: bool = False
    created_at: Optional[datetime] = None


class PlatformCommunity(BaseModel):
    platform: str
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None


class PlatformPostResult(BaseModel):
    success: bool
    post_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None


class PlatformCommentResult(BaseModel):
    success: bool
    comment_id: Optional[str] = None
    error: Optional[str] = None


class RegistrationResult(BaseModel):
    success: bool
    claim_url: Optional[str] = None
    verification_code: Optional[str] = None
    api_key: Optional[str] = None
    error: Optional[str] = None


class RateLimitConfig(BaseModel):
    post_cooldown_seconds: int = 0
    comment_cooldown_seconds: int = 0
    api_calls_per_minute: int = 60
    comments_per_day: int = 100


class AcquireResult(BaseModel):
    allowed: bool
    wait_seconds: float = 0.0
