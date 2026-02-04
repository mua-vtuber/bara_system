from __future__ import annotations

from typing import Optional

from app.models.good_example import GoodExample, GoodExampleCreate
from app.repositories.base import BaseRepository


class GoodExampleRepository(BaseRepository):
    """CRUD and query helpers for the ``good_examples`` table."""

    _table_name = "good_examples"

    async def add(self, item: GoodExampleCreate) -> GoodExample:
        """Insert a new good example."""
        row_id = await self.execute_write(
            "INSERT INTO good_examples "
            "(platform, action_type, context_title, context_content, "
            " bot_response, engagement_score, reply_count, upvote_count, "
            " activity_id, post_id, embedding) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item.platform,
                item.action_type,
                item.context_title,
                item.context_content,
                item.bot_response,
                item.engagement_score,
                item.reply_count,
                item.upvote_count,
                item.activity_id,
                item.post_id,
                item.embedding,
            ),
        )
        row = await self.fetch_one(
            "SELECT * FROM good_examples WHERE id = ?", (row_id,)
        )
        assert row is not None
        return GoodExample(**row)

    async def get_by_action_type(
        self,
        action_type: str,
        limit: int = 10,
    ) -> list[GoodExample]:
        """Fetch good examples by action type, ordered by engagement score."""
        rows = await self.fetch_all(
            "SELECT * FROM good_examples WHERE action_type = ? "
            "ORDER BY engagement_score DESC LIMIT ?",
            (action_type, limit),
        )
        return [GoodExample(**r) for r in rows]

    async def get_embedding_candidates(
        self,
        limit: int = 100,
        action_type: str | None = None,
    ) -> list[tuple[int, bytes]]:
        """Fetch (id, embedding_blob) pairs for vector search."""
        conditions = ["embedding IS NOT NULL"]
        params: list[object] = []
        if action_type is not None:
            conditions.append("action_type = ?")
            params.append(action_type)

        where = "WHERE " + " AND ".join(conditions)
        sql = (
            f"SELECT id, embedding FROM good_examples {where} "
            "ORDER BY engagement_score DESC LIMIT ?"
        )
        params.append(limit)

        rows = await self.fetch_all(sql, tuple(params))
        return [(r["id"], r["embedding"]) for r in rows]

    async def get_by_ids(self, ids: list[int]) -> list[GoodExample]:
        """Fetch multiple good examples by their IDs."""
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        sql = f"SELECT * FROM good_examples WHERE id IN ({placeholders})"
        rows = await self.fetch_all(sql, tuple(ids))
        return [GoodExample(**r) for r in rows]

    async def exists_for_activity(self, activity_id: int) -> bool:
        """Check if a good example already exists for a given activity."""
        row = await self.fetch_one(
            "SELECT id FROM good_examples WHERE activity_id = ?",
            (activity_id,),
        )
        return row is not None
