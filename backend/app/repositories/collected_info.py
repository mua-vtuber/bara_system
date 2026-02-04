from __future__ import annotations

import json
from typing import Optional

from app.models.collected_info import CollectedInfo, CollectedInfoCreate
from app.repositories.base import BaseRepository


class CollectedInfoRepository(BaseRepository):
    """CRUD and query helpers for the ``collected_info`` table."""

    _table_name = "collected_info"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_tags(tags: Optional[str | list[str]]) -> Optional[str]:
        """Ensure tags are stored as a JSON string."""
        if tags is None:
            return None
        if isinstance(tags, list):
            return json.dumps(tags, ensure_ascii=False)
        return tags

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def add(self, item: CollectedInfoCreate) -> CollectedInfo:
        tags_str = self._serialize_tags(item.tags)
        row_id = await self.execute_write(
            "INSERT INTO collected_info "
            "(platform, author, category, title, content, source_url, tags, embedding) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item.platform,
                item.author,
                item.category,
                item.title,
                item.content,
                item.source_url,
                tags_str,
                item.embedding,
            ),
        )
        row = await self.fetch_one(
            "SELECT * FROM collected_info WHERE id = ?", (row_id,)
        )
        assert row is not None
        return CollectedInfo(**row)

    async def get_by_id(self, id: int) -> Optional[CollectedInfo]:
        row = await self.fetch_one(
            "SELECT * FROM collected_info WHERE id = ?", (id,)
        )
        if row is None:
            return None
        return CollectedInfo(**row)

    async def delete(self, id: int) -> bool:
        existing = await self.fetch_one(
            "SELECT id FROM collected_info WHERE id = ?", (id,)
        )
        if existing is None:
            return False
        await self.execute_write(
            "DELETE FROM collected_info WHERE id = ?", (id,)
        )
        return True

    # ------------------------------------------------------------------
    # Domain-specific queries
    # ------------------------------------------------------------------

    async def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        bookmarked_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CollectedInfo]:
        conditions: list[str] = []
        params: list[object] = []

        if query is not None:
            conditions.append(
                "(title LIKE ? OR content LIKE ? OR tags LIKE ?)"
            )
            like = f"%{query}%"
            params.extend([like, like, like])
        if category is not None:
            conditions.append("category = ?")
            params.append(category)
        if bookmarked_only:
            conditions.append("bookmarked = 1")

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        sql = (
            f"SELECT * FROM collected_info {where} "
            "ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        rows = await self.fetch_all(sql, tuple(params))
        return [CollectedInfo(**r) for r in rows]

    async def toggle_bookmark(self, id: int) -> bool:
        """Toggle the bookmark flag and return the new state."""
        row = await self.fetch_one(
            "SELECT bookmarked FROM collected_info WHERE id = ?", (id,)
        )
        if row is None:
            raise ValueError(f"CollectedInfo {id} not found")
        new_state = not row["bookmarked"]
        await self.execute_write(
            "UPDATE collected_info SET bookmarked = ? WHERE id = ?",
            (new_state, id),
        )
        return new_state

    async def get_categories(self) -> list[str]:
        rows = await self.fetch_all(
            "SELECT DISTINCT category FROM collected_info "
            "WHERE category IS NOT NULL ORDER BY category"
        )
        return [r["category"] for r in rows]

    # ------------------------------------------------------------------
    # Vector / embedding helpers
    # ------------------------------------------------------------------

    async def get_embedding_candidates(
        self,
        limit: int = 100,
        category: str | None = None,
    ) -> list[tuple[int, bytes]]:
        """Fetch (id, embedding_blob) pairs for vector search."""
        conditions = ["embedding IS NOT NULL"]
        params: list[object] = []
        if category is not None:
            conditions.append("category = ?")
            params.append(category)

        where = "WHERE " + " AND ".join(conditions)
        sql = (
            f"SELECT id, embedding FROM collected_info {where} "
            "ORDER BY timestamp DESC LIMIT ?"
        )
        params.append(limit)

        rows = await self.fetch_all(sql, tuple(params))
        return [(r["id"], r["embedding"]) for r in rows]

    async def get_by_ids(self, ids: list[int]) -> list[CollectedInfo]:
        """Fetch multiple CollectedInfo records by their IDs."""
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        sql = f"SELECT * FROM collected_info WHERE id IN ({placeholders})"
        rows = await self.fetch_all(sql, tuple(ids))
        return [CollectedInfo(**r) for r in rows]

    async def update_embedding(self, info_id: int, embedding: bytes) -> None:
        """Update the embedding blob for a collected_info record."""
        await self.execute_write(
            "UPDATE collected_info SET embedding = ? WHERE id = ?",
            (embedding, info_id),
        )
