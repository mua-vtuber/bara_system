from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.base import BaseModel


class ConversationCreate(BaseModel):
    role: str
    content: str
    platform: str


class Conversation(BaseModel):
    id: int
    timestamp: datetime
    role: str
    content: str
    platform: str
