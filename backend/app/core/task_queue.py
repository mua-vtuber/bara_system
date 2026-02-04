from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from app.core.logging import get_logger
from app.core.rate_limiter import PlatformRateLimiter

logger = get_logger(__name__)

# Priority constants (lower = higher priority)
PRIORITY_NOTIFICATION_REPLY: int = 1
PRIORITY_MANUAL: int = 3
PRIORITY_SCHEDULED: int = 5


@dataclass(order=False)
class QueuedTask:
    """A unit of work submitted to :class:`TaskQueue`.

    Ordering is determined by ``(priority, created_at)`` so that the
    :class:`asyncio.PriorityQueue` picks the highest-priority, oldest
    task first.
    """

    priority: int
    created_at: datetime
    platform: str
    action_type: str  # "post", "comment", "upvote"
    coroutine_func: Callable[..., Awaitable[Any]]
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    callback: Optional[Callable[[Any], Any]] = None
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    # PriorityQueue comparison
    def __lt__(self, other: QueuedTask) -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


class TaskQueue:
    """Per-platform priority queue with rate-limited consumers.

    Each platform gets its own :class:`asyncio.PriorityQueue` and a
    dedicated consumer coroutine that calls
    :meth:`PlatformRateLimiter.wait_and_acquire` before executing the task.
    """

    def __init__(
        self,
        rate_limiters: dict[str, PlatformRateLimiter],
    ) -> None:
        self._rate_limiters = rate_limiters
        self._queues: dict[str, asyncio.PriorityQueue[QueuedTask]] = {}
        self._consumers: dict[str, asyncio.Task[None]] = {}
        self._running: bool = False

        # Pre-create queues for each platform that has a limiter
        for platform_name in rate_limiters:
            self._queues[platform_name] = asyncio.PriorityQueue()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start a consumer coroutine for every platform queue."""
        if self._running:
            return

        self._running = True
        for platform_name in self._queues:
            task = asyncio.create_task(
                self._consumer(platform_name),
                name=f"task-queue-consumer-{platform_name}",
            )
            self._consumers[platform_name] = task
            logger.info("TaskQueue consumer started for %s", platform_name)

    async def stop(self) -> None:
        """Signal consumers to stop and wait for them to drain."""
        if not self._running:
            return

        self._running = False

        # Push a sentinel so blocked .get() calls wake up
        for q in self._queues.values():
            sentinel = QueuedTask(
                priority=999,
                created_at=datetime.now(timezone.utc),
                platform="__stop__",
                action_type="__stop__",
                coroutine_func=_noop,
            )
            await q.put(sentinel)

        # Wait for all consumers to finish (with a timeout)
        if self._consumers:
            await asyncio.gather(
                *self._consumers.values(), return_exceptions=True
            )
            logger.info("All TaskQueue consumers stopped")

        self._consumers.clear()

    # ------------------------------------------------------------------
    # Submitting work
    # ------------------------------------------------------------------

    async def submit(self, task: QueuedTask) -> None:
        """Add a task to the appropriate platform queue.

        If the platform does not have a queue yet, one is created lazily.
        """
        if task.platform not in self._queues:
            self._queues[task.platform] = asyncio.PriorityQueue()
            # Start a consumer if we are running
            if self._running and task.platform in self._rate_limiters:
                consumer = asyncio.create_task(
                    self._consumer(task.platform),
                    name=f"task-queue-consumer-{task.platform}",
                )
                self._consumers[task.platform] = consumer

        await self._queues[task.platform].put(task)
        logger.debug(
            "Task %s submitted to %s queue (priority=%d, action=%s)",
            task.task_id,
            task.platform,
            task.priority,
            task.action_type,
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_queue_sizes(self) -> dict[str, int]:
        """Return current queue depth per platform."""
        return {name: q.qsize() for name, q in self._queues.items()}

    # ------------------------------------------------------------------
    # Consumer loop
    # ------------------------------------------------------------------

    async def _consumer(self, platform: str) -> None:
        """Pull tasks from *platform*'s queue, rate-limit, and execute."""
        queue = self._queues[platform]
        limiter = self._rate_limiters.get(platform)

        while self._running:
            task = await queue.get()

            # Sentinel check
            if task.platform == "__stop__":
                queue.task_done()
                break

            try:
                # Respect rate limits
                if limiter is not None:
                    await limiter.wait_and_acquire(task.action_type)

                # Execute the coroutine
                result = await task.coroutine_func(*task.args, **task.kwargs)

                logger.info(
                    "Task %s completed (platform=%s, action=%s)",
                    task.task_id,
                    task.platform,
                    task.action_type,
                )

                # Success callback
                if task.callback is not None:
                    try:
                        cb_result = task.callback(result)
                        if asyncio.iscoroutine(cb_result):
                            await cb_result
                    except Exception:
                        logger.exception(
                            "Callback failed for task %s", task.task_id
                        )

            except Exception as exc:
                task.retry_count += 1
                if task.retry_count <= task.max_retries:
                    logger.warning(
                        "Task %s failed (attempt %d/%d): %s -- re-queuing",
                        task.task_id,
                        task.retry_count,
                        task.max_retries,
                        exc,
                    )
                    await queue.put(task)
                else:
                    logger.error(
                        "Task %s failed permanently after %d retries: %s",
                        task.task_id,
                        task.max_retries,
                        exc,
                    )
            finally:
                queue.task_done()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


async def _noop() -> None:
    """No-op coroutine used as sentinel task body."""
