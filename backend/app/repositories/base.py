from __future__ import annotations

from typing import Any, Optional

from app.core.database import Database


class BaseRepository:
    """Thin convenience wrapper around :class:`Database`.

    Subclasses set ``_table_name`` and build domain-specific queries.
    All SQL uses parameter binding -- **never** f-string interpolation.
    """

    _table_name: str = ""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Delegated helpers
    # ------------------------------------------------------------------

    async def execute_write(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> Optional[int]:
        return await self._db.execute_write(sql, params)

    async def fetch_one(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> Optional[dict[str, Any]]:
        return await self._db.fetch_one(sql, params)

    async def fetch_all(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        return await self._db.fetch_all(sql, params)
