from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional, Sequence

import aiosqlite

from app.core.constants import DEFAULT_BUSY_TIMEOUT_MS
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger

logger = get_logger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:
    """Async SQLite wrapper with WAL mode and write serialization.

    All writes go through ``execute_write`` or ``execute_write_transaction``
    which acquire ``_write_lock`` to serialize concurrent writes inside the
    Python process.  Reads never acquire the lock because WAL mode allows
    concurrent readers even while a write is in progress.
    """

    _instance: Optional[Database] = None

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self._conn = connection
        self._write_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Factory / singleton
    # ------------------------------------------------------------------

    @classmethod
    async def initialize(cls, db_path: str = "bara_system.db") -> Database:
        try:
            conn = await aiosqlite.connect(db_path)
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute(f"PRAGMA busy_timeout={DEFAULT_BUSY_TIMEOUT_MS}")
            instance = cls(conn)
            cls._instance = instance
            logger.info("Database initialized: %s", db_path)
            return instance
        except Exception as exc:
            raise DatabaseError(f"Failed to initialize database: {exc}") from exc

    @classmethod
    async def initialize_memory(cls) -> Database:
        try:
            conn = await aiosqlite.connect(":memory:")
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute(f"PRAGMA busy_timeout={DEFAULT_BUSY_TIMEOUT_MS}")
            instance = cls(conn)
            cls._instance = instance
            logger.info("In-memory database initialized")
            return instance
        except Exception as exc:
            raise DatabaseError(f"Failed to initialize in-memory database: {exc}") from exc

    @classmethod
    def get_instance(cls) -> Database:
        if cls._instance is None:
            raise DatabaseError("Database has not been initialized.")
        return cls._instance

    # ------------------------------------------------------------------
    # Migration runner
    # ------------------------------------------------------------------

    async def run_migrations(self, migrations_dir: Optional[Path] = None) -> None:
        migrations_path = migrations_dir or _MIGRATIONS_DIR

        await self.execute_write(
            "CREATE TABLE IF NOT EXISTS _migrations ("
            "    id INTEGER PRIMARY KEY,"
            "    filename TEXT UNIQUE NOT NULL,"
            "    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")",
            (),
        )

        rows = await self.fetch_all("SELECT filename FROM _migrations", ())
        applied: set[str] = {row["filename"] for row in rows}

        sql_files = sorted(
            p for p in migrations_path.glob("*.sql") if p.name not in applied
        )

        for sql_file in sql_files:
            logger.info("Applying migration: %s", sql_file.name)
            sql_text = sql_file.read_text(encoding="utf-8")

            statements = [s.strip() for s in sql_text.split(";") if s.strip()]
            operations: list[tuple[str, tuple[Any, ...]]] = [
                (stmt, ()) for stmt in statements
            ]
            operations.append(
                ("INSERT INTO _migrations (filename) VALUES (?)", (sql_file.name,))
            )
            await self.execute_write_transaction(operations)
            logger.info("Migration applied: %s", sql_file.name)

    # ------------------------------------------------------------------
    # Write operations (lock-protected)
    # ------------------------------------------------------------------

    async def execute_write(self, sql: str, params: tuple[Any, ...] = ()) -> Optional[int]:
        async with self._write_lock:
            try:
                cursor = await self._conn.execute(sql, params)
                await self._conn.commit()
                return cursor.lastrowid
            except Exception as exc:
                raise DatabaseError(f"Write failed: {exc}") from exc

    async def execute_write_transaction(
        self, operations: Sequence[tuple[str, tuple[Any, ...]]]
    ) -> None:
        async with self._write_lock:
            try:
                for sql, params in operations:
                    await self._conn.execute(sql, params)
                await self._conn.commit()
            except Exception as exc:
                await self._conn.rollback()
                raise DatabaseError(f"Transaction failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Read operations (no lock needed under WAL)
    # ------------------------------------------------------------------

    async def fetch_one(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> Optional[dict[str, Any]]:
        try:
            cursor = await self._conn.execute(sql, params)
            row = await cursor.fetchone()
            if row is None:
                return None
            return dict(row)
        except Exception as exc:
            raise DatabaseError(f"fetch_one failed: {exc}") from exc

    async def fetch_all(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        try:
            cursor = await self._conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            raise DatabaseError(f"fetch_all failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        try:
            await self._conn.close()
            logger.info("Database connection closed")
        except Exception as exc:
            logger.warning("Error closing database: %s", exc)
        finally:
            if Database._instance is self:
                Database._instance = None
