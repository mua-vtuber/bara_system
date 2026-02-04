from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.notification import NotificationCreate, NotificationLog
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    """CRUD and query helpers for the ``notification_log`` table."""

    _table_name = "notification_log"

    async def add(self, item: NotificationCreate) -> NotificationLog:
        row_id = await self.execute_write(
            "INSERT INTO notification_log "
            "(platform, notification_id, notification_type, "
            "actor_name, post_id, is_read) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                item.platform,
                item.notification_id,
                item.notification_type,
                item.actor_name,
                item.post_id,
                item.is_read,
            ),
        )
        row = await self.fetch_one(
            "SELECT * FROM notification_log WHERE id = ?", (row_id,)
        )
        assert row is not None
        return NotificationLog(**row)

    async def get_by_id(self, id: int) -> Optional[NotificationLog]:
        row = await self.fetch_one(
            "SELECT * FROM notification_log WHERE id = ?", (id,)
        )
        if row is None:
            return None
        return NotificationLog(**row)

    async def delete(self, id: int) -> bool:
        existing = await self.fetch_one(
            "SELECT id FROM notification_log WHERE id = ?", (id,)
        )
        if existing is None:
            return False
        await self.execute_write(
            "DELETE FROM notification_log WHERE id = ?", (id,)
        )
        return True

    # ------------------------------------------------------------------
    # Domain-specific queries
    # ------------------------------------------------------------------

    async def get_unprocessed(self, platform: str) -> list[NotificationLog]:
        rows = await self.fetch_all(
            "SELECT * FROM notification_log "
            "WHERE platform = ? AND is_read = 0 "
            "AND response_activity_id IS NULL "
            "ORDER BY timestamp ASC",
            (platform,),
        )
        return [NotificationLog(**r) for r in rows]

    async def mark_responded(
        self, id: int, response_activity_id: int
    ) -> None:
        await self.execute_write(
            "UPDATE notification_log "
            "SET is_read = 1, response_activity_id = ? "
            "WHERE id = ?",
            (response_activity_id, id),
        )

    async def get_last_check_time(
        self, platform: str
    ) -> Optional[datetime]:
        row = await self.fetch_one(
            "SELECT MAX(timestamp) AS last_ts FROM notification_log "
            "WHERE platform = ?",
            (platform,),
        )
        if row is None or row["last_ts"] is None:
            return None
        ts = row["last_ts"]
        if isinstance(ts, str):
            return datetime.fromisoformat(ts)
        return ts  # type: ignore[return-value]

    async def exists_by_platform_id(
        self, platform: str, notification_id: str
    ) -> bool:
        row = await self.fetch_one(
            "SELECT 1 FROM notification_log "
            "WHERE platform = ? AND notification_id = ? LIMIT 1",
            (platform, notification_id),
        )
        return row is not None
