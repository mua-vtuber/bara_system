from __future__ import annotations

from typing import Optional

from app.models.conversation import Conversation, ConversationCreate
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository):
    """CRUD and query helpers for the ``conversations`` table."""

    _table_name = "conversations"

    async def add(self, item: ConversationCreate) -> Conversation:
        row_id = await self.execute_write(
            "INSERT INTO conversations (role, content, platform) "
            "VALUES (?, ?, ?)",
            (item.role, item.content, item.platform),
        )
        row = await self.fetch_one(
            "SELECT * FROM conversations WHERE id = ?", (row_id,)
        )
        assert row is not None
        return Conversation(**row)

    async def get_by_id(self, id: int) -> Optional[Conversation]:
        row = await self.fetch_one(
            "SELECT * FROM conversations WHERE id = ?", (id,)
        )
        if row is None:
            return None
        return Conversation(**row)

    async def delete(self, id: int) -> bool:
        existing = await self.fetch_one(
            "SELECT id FROM conversations WHERE id = ?", (id,)
        )
        if existing is None:
            return False
        await self.execute_write(
            "DELETE FROM conversations WHERE id = ?", (id,)
        )
        return True

    async def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        platform_filter: Optional[str] = None,
    ) -> list[Conversation]:
        conditions: list[str] = []
        params: list[object] = []

        if platform_filter is not None:
            conditions.append("platform = ?")
            params.append(platform_filter)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        sql = (
            f"SELECT * FROM conversations {where} "
            "ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        rows = await self.fetch_all(sql, tuple(params))
        return [Conversation(**r) for r in rows]
