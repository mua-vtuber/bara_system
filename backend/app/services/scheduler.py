from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from app.core.constants import AUTO_BACKUP_DIR, AUTO_BACKUP_INTERVAL_SECONDS, BACKUP_RETENTION_DAYS
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.config import Config
    from app.core.events import EventBus
    from app.services.backup import BackupService
    from app.services.feed_monitor import FeedMonitor
    from app.services.notifications import NotificationService

logger = get_logger(__name__)

# Default notification polling interval (seconds)
_DEFAULT_NOTIFICATION_INTERVAL: int = 60


class Scheduler:
    """Manages periodic execution of feed monitoring and notification polling.

    Tasks only execute during configured active hours.  Each periodic task
    runs in its own ``asyncio.Task`` with a sleep-based loop.
    """

    def __init__(
        self,
        config: Config,
        feed_monitor: FeedMonitor,
        notification_service: NotificationService,
        event_bus: EventBus,
        backup_service: BackupService | None = None,
    ) -> None:
        self._config = config
        self._feed_monitor = feed_monitor
        self._notification_service = notification_service
        self._event_bus = event_bus
        self._backup_service = backup_service
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._running: bool = False
        self._intervals: dict[str, int] = {}
        self._next_run: dict[str, datetime | None] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start all periodic tasks."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True

        feed_interval = self._config.behavior.monitoring_interval_minutes * 60
        notif_interval = _DEFAULT_NOTIFICATION_INTERVAL

        self._intervals["feed_monitor"] = feed_interval
        self._intervals["notification_poll"] = notif_interval

        self._tasks["feed_monitor"] = asyncio.create_task(
            self._periodic_task(
                "feed_monitor",
                self._feed_monitor.poll_all_platforms,
                feed_interval,
            ),
            name="scheduler-feed-monitor",
        )

        self._tasks["notification_poll"] = asyncio.create_task(
            self._periodic_task(
                "notification_poll",
                self._notification_service.poll_notifications,
                notif_interval,
            ),
            name="scheduler-notification-poll",
        )

        if self._backup_service is not None:
            backup_interval = AUTO_BACKUP_INTERVAL_SECONDS
            self._intervals["daily_backup"] = backup_interval
            self._tasks["daily_backup"] = asyncio.create_task(
                self._periodic_task(
                    "daily_backup",
                    self._run_daily_backup,
                    backup_interval,
                ),
                name="scheduler-daily-backup",
            )

        logger.info(
            "Scheduler started (feed_interval=%ds, notif_interval=%ds)",
            feed_interval,
            notif_interval,
        )

    async def stop(self) -> None:
        """Cancel all periodic tasks and wait for them to finish."""
        if not self._running:
            return

        self._running = False

        for name, task in self._tasks.items():
            task.cancel()
            logger.debug("Cancelling scheduler task: %s", name)

        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

        self._tasks.clear()
        self._next_run.clear()
        logger.info("Scheduler stopped")

    # ------------------------------------------------------------------
    # Periodic task loop
    # ------------------------------------------------------------------

    async def _periodic_task(
        self,
        name: str,
        coro_func: Callable[[], Awaitable[Any]],
        interval_seconds: int,
    ) -> None:
        """Run *coro_func* every *interval_seconds*, respecting active hours."""
        logger.debug("Periodic task '%s' started (interval=%ds)", name, interval_seconds)

        while self._running:
            try:
                # Check active hours
                if not self.is_within_active_hours():
                    logger.debug(
                        "Task '%s' skipped: outside active hours", name
                    )
                    self._next_run[name] = None
                    await asyncio.sleep(60)  # Re-check every minute
                    continue

                # Record next run time
                next_time = datetime.now(timezone.utc)
                self._next_run[name] = next_time

                # Execute
                logger.debug("Executing periodic task: %s", name)
                await coro_func()

            except asyncio.CancelledError:
                logger.debug("Periodic task '%s' cancelled", name)
                return
            except Exception:
                logger.exception("Periodic task '%s' failed", name)

            # Sleep until next interval
            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                return

    # ------------------------------------------------------------------
    # Daily backup
    # ------------------------------------------------------------------

    async def _run_daily_backup(self) -> None:
        if self._backup_service is None:
            return

        backup_dir = Path(AUTO_BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)

        try:
            data = await self._backup_service.export_backup()
            filename = f"auto_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
            filepath = backup_dir / filename
            filepath.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.info("Auto-backup saved: %s", filepath)
        except Exception:
            logger.exception("Auto-backup failed")
            return

        # Cleanup old auto-backups
        cutoff = datetime.now(timezone.utc).timestamp() - (BACKUP_RETENTION_DAYS * 86400)
        for entry in backup_dir.iterdir():
            if entry.is_file() and entry.name.startswith("auto_") and entry.suffix == ".json":
                try:
                    if entry.stat().st_mtime < cutoff:
                        entry.unlink()
                        logger.info("Deleted old auto-backup: %s", entry.name)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Active hours check
    # ------------------------------------------------------------------

    def is_within_active_hours(self) -> bool:
        """Return ``True`` when the current time is inside configured active hours."""
        now = datetime.now()
        is_weekend = now.weekday() >= 5

        active_hours = self._config.behavior.active_hours
        if is_weekend:
            start = active_hours.weekend.start
            end = active_hours.weekend.end
        else:
            start = active_hours.weekday.start
            end = active_hours.weekday.end

        return start <= now.hour < end

    # ------------------------------------------------------------------
    # State / reconfiguration
    # ------------------------------------------------------------------

    def get_state(self) -> dict[str, Any]:
        """Return current scheduler state for the status API."""
        tasks_info: dict[str, Any] = {}
        for name, task in self._tasks.items():
            tasks_info[name] = {
                "running": not task.done(),
                "interval_seconds": self._intervals.get(name, 0),
                "next_run": (
                    self._next_run[name].isoformat()
                    if self._next_run.get(name)
                    else None
                ),
            }
        return {
            "running": self._running,
            "active_hours": self.is_within_active_hours(),
            "tasks": tasks_info,
        }

    async def add_task(
        self,
        name: str,
        coro_func: Callable[[], Awaitable[Any]],
        interval_seconds: int,
    ) -> None:
        """Register and start a new periodic task.

        Can be called after ``start()`` to dynamically add tasks.
        """
        if not self._running:
            logger.warning("Cannot add task '%s': scheduler not running", name)
            return

        if name in self._tasks:
            logger.warning("Task '%s' already exists, rescheduling", name)
            await self.reschedule(name, interval_seconds)
            return

        self._intervals[name] = interval_seconds
        self._tasks[name] = asyncio.create_task(
            self._periodic_task(name, coro_func, interval_seconds),
            name=f"scheduler-{name}",
        )
        logger.info(
            "Added periodic task '%s' (interval=%ds)", name, interval_seconds
        )

    async def reschedule(self, task_name: str, new_interval: int) -> None:
        """Change the interval for a running task by restarting it."""
        if task_name not in self._tasks:
            logger.warning("Cannot reschedule unknown task: %s", task_name)
            return

        old_task = self._tasks[task_name]
        old_task.cancel()
        try:
            await old_task
        except (asyncio.CancelledError, Exception):
            pass

        self._intervals[task_name] = new_interval

        # Determine which coroutine to use
        coro_map: dict[str, Callable[[], Awaitable[Any]]] = {
            "feed_monitor": self._feed_monitor.poll_all_platforms,
            "notification_poll": self._notification_service.poll_notifications,
            "daily_backup": self._run_daily_backup,
        }

        coro_func = coro_map.get(task_name)
        if coro_func is None:
            logger.error("No coroutine mapped for task: %s", task_name)
            return

        self._tasks[task_name] = asyncio.create_task(
            self._periodic_task(task_name, coro_func, new_interval),
            name=f"scheduler-{task_name}",
        )
        logger.info(
            "Rescheduled task '%s' with new interval=%ds", task_name, new_interval
        )
