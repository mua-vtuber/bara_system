from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.core.constants import KILL_SWITCH_FILE
from app.core.logging import get_logger
from app.models.events import EmergencyStopEvent

if TYPE_CHECKING:
    from app.core.config import Config
    from app.core.events import EventBus
    from app.core.task_queue import TaskQueue
    from app.services.scheduler import Scheduler

logger = get_logger(__name__)


class KillSwitch:
    """Emergency stop mechanism that halts the scheduler and task queue.

    The kill switch can be activated either via the REST API or by detecting
    the presence of the ``STOP_BOT`` file on disk.
    """

    def __init__(
        self,
        scheduler: Scheduler,
        task_queue: TaskQueue,
        event_bus: EventBus,
        config: Config,
    ) -> None:
        self._scheduler = scheduler
        self._task_queue = task_queue
        self._event_bus = event_bus
        self._config = config
        self._active: bool = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # File-based check
    # ------------------------------------------------------------------

    async def check_file(self) -> bool:
        """Return ``True`` if the kill-switch file exists on disk.

        When detected, :meth:`activate` is called automatically.
        """
        if Path(KILL_SWITCH_FILE).exists():
            if not self._active:
                await self.activate(source="file")
            return True
        return False

    # ------------------------------------------------------------------
    # Activate / deactivate
    # ------------------------------------------------------------------

    async def activate(self, source: str = "api") -> None:
        """Stop all automated work immediately."""
        if self._active:
            logger.warning("Kill switch already active")
            return

        logger.warning("Kill switch ACTIVATED (source=%s)", source)
        self._active = True

        # Stop the scheduler
        try:
            await self._scheduler.stop()
        except Exception as exc:
            logger.error("Error stopping scheduler during kill switch: %s", exc)

        # Stop the task queue
        try:
            await self._task_queue.stop()
        except Exception as exc:
            logger.error("Error stopping task queue during kill switch: %s", exc)

        # Publish emergency stop event
        await self._event_bus.publish(
            EmergencyStopEvent(source=source)
        )

    async def deactivate(self) -> None:
        """Clear the kill switch state and remove the file if present.

        Note: the scheduler is **not** restarted automatically.  The caller
        must explicitly start it again when ready.
        """
        if not self._active:
            logger.info("Kill switch already inactive")
            return

        # Remove kill switch file if it exists
        kill_path = Path(KILL_SWITCH_FILE)
        if kill_path.exists():
            try:
                kill_path.unlink()
                logger.info("Removed kill switch file: %s", KILL_SWITCH_FILE)
            except OSError as exc:
                logger.error("Failed to remove kill switch file: %s", exc)

        self._active = False
        logger.info("Kill switch DEACTIVATED")

    # ------------------------------------------------------------------
    # Graceful shutdown
    # ------------------------------------------------------------------

    async def graceful_shutdown(self) -> None:
        """Drain the task queue and stop the scheduler cleanly."""
        logger.info("Initiating graceful shutdown")

        # Stop scheduler first (no new tasks enqueued)
        try:
            await self._scheduler.stop()
        except Exception as exc:
            logger.error("Error during graceful scheduler stop: %s", exc)

        # Stop task queue (drains remaining tasks)
        try:
            await self._task_queue.stop()
        except Exception as exc:
            logger.error("Error during graceful queue stop: %s", exc)

        self._active = True
        logger.info("Graceful shutdown complete")
