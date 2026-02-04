from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.constants import BACKUP_ALLOWED_TABLES
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.config import Config
    from app.core.database import Database

logger = get_logger(__name__)

_BACKUP_DIR = Path("backups")


class BackupService:
    """Export and import database + config snapshots as JSON."""

    def __init__(self, db: Database, config: Config) -> None:
        self._db = db
        self._config = config

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    async def export_backup(self) -> dict[str, Any]:
        """Dump all table data and config into a JSON-serialisable dict."""
        tables = list(BACKUP_ALLOWED_TABLES)

        data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "tables": {},
            "config": self._config.to_dict(),
        }

        for table in tables:
            try:
                rows = await self._db.fetch_all(f"SELECT * FROM {table}")  # noqa: S608
                # Convert datetime objects to ISO strings for JSON
                serialized_rows: list[dict[str, Any]] = []
                for row in rows:
                    clean: dict[str, Any] = {}
                    for k, v in row.items():
                        if isinstance(v, datetime):
                            clean[k] = v.isoformat()
                        else:
                            clean[k] = v
                    serialized_rows.append(clean)
                data["tables"][table] = serialized_rows
            except Exception as exc:
                logger.warning("Failed to export table %s: %s", table, exc)
                data["tables"][table] = []

        return data

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    async def import_backup(self, data: dict[str, Any]) -> None:
        """Restore tables from a backup dict.

        Each table is cleared and repopulated.  The config section is written
        back to ``config.json`` if a config_path is available.
        """
        tables_data: dict[str, list[dict[str, Any]]] = data.get("tables", {})

        _VALID_COLUMN_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

        for table_name, rows in tables_data.items():
            if table_name not in BACKUP_ALLOWED_TABLES:
                logger.warning("Backup import: rejected unknown table '%s'", table_name)
                continue
            if not isinstance(rows, list):
                continue

            # Clear existing data
            try:
                await self._db.execute_write(f"DELETE FROM {table_name}")  # noqa: S608 — table_name validated above
            except Exception as exc:
                logger.error("Failed to clear table %s: %s", table_name, exc)
                continue

            # Insert rows
            for row in rows:
                if not isinstance(row, dict):
                    continue
                # Validate column names against a strict pattern.
                columns = [c for c in row.keys() if _VALID_COLUMN_RE.match(c)]
                if not columns:
                    continue
                # Skip auto-increment ID columns.
                columns = [c for c in columns if c != "id"]
                if not columns:
                    continue
                values = [row[c] for c in columns]
                col_names = ", ".join(columns)
                placeholders = ", ".join(["?"] * len(columns))
                sql = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"  # noqa: S608 — validated
                try:
                    await self._db.execute_write(sql, tuple(values))
                except Exception as exc:
                    logger.error(
                        "Failed to restore row in %s: %s", table_name, exc
                    )

        # Restore config.json if available
        config_data = data.get("config")
        if config_data and self._config.config_path:
            try:
                self._config.config_path.write_text(
                    json.dumps(config_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                await self._config.reload_from_file()
                logger.info("Config restored from backup")
            except Exception as exc:
                logger.error("Failed to restore config: %s", exc)

        logger.info("Backup import completed")

    # ------------------------------------------------------------------
    # Backup listing
    # ------------------------------------------------------------------

    async def get_backup_list(self) -> list[dict[str, Any]]:
        """Return metadata for all backup files in the backups/ directory."""
        _BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        result: list[dict[str, Any]] = []
        for path in sorted(_BACKUP_DIR.glob("*.json"), reverse=True):
            try:
                stat = path.stat()
                result.append({
                    "filename": path.name,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(
                        stat.st_ctime, tz=timezone.utc
                    ).isoformat(),
                })
            except OSError as exc:
                logger.debug("Error reading backup file %s: %s", path, exc)

        return result
