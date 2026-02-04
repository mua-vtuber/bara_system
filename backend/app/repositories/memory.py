from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from app.models.memory import BotMemory, BotMemoryCreate
from app.repositories.base import BaseRepository


class BotMemoryRepository(BaseRepository):
    """CRUD and query helpers for the ``bot_memory`` table."""

    _table_name = "bot_memory"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_model(row: dict) -> BotMemory:
        """Convert a DB row to a BotMemory, parsing JSON fields."""
        data = dict(row)
        topics_raw = data.get("topics", "[]")
        if isinstance(topics_raw, str):
            try:
                data["topics"] = json.loads(topics_raw)
            except (json.JSONDecodeError, TypeError):
                data["topics"] = []
        return BotMemory(**data)

    @staticmethod
    def _serialize_topics(topics: list[str]) -> str:
        return json.dumps(topics, ensure_ascii=False)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def add_or_update(self, create: BotMemoryCreate) -> BotMemory:
        """UPSERT: insert new or update existing bot memory entry."""
        now = datetime.now(timezone.utc).isoformat()
        topics_str = self._serialize_topics(create.topics)

        await self.execute_write(
            "INSERT INTO bot_memory "
            "(platform, entity_name, entity_type, topics, relationship_notes, "
            " first_seen_at, last_interaction_at, interaction_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1) "
            "ON CONFLICT(platform, entity_name) DO UPDATE SET "
            "  interaction_count = interaction_count + 1, "
            "  last_interaction_at = ?, "
            "  entity_type = COALESCE(NULLIF(?, ''), entity_type), "
            "  topics = CASE "
            "    WHEN ? = '[]' THEN topics "
            "    ELSE ? "
            "  END",
            (
                create.platform,
                create.entity_name,
                create.entity_type,
                topics_str,
                create.relationship_notes,
                now,
                now,
                # ON CONFLICT params:
                now,
                create.entity_type,
                topics_str,
                topics_str,
            ),
        )

        return await self.get_by_name(create.platform, create.entity_name)  # type: ignore[return-value]

    async def get_by_name(
        self, platform: str, entity_name: str
    ) -> Optional[BotMemory]:
        row = await self.fetch_one(
            "SELECT * FROM bot_memory WHERE platform = ? AND entity_name = ?",
            (platform, entity_name),
        )
        if row is None:
            return None
        return self._row_to_model(row)

    async def get_by_id(self, memory_id: int) -> Optional[BotMemory]:
        row = await self.fetch_one(
            "SELECT * FROM bot_memory WHERE id = ?", (memory_id,)
        )
        if row is None:
            return None
        return self._row_to_model(row)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    async def get_frequent_contacts(
        self, platform: str, limit: int = 10
    ) -> list[BotMemory]:
        """Top contacts by interaction count on a platform."""
        rows = await self.fetch_all(
            "SELECT * FROM bot_memory WHERE platform = ? "
            "ORDER BY interaction_count DESC LIMIT ?",
            (platform, limit),
        )
        return [self._row_to_model(r) for r in rows]

    async def get_by_topic(
        self, topic_keyword: str, limit: int = 10
    ) -> list[BotMemory]:
        """Find memories whose topics JSON contains the keyword."""
        rows = await self.fetch_all(
            "SELECT * FROM bot_memory WHERE topics LIKE ? "
            "ORDER BY interaction_count DESC LIMIT ?",
            (f"%{topic_keyword}%", limit),
        )
        return [self._row_to_model(r) for r in rows]

    async def search(
        self,
        query: str,
        platform: Optional[str] = None,
        limit: int = 20,
    ) -> list[BotMemory]:
        """Search across entity_name, topics, and relationship_notes."""
        conditions = [
            "(entity_name LIKE ? OR topics LIKE ? OR relationship_notes LIKE ?)"
        ]
        like = f"%{query}%"
        params: list[object] = [like, like, like]

        if platform is not None:
            conditions.append("platform = ?")
            params.append(platform)

        where = "WHERE " + " AND ".join(conditions)
        sql = (
            f"SELECT * FROM bot_memory {where} "
            "ORDER BY last_interaction_at DESC LIMIT ?"
        )
        params.append(limit)

        rows = await self.fetch_all(sql, tuple(params))
        return [self._row_to_model(r) for r in rows]

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------

    async def update_notes(
        self, memory_id: int, notes: str, sentiment: str = "neutral"
    ) -> None:
        """Update relationship notes and sentiment (typically LLM-generated)."""
        await self.execute_write(
            "UPDATE bot_memory SET relationship_notes = ?, sentiment = ? "
            "WHERE id = ?",
            (notes, sentiment, memory_id),
        )

    async def update_topics(
        self, memory_id: int, topics: list[str]
    ) -> None:
        """Replace the topics list for a memory entry."""
        await self.execute_write(
            "UPDATE bot_memory SET topics = ? WHERE id = ?",
            (self._serialize_topics(topics), memory_id),
        )

    async def update_embedding(self, memory_id: int, embedding: bytes) -> None:
        """Update the embedding blob for a bot_memory record."""
        await self.execute_write(
            "UPDATE bot_memory SET embedding = ? WHERE id = ?",
            (embedding, memory_id),
        )
