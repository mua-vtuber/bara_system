from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, Union

from app.models.mission import Mission, MissionCreate
from app.repositories.base import BaseRepository


class MissionRepository(BaseRepository):
    """CRUD and query helpers for the ``missions`` table."""

    _table_name = "missions"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_model(row: dict) -> Mission:
        """Convert a DB row to a Mission, parsing JSON fields."""
        data = dict(row)
        responses_raw = data.get("collected_responses", "[]")
        if isinstance(responses_raw, str):
            try:
                data["collected_responses"] = json.loads(responses_raw)
            except (json.JSONDecodeError, TypeError):
                data["collected_responses"] = []
        return Mission(**data)

    @staticmethod
    def _serialize_responses(responses: list[dict]) -> str:
        return json.dumps(responses, ensure_ascii=False)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def add(self, create: MissionCreate) -> Mission:
        """Insert a new mission and return the full record."""
        row_id = await self.execute_write(
            "INSERT INTO missions "
            "(topic, question_hint, urgency, target_platform, "
            " target_community, user_notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                create.topic,
                create.question_hint,
                create.urgency,
                create.target_platform,
                create.target_community,
                create.user_notes,
            ),
        )
        row = await self.fetch_one(
            "SELECT * FROM missions WHERE id = ?", (row_id,)
        )
        if row is None:
            raise ValueError("Failed to retrieve newly created mission")
        return self._row_to_model(row)

    async def get(self, mission_id: int) -> Optional[Mission]:
        row = await self.fetch_one(
            "SELECT * FROM missions WHERE id = ?", (mission_id,)
        )
        if row is None:
            return None
        return self._row_to_model(row)

    async def get_by_status(
        self, status: Union[str, list[str]]
    ) -> list[Mission]:
        """Get missions filtered by one or more statuses."""
        if isinstance(status, str):
            rows = await self.fetch_all(
                "SELECT * FROM missions WHERE status = ? "
                "ORDER BY created_at DESC",
                (status,),
            )
        else:
            placeholders = ", ".join("?" for _ in status)
            rows = await self.fetch_all(
                f"SELECT * FROM missions WHERE status IN ({placeholders}) "
                "ORDER BY created_at DESC",
                tuple(status),
            )
        return [self._row_to_model(r) for r in rows]

    async def get_active(self) -> list[Mission]:
        """Get all missions that are not complete or cancelled."""
        rows = await self.fetch_all(
            "SELECT * FROM missions "
            "WHERE status NOT IN ('complete', 'cancelled') "
            "ORDER BY created_at ASC",
        )
        return [self._row_to_model(r) for r in rows]

    async def get_all(
        self, limit: int = 50, offset: int = 0
    ) -> list[Mission]:
        rows = await self.fetch_all(
            "SELECT * FROM missions ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._row_to_model(r) for r in rows]

    async def count(self) -> int:
        row = await self.fetch_one("SELECT COUNT(*) as cnt FROM missions")
        return row["cnt"] if row else 0

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    async def update_status(self, mission_id: int, status: str) -> None:
        """Update mission status. Sets completed_at for terminal states."""
        if status in ("complete", "cancelled"):
            now = datetime.now(timezone.utc).isoformat()
            await self.execute_write(
                "UPDATE missions SET status = ?, completed_at = ? WHERE id = ?",
                (status, now, mission_id),
            )
        else:
            await self.execute_write(
                "UPDATE missions SET status = ? WHERE id = ?",
                (status, mission_id),
            )

    async def increment_warmup(self, mission_id: int) -> int:
        """Increment warmup_count and return the new value."""
        await self.execute_write(
            "UPDATE missions SET warmup_count = warmup_count + 1 WHERE id = ?",
            (mission_id,),
        )
        row = await self.fetch_one(
            "SELECT warmup_count FROM missions WHERE id = ?", (mission_id,)
        )
        return row["warmup_count"] if row else 0

    async def set_post_info(
        self, mission_id: int, platform: str, post_id: str
    ) -> None:
        """Record the published question post info."""
        await self.execute_write(
            "UPDATE missions SET post_platform = ?, post_id = ? WHERE id = ?",
            (platform, post_id, mission_id),
        )

    # ------------------------------------------------------------------
    # Response collection
    # ------------------------------------------------------------------

    async def add_response(
        self, mission_id: int, response: dict
    ) -> None:
        """Append a response to the collected_responses JSON array."""
        row = await self.fetch_one(
            "SELECT collected_responses FROM missions WHERE id = ?",
            (mission_id,),
        )
        if row is None:
            return

        existing_raw = row["collected_responses"] or "[]"
        try:
            existing = json.loads(existing_raw) if isinstance(existing_raw, str) else existing_raw
        except (json.JSONDecodeError, TypeError):
            existing = []

        existing.append(response)
        await self.execute_write(
            "UPDATE missions SET collected_responses = ? WHERE id = ?",
            (self._serialize_responses(existing), mission_id),
        )

    async def set_summary(self, mission_id: int, summary: str) -> None:
        await self.execute_write(
            "UPDATE missions SET summary = ? WHERE id = ?",
            (summary, mission_id),
        )
