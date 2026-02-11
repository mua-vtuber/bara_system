from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import Field

from app.models.base import BaseModel


# ── Legacy models (backward compatible) ──────────────────────────────


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


# ── Knowledge graph enums ────────────────────────────────────────────


class MemoryType(str, Enum):
    """Types of knowledge stored in the graph."""

    FACT = "fact"
    PREFERENCE = "preference"
    TRIPLE = "triple"
    INSIGHT = "insight"
    EPISODE = "episode"


class SourceType(str, Enum):
    """How a knowledge node was created."""

    AUTO_CAPTURE = "auto_capture"
    LLM_EXTRACT = "llm_extract"
    REFLECTION = "reflection"
    USER_EXPLICIT = "user_explicit"


# ── Knowledge nodes ──────────────────────────────────────────────────


class KnowledgeNodeCreate(BaseModel):
    """Data needed to insert a knowledge node."""

    content: str
    memory_type: MemoryType = MemoryType.FACT
    source_type: SourceType = SourceType.AUTO_CAPTURE
    importance: float = 0.5
    confidence: float = 0.7
    platform: str = ""
    author: str = ""
    embedding: Optional[bytes] = None
    metadata_json: str = "{}"


class KnowledgeNode(BaseModel):
    """Full knowledge node record from the database."""

    id: int
    content: str
    memory_type: str = "fact"
    source_type: str = "auto_capture"
    importance: float = 0.5
    confidence: float = 0.7
    platform: str = ""
    author: str = ""
    created_at: str = ""
    last_accessed_at: str = ""
    access_count: int = 0
    embedding: Optional[bytes] = None
    metadata_json: str = "{}"


# ── Knowledge edges ──────────────────────────────────────────────────


class KnowledgeEdge(BaseModel):
    """A directed relationship between two knowledge nodes."""

    id: int = 0
    source_id: int
    target_id: int
    relation: str = "related_to"
    weight: float = 1.0
    created_at: str = ""


# ── Entity profiles ──────────────────────────────────────────────────


class EntityProfileCreate(BaseModel):
    """Data needed to create or upsert an entity profile."""

    platform: str
    entity_name: str
    entity_type: str = "bot"
    display_name: str = ""


class EntityProfile(BaseModel):
    """Full entity profile record from the database."""

    id: int
    platform: str
    entity_name: str
    entity_type: str = "bot"
    display_name: str = ""
    summary: str = ""
    interests_json: str = "[]"
    personality_notes: str = ""
    first_seen_at: str = ""
    last_interaction_at: str = ""
    interaction_count: int = 0
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    trust_level: float = 0.5
    embedding: Optional[bytes] = None


# ── Retrieval results ────────────────────────────────────────────────


class RetrievalResult(BaseModel):
    """A scored knowledge node from hybrid retrieval."""

    node: KnowledgeNode
    score: float = 0.0
    source: str = ""  # "vector", "fts", "graph"


# ── Extraction results ───────────────────────────────────────────────


class ExtractionItem(BaseModel):
    """A single fact extracted by the LLM extractor."""

    content: str
    memory_type: MemoryType = MemoryType.FACT
    importance: float = 0.5
    subject: Optional[str] = None
    predicate: Optional[str] = None
    object: Optional[str] = None


class ExtractionResult(BaseModel):
    """Result of an LLM extraction pass."""

    items: list[ExtractionItem] = Field(default_factory=list)
    turn_count: int = 0
