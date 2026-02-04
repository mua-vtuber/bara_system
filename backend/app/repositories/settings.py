from __future__ import annotations

from typing import Optional

from app.models.settings import SettingsSnapshot
from app.repositories.base import BaseRepository


class SettingsRepository(BaseRepository):
    """Read/write helpers for the ``settings_history`` table."""

    _table_name = "settings_history"

    async def save_snapshot(self, config_json: str) -> None:
        await self.execute_write(
            "INSERT INTO settings_history (config_snapshot) VALUES (?)",
            (config_json,),
        )

    async def get_latest(self) -> Optional[str]:
        row = await self.fetch_one(
            "SELECT config_snapshot FROM settings_history "
            "ORDER BY timestamp DESC LIMIT 1"
        )
        if row is None:
            return None
        return row["config_snapshot"]

    async def get_history(self, limit: int = 20) -> list[SettingsSnapshot]:
        rows = await self.fetch_all(
            "SELECT * FROM settings_history "
            "ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [SettingsSnapshot(**r) for r in rows]
