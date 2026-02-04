from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.core.constants import ActivityStatus, ActivityType
from app.core.logging import get_logger
from app.core.task_queue import PRIORITY_NOTIFICATION_REPLY, QueuedTask
from app.models.activity import ActivityCreate
from app.models.events import CommentPostedEvent, NotificationReceivedEvent
from app.models.notification import NotificationCreate

if TYPE_CHECKING:
    from app.core.config import Config
    from app.core.events import EventBus
    from app.core.task_queue import TaskQueue
    from app.platforms.base import PlatformAdapter
    from app.platforms.registry import PlatformRegistry
    from app.repositories.activity import ActivityRepository
    from app.repositories.notification import NotificationRepository
    from app.services.strategy import StrategyEngine

logger = get_logger(__name__)

# Notification types that warrant an automated reply
_REPLY_TYPES = {"comment_on_post", "reply_to_comment"}


class NotificationService:
    """Polls platform notifications, persists them, and enqueues reply tasks
    for comment/reply-type notifications.
    """

    def __init__(
        self,
        platform_registry: PlatformRegistry,
        notification_repo: NotificationRepository,
        activity_repo: ActivityRepository,
        strategy_engine: StrategyEngine,
        event_bus: EventBus,
        task_queue: TaskQueue,
    ) -> None:
        self._platform_registry = platform_registry
        self._notification_repo = notification_repo
        self._activity_repo = activity_repo
        self._strategy_engine = strategy_engine
        self._event_bus = event_bus
        self._task_queue = task_queue

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def poll_notifications(self) -> None:
        """Poll notifications from all enabled platforms."""
        adapters = self._platform_registry.get_enabled_platforms()
        if not adapters:
            return

        results = await asyncio.gather(
            *(self._poll_platform(adapter) for adapter in adapters),
            return_exceptions=True,
        )

        for adapter, result in zip(adapters, results):
            if isinstance(result, Exception):
                logger.error(
                    "Error polling notifications on %s: %s",
                    adapter.platform_name,
                    result,
                )

    # ------------------------------------------------------------------
    # Internal: single-platform polling
    # ------------------------------------------------------------------

    async def _poll_platform(self, adapter: PlatformAdapter) -> None:
        platform = adapter.platform_name
        logger.debug("Polling notifications for %s", platform)

        try:
            notifications = await adapter.get_notifications(unread_only=True)
        except Exception as exc:
            logger.error(
                "Failed to fetch notifications from %s: %s", platform, exc
            )
            return

        for notif in notifications:
            # Dedup check
            already_exists = await self._notification_repo.exists_by_platform_id(
                platform, notif.notification_id
            )
            if already_exists:
                continue

            # Persist
            log_entry = await self._notification_repo.add(
                NotificationCreate(
                    platform=platform,
                    notification_id=notif.notification_id,
                    notification_type=notif.notification_type,
                    actor_name=notif.actor_name,
                    post_id=notif.post_id,
                )
            )

            # Publish event
            await self._event_bus.publish(
                NotificationReceivedEvent(
                    platform=platform,
                    notification_id=notif.notification_id,
                    notification_type=notif.notification_type,
                    actor_name=notif.actor_name or "",
                    post_id=notif.post_id or "",
                )
            )

            # Enqueue reply task for reply-worthy notifications
            if notif.notification_type in _REPLY_TYPES and notif.post_id:
                task = QueuedTask(
                    priority=PRIORITY_NOTIFICATION_REPLY,
                    created_at=datetime.now(timezone.utc),
                    platform=platform,
                    action_type="reply",
                    coroutine_func=self._handle_reply_task,
                    args=(adapter, notif, log_entry.id),
                )
                await self._task_queue.submit(task)
                logger.info(
                    "Enqueued reply task for notification %s on %s",
                    notif.notification_id,
                    platform,
                )

    # ------------------------------------------------------------------
    # Internal: reply handler
    # ------------------------------------------------------------------

    async def _handle_reply_task(
        self,
        adapter: PlatformAdapter,
        notification: object,
        log_id: int,
    ) -> None:
        """Generate and post a reply to a notification."""
        from app.models.platform import PlatformNotification

        notif: PlatformNotification = notification  # type: ignore[assignment]
        platform = adapter.platform_name

        # Fetch original post and conversation context
        try:
            original_post = await adapter.get_post_detail(notif.post_id or "")
            conversation = await adapter.get_comments(notif.post_id or "")
        except Exception as exc:
            logger.error(
                "Failed to load context for reply on %s: %s", platform, exc
            )
            return

        # Generate reply
        try:
            checked_reply = await self._strategy_engine.generate_reply(
                notif, original_post, conversation
            )
        except Exception as exc:
            logger.error("Reply generation failed on %s: %s", platform, exc)
            return

        if not checked_reply.passed:
            logger.warning(
                "Reply quality check failed on %s: %s",
                platform,
                checked_reply.issues,
            )
            return

        # Record pending activity
        activity = await self._activity_repo.add(
            ActivityCreate(
                type=ActivityType.REPLY,
                platform=platform,
                platform_post_id=notif.post_id,
                platform_comment_id=notif.comment_id,
                bot_response=checked_reply.content,
                original_content=notif.content_preview,
                status=ActivityStatus.PENDING,
            )
        )

        # Post the reply
        try:
            parent_comment_id = notif.comment_id if notif.comment_id else None
            result = await adapter.create_comment(
                notif.post_id or "",
                checked_reply.content,
                parent_comment_id=parent_comment_id,
            )

            if result.success:
                await self._activity_repo.update_status(
                    activity.id, ActivityStatus.POSTED.value
                )
                await self._notification_repo.mark_responded(
                    log_id, activity.id
                )
                await self._event_bus.publish(
                    CommentPostedEvent(
                        platform=platform,
                        activity_id=activity.id,
                        post_id=notif.post_id or "",
                        comment_id=result.comment_id or "",
                    )
                )
                logger.info(
                    "Reply posted on %s for notification %s (activity_id=%d)",
                    platform,
                    notif.notification_id,
                    activity.id,
                )
            else:
                await self._activity_repo.update_status(
                    activity.id,
                    ActivityStatus.FAILED.value,
                    error_message=result.error,
                )
                logger.warning(
                    "Reply failed on %s: %s", platform, result.error
                )
        except Exception as exc:
            await self._activity_repo.update_status(
                activity.id,
                ActivityStatus.FAILED.value,
                error_message=str(exc),
            )
            logger.error(
                "Exception posting reply on %s: %s", platform, exc
            )
            raise
