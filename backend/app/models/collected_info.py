from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.base import BaseModel


class CollectedInfoCreate(BaseModel):
    platform: str
    author: Optional[str] = None
    category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    source_url: Optional[str] = None
    tags: Optional[str] = None


class CollectedInfo(BaseModel):
    id: int
    timestamp: datetime
    platform: str
    author: Optional[str] = None
    category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    source_url: Optional[str] = None
    bookmarked: bool = False
    tags: Optional[str] = None
