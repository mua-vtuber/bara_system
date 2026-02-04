from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.constants import LOG_DIR_WARNING_SIZE_BYTES
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.config import Config
    from app.core.database import Database
    from app.platforms.registry import PlatformRegistry
    from app.services.llm import LLMService

logger = get_logger(__name__)


@dataclass
class HealthCheckResult:
    """Aggregated result of all health checks."""

    status: str  # "healthy", "degraded", "unhealthy"
    uptime_seconds: int = 0
    checks: list[dict[str, Any]] = field(default_factory=list)


class HealthMonitor:
    """Performs comprehensive health checks across all system components:
    Ollama LLM, database, platform adapters, and disk space.
    """

    def __init__(
        self,
        config: Config,
        llm_service: LLMService,
        db: Database,
        platform_registry: PlatformRegistry,
    ) -> None:
        self._config = config
        self._llm_service = llm_service
        self._db = db
        self._platform_registry = platform_registry
        self._start_time: float = time.monotonic()
        self._last_result: HealthCheckResult | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_all(self) -> HealthCheckResult:
        """Run all health checks and return an aggregated result."""
        checks: list[dict[str, Any]] = []
        has_critical_failure = False
        has_warning = False

        # 1. Ollama / LLM health
        ollama_ok = await self._check_ollama()
        checks.append({
            "name": "ollama",
            "status": "ok" if ollama_ok else "fail",
            "message": "Ollama is reachable" if ollama_ok else "Ollama unreachable",
        })
        if not ollama_ok:
            has_critical_failure = True

        # 2. Database health
        db_ok = await self._check_database()
        checks.append({
            "name": "database",
            "status": "ok" if db_ok else "fail",
            "message": "Database responding" if db_ok else "Database check failed",
        })
        if not db_ok:
            has_critical_failure = True

        # 3. Platform health
        platform_checks = await self._check_platforms()
        for pc in platform_checks:
            checks.append(pc)
            if pc["status"] == "fail":
                has_warning = True

        # 4. Disk space
        disk_check = self._check_disk()
        checks.append(disk_check)
        if disk_check["status"] == "warning":
            has_warning = True
        elif disk_check["status"] == "fail":
            has_critical_failure = True

        # 5. Log directory
        log_check = self._check_log_directory()
        checks.append(log_check)
        if log_check["status"] == "warning":
            has_warning = True

        # Determine overall status
        if has_critical_failure:
            status = "unhealthy"
        elif has_warning:
            status = "degraded"
        else:
            status = "healthy"

        result = HealthCheckResult(
            status=status,
            uptime_seconds=self.get_uptime_seconds(),
            checks=checks,
        )
        self._last_result = result
        return result

    def get_current_status(self) -> str:
        """Return the status string from the last check, or 'unknown'."""
        if self._last_result is None:
            return "unknown"
        return self._last_result.status

    def get_uptime_seconds(self) -> int:
        """Return seconds since the monitor was created."""
        return int(time.monotonic() - self._start_time)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    async def _check_ollama(self) -> bool:
        try:
            return await self._llm_service.check_health()
        except Exception as exc:
            logger.debug("Ollama health check failed: %s", exc)
            return False

    async def _check_database(self) -> bool:
        try:
            row = await self._db.fetch_one("SELECT 1 AS ok")
            return row is not None and row.get("ok") == 1
        except Exception as exc:
            logger.debug("Database health check failed: %s", exc)
            return False

    async def _check_platforms(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for adapter in self._platform_registry.get_enabled_platforms():
            name = adapter.platform_name
            try:
                valid = await adapter.validate_credentials()
                results.append({
                    "name": f"platform:{name}",
                    "status": "ok" if valid else "fail",
                    "message": (
                        f"{name} credentials valid"
                        if valid
                        else f"{name} credentials invalid"
                    ),
                })
            except Exception as exc:
                results.append({
                    "name": f"platform:{name}",
                    "status": "fail",
                    "message": f"{name} check error: {exc}",
                })
        return results

    def _check_disk(self) -> dict[str, Any]:
        try:
            usage = shutil.disk_usage(".")
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            pct_free = (usage.free / usage.total) * 100

            if pct_free < 5:
                status = "fail"
                message = f"Disk critically low: {free_gb:.1f}GB / {total_gb:.1f}GB ({pct_free:.1f}% free)"
            elif pct_free < 15:
                status = "warning"
                message = f"Disk space low: {free_gb:.1f}GB / {total_gb:.1f}GB ({pct_free:.1f}% free)"
            else:
                status = "ok"
                message = f"Disk OK: {free_gb:.1f}GB / {total_gb:.1f}GB ({pct_free:.1f}% free)"

            return {"name": "disk", "status": status, "message": message}
        except Exception as exc:
            return {
                "name": "disk",
                "status": "fail",
                "message": f"Disk check error: {exc}",
            }

    def _check_log_directory(self, log_dir: str | Path = "logs") -> dict[str, Any]:
        log_path = Path(log_dir)

        if not log_path.is_dir():
            return {
                "name": "log_directory",
                "status": "warning",
                "message": "Log directory does not exist",
            }

        # Check writable
        writable = os.access(log_path, os.W_OK)
        if not writable:
            return {
                "name": "log_directory",
                "status": "warning",
                "message": "Log directory is not writable",
            }

        # Calculate total size
        total_size = 0
        for entry in log_path.iterdir():
            if entry.is_file():
                try:
                    total_size += entry.stat().st_size
                except OSError:
                    pass

        size_mb = total_size / (1024 * 1024)

        if total_size > LOG_DIR_WARNING_SIZE_BYTES:
            return {
                "name": "log_directory",
                "status": "warning",
                "message": f"Log directory large: {size_mb:.1f}MB (threshold: {LOG_DIR_WARNING_SIZE_BYTES / (1024 * 1024):.0f}MB)",
            }

        return {
            "name": "log_directory",
            "status": "ok",
            "message": f"Log directory OK: {size_mb:.1f}MB",
        }
