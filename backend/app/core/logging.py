from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from app.core.constants import LOG_MAX_SIZE_BYTES, LOG_RETENTION_DAYS


class _JSONFormatter(logging.Formatter):
    """Produces one JSON object per log record for file output."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


class _ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter with timestamp and level."""

    FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"

    def __init__(self) -> None:
        super().__init__(fmt=self.FORMAT, datefmt="%Y-%m-%d %H:%M:%S")


_setup_done: bool = False


def setup_logging(
    log_dir: str | Path = "logs",
    level: int = logging.INFO,
    max_bytes: int = LOG_MAX_SIZE_BYTES,
    backup_count: int = LOG_RETENTION_DAYS,
) -> None:
    """Configure the root logger with console and rotating file handlers.

    Safe to call multiple times; subsequent calls are no-ops.
    """
    global _setup_done
    if _setup_done:
        return
    _setup_done = True

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(_ConsoleFormatter())
    root.addHandler(console_handler)

    # Rotating file handler (JSON)
    file_handler = RotatingFileHandler(
        filename=str(log_path / "bara_system.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(_JSONFormatter())
    root.addHandler(file_handler)


def cleanup_old_logs(log_dir: str | Path = "logs", max_age_days: int = LOG_RETENTION_DAYS) -> int:
    """Delete log files older than *max_age_days*. Returns count of deleted files."""
    import time

    log_path = Path(log_dir)
    if not log_path.is_dir():
        return 0

    cutoff = time.time() - (max_age_days * 86400)
    deleted = 0

    for entry in log_path.iterdir():
        if not entry.is_file():
            continue
        if not (entry.suffix == ".log" or ".log." in entry.name):
            continue
        try:
            if entry.stat().st_mtime < cutoff:
                entry.unlink()
                logging.getLogger(__name__).info("Deleted old log file: %s", entry.name)
                deleted += 1
        except OSError:
            pass

    return deleted


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given name."""
    return logging.getLogger(name)
