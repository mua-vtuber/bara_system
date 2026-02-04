from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from app.models.activity import Activity, ActivityCreate, DailyCounts
from app.repositories.base import BaseRepository


class ActivityRepository(BaseRepository):
    """CRUD and query helpers for the ``activities`` table."""

    _table_name = "activities"

    async def add(self, item: ActivityCreate) -> Activity:
        row_id = await self.execute_write(
            "INSERT INTO activities "
            "(type, platform, platform_post_id, platform_comment_id, "
            "parent_id, url, original_content, bot_response, "
            "translated_content, translation_direction, llm_prompt, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item.type.value if hasattr(item.type, "value") else item.type,
                item.platform.value if hasattr(item.platform, "value") else item.platform,
                item.platform_post_id,
                item.platform_comment_id,
                item.parent_id,
                item.url,
                item.original_content,
                item.bot_response,
                item.translated_content,
                item.translation_direction,
                item.llm_prompt,
                item.status.value if hasattr(item.status, "value") else item.status,
            ),
        )
        row = await self.fetch_one(
            "SELECT * FROM activities WHERE id = ?", (row_id,)
        )
        assert row is not None
        return Activity(**row)

    async def get_by_id(self, id: int) -> Optional[Activity]:
        row = await self.fetch_one(
            "SELECT * FROM activities WHERE id = ?", (id,)
        )
        if row is None:
            return None
        return Activity(**row)

    async def delete(self, id: int) -> bool:
        existing = await self.fetch_one(
            "SELECT id FROM activities WHERE id = ?", (id,)
        )
        if existing is None:
            return False
        await self.execute_write(
            "DELETE FROM activities WHERE id = ?", (id,)
        )
        return True

    # ------------------------------------------------------------------
    # Domain-specific queries
    # ------------------------------------------------------------------

    async def has_responded_to(self, platform: str, post_id: str) -> bool:
        """Return True if at least one activity already targets *post_id*."""
        row = await self.fetch_one(
            "SELECT 1 FROM activities "
            "WHERE platform = ? AND platform_post_id = ? LIMIT 1",
            (platform, post_id),
        )
        return row is not None

    async def get_daily_counts(
        self, platform: str, target_date: date
    ) -> DailyCounts:
        date_str = target_date.isoformat()
        rows = await self.fetch_all(
            "SELECT type, COUNT(*) AS cnt FROM activities "
            "WHERE platform = ? AND DATE(timestamp) = ? "
            "GROUP BY type",
            (platform, date_str),
        )
        counts = {r["type"]: r["cnt"] for r in rows}
        return DailyCounts(
            comments=counts.get("comment", 0) + counts.get("reply", 0),
            posts=counts.get("post", 0),
            upvotes=counts.get("upvote", 0),
            downvotes=counts.get("downvote", 0),
            follows=counts.get("follow", 0),
        )

    async def get_by_status(
        self, status: str, limit: int = 50
    ) -> list[Activity]:
        rows = await self.fetch_all(
            "SELECT * FROM activities WHERE status = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (status, limit),
        )
        return [Activity(**r) for r in rows]

    async def update_status(
        self,
        id: int,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        await self.execute_write(
            "UPDATE activities SET status = ?, error_message = ? "
            "WHERE id = ?",
            (status, error_message, id),
        )

    async def get_timeline(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        platform_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Activity]:
        conditions: list[str] = []
        params: list[object] = []

        if start is not None:
            conditions.append("timestamp >= ?")
            params.append(start.isoformat())
        if end is not None:
            conditions.append("timestamp <= ?")
            params.append(end.isoformat())
        if platform_filter is not None:
            conditions.append("platform = ?")
            params.append(platform_filter)
        if type_filter is not None:
            conditions.append("type = ?")
            params.append(type_filter)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        sql = (
            f"SELECT * FROM activities {where} "
            "ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        rows = await self.fetch_all(sql, tuple(params))
        return [Activity(**r) for r in rows]

    async def get_by_platform_post(
        self, platform: str, post_id: str
    ) -> list[Activity]:
        rows = await self.fetch_all(
            "SELECT * FROM activities "
            "WHERE platform = ? AND platform_post_id = ? "
            "ORDER BY timestamp DESC",
            (platform, post_id),
        )
        return [Activity(**r) for r in rows]
