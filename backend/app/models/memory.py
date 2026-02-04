from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.base import BaseModel


class BotMemoryCreate(BaseModel):
    """Data needed to create or update a bot memory entry."""

    platform: str
    entity_name: str
    entity_type: str = "bot"
    topics: list[str] = []
    relationship_notes: str = ""


class BotMemory(BaseModel):
    """Full bot memory record from the database."""

    id: int
    platform: str
    entity_name: str
    entity_type: str = "bot"
    first_seen_at: datetime
    last_interaction_at: datetime
    interaction_count: int = 0
    topics: list[str] = []
    relationship_notes: str = ""
    sentiment: str = "neutral"
    embedding: Optional[bytes] = None
