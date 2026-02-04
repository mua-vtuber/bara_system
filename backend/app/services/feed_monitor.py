from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.core.constants import ActivityStatus, ActivityType
from app.core.logging import get_logger
from app.core.task_queue import PRIORITY_SCHEDULED, QueuedTask
from app.models.activity import ActivityCreate
from app.models.events import CommentPostedEvent, NewPostDiscoveredEvent

if TYPE_CHECKING:
    from app.core.config import Config
    from app.core.events import EventBus
    from app.core.task_queue import TaskQueue
    from app.platforms.base import PlatformAdapter
    from app.platforms.registry import PlatformRegistry
    from app.repositories.activity import ActivityRepository
    from app.services.strategy import StrategyEngine
    from app.services.activity_mixer import ActivityMixer
    from app.services.memory import MemoryService
    from app.services.mission import MissionService

logger = get_logger(__name__)


class FeedMonitor:
    """Periodically polls enabled platforms for new posts, evaluates them
    through the strategy engine, and enqueues comment tasks when appropriate.
    """

    def __init__(
        self,
        platform_registry: PlatformRegistry,
        config: Config,
        strategy_engine: StrategyEngine,
        activity_repo: ActivityRepository,
        event_bus: EventBus,
        task_queue: TaskQueue,
    ) -> None:
        self._platform_registry = platform_registry
        self._config = config
        self._strategy_engine = strategy_engine
        self._activity_repo = activity_repo
        self._event_bus = event_bus
        self._task_queue = task_queue
        self._memory_service: MemoryService | None = None
        self._activity_mixer: ActivityMixer | None = None
        self._mission_service: MissionService | None = None

    def set_memory_service(self, service: MemoryService) -> None:
        """Inject MemoryService (post-init wiring)."""
        self._memory_service = service

    def set_activity_mixer(self, mixer: ActivityMixer) -> None:
        """Inject ActivityMixer (post-init wiring)."""
        self._activity_mixer = mixer

    def set_mission_service(self, service: MissionService) -> None:
        """Inject MissionService (post-init wiring)."""
        self._mission_service = service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def poll_all_platforms(self) -> None:
        """Poll every enabled platform in parallel."""
        adapters = self._platform_registry.get_enabled_platforms()
        if not adapters:
            logger.debug("No enabled platforms to poll")
            return

        results = await asyncio.gather(
            *(self._poll_platform(adapter) for adapter in adapters),
            return_exceptions=True,
        )

        for adapter, result in zip(adapters, results):
            if isinstance(result, Exception):
                logger.error(
                    "Error polling platform %s: %s",
                    adapter.platform_name,
                    result,
                )

    # ------------------------------------------------------------------
    # Internal: single-platform polling
    # ------------------------------------------------------------------

    async def _poll_platform(self, adapter: PlatformAdapter) -> None:
        platform = adapter.platform_name
        logger.debug("Polling platform: %s", platform)

        try:
            posts = await adapter.get_posts(sort="new", limit=25)
        except Exception as exc:
            logger.error("Failed to fetch posts from %s: %s", platform, exc)
            return

        # Get active missions if mission service is available
        active_missions = []
        if self._mission_service:
            try:
                active_missions = await self._mission_service.get_active_missions()
            except Exception as exc:
                logger.warning("Failed to get active missions: %s", exc)

        for post in posts:
            # Publish discovery event
            await self._event_bus.publish(
                NewPostDiscoveredEvent(
                    platform=platform,
                    post_id=post.post_id,
                    title=post.title or "",
                    author=post.author or "",
                    url=post.url or "",
                )
            )

            # Remember interesting posts
            if self._memory_service:
                try:
                    await self._memory_service.remember_post(post, platform)
                except Exception as exc:
                    logger.debug("Memory save failed: %s", exc)

            # Decide action using ActivityMixer or fallback to original logic
            if self._activity_mixer:
                try:
                    decision = await self._strategy_engine.evaluate_post(
                        post, platform, self._activity_repo
                    )
                except Exception as exc:
                    logger.error(
                        "Strategy evaluation failed for post %s on %s: %s",
                        post.post_id, platform, exc,
                    )
                    continue

                if not decision.should_comment:
                    continue

                action = self._activity_mixer.choose_action(
                    post,
                    await self._build_strategy_context(platform),
                    active_missions,
                )

                if action == "comment":
                    await self._enqueue_comment(adapter, post, platform, decision.priority)
                elif action == "upvote":
                    await self._enqueue_upvote(adapter, post, platform)
                elif action == "warmup" and self._mission_service:
                    related = self._activity_mixer.get_related_mission(
                        post, active_missions
                    )
                    if related:
                        await self._enqueue_warmup(adapter, post, platform, related)
                # "skip" → do nothing

            else:
                # Original logic: evaluate + comment only
                try:
                    decision = await self._strategy_engine.evaluate_post(
                        post, platform, self._activity_repo
                    )
                except Exception as exc:
                    logger.error(
                        "Strategy evaluation failed for post %s on %s: %s",
                        post.post_id, platform, exc,
                    )
                    continue

                if not decision.should_comment:
                    continue

                await self._enqueue_comment(adapter, post, platform, decision.priority)

    # ------------------------------------------------------------------
    # Internal: action helpers
    # ------------------------------------------------------------------

    async def _build_strategy_context(self, platform: str):
        """Build a StrategyContext for ActivityMixer."""
        from datetime import date
        from app.models.activity import DailyCounts, DailyLimits
        from app.services.strategy import StrategyContext

        today = date.today()
        daily_counts = await self._activity_repo.get_daily_counts(platform, today)
        behavior = self._config.behavior
        daily_limits = DailyLimits(
            max_comments=behavior.daily_limits.max_comments,
            max_posts=behavior.daily_limits.max_posts,
            max_upvotes=behavior.daily_limits.max_upvotes,
        )
        active_hours = {
            "weekday": {"start": behavior.active_hours.weekday.start, "end": behavior.active_hours.weekday.end},
            "weekend": {"start": behavior.active_hours.weekend.start, "end": behavior.active_hours.weekend.end},
        }
        return StrategyContext(
            daily_counts=daily_counts,
            daily_limits=daily_limits,
            interest_keywords=behavior.interest_keywords,
            recent_activities=[],
            current_time=datetime.now(),
            active_hours=active_hours,
        )

    async def _enqueue_comment(
        self, adapter: PlatformAdapter, post, platform: str, priority: int
    ) -> None:
        """Generate and enqueue a comment task."""
        try:
            checked = await self._strategy_engine.generate_comment(post, platform)
        except Exception as exc:
            logger.error("Comment generation failed for %s: %s", post.post_id, exc)
            return
        if not checked.passed:
            logger.warning("Comment quality failed for %s: %s", post.post_id, checked.issues)
            return
        task = QueuedTask(
            priority=priority,
            created_at=datetime.now(timezone.utc),
            platform=platform,
            action_type="comment",
            coroutine_func=self._handle_comment_task,
            args=(adapter, post.post_id, checked.content, post.url),
        )
        await self._task_queue.submit(task)
        logger.info("Enqueued comment for %s on %s (pri=%d)", post.post_id, platform, priority)

    async def _enqueue_upvote(
        self, adapter: PlatformAdapter, post, platform: str
    ) -> None:
        """Enqueue an upvote task."""
        task = QueuedTask(
            priority=PRIORITY_SCHEDULED + 2,
            created_at=datetime.now(timezone.utc),
            platform=platform,
            action_type="upvote",
            coroutine_func=self._handle_upvote_task,
            args=(adapter, post.post_id),
        )
        await self._task_queue.submit(task)
        logger.info("Enqueued upvote for %s on %s", post.post_id, platform)

    async def _enqueue_warmup(
        self, adapter: PlatformAdapter, post, platform: str, mission
    ) -> None:
        """Generate and enqueue a warmup comment for a mission."""
        if not self._mission_service:
            return
        try:
            content = await self._mission_service.execute_warmup(mission, post)
        except Exception as exc:
            logger.error("Warmup generation failed: %s", exc)
            return
        if not content:
            return
        task = QueuedTask(
            priority=PRIORITY_SCHEDULED,
            created_at=datetime.now(timezone.utc),
            platform=platform,
            action_type="comment",
            coroutine_func=self._handle_comment_task,
            args=(adapter, post.post_id, content, post.url),
        )
        await self._task_queue.submit(task)
        logger.info("Enqueued warmup comment for mission #%d on %s", mission.id, platform)

    async def _handle_upvote_task(
        self, adapter: PlatformAdapter, post_id: str
    ) -> None:
        """Post an upvote."""
        platform = adapter.platform_name
        try:
            await adapter.upvote(post_id)
            logger.info("Upvoted post %s on %s", post_id, platform)
        except Exception as exc:
            logger.error("Upvote failed for %s on %s: %s", post_id, platform, exc)

    # ------------------------------------------------------------------
    # Internal: comment posting handler
    # ------------------------------------------------------------------

    async def _handle_comment_task(
        self,
        adapter: PlatformAdapter,
        post_id: str,
        comment_content: str,
        post_url: str | None,
    ) -> None:
        """Actually post a comment and record the activity."""
        platform = adapter.platform_name

        # Record pending activity
        activity = await self._activity_repo.add(
            ActivityCreate(
                type=ActivityType.COMMENT,
                platform=platform,
                platform_post_id=post_id,
                bot_response=comment_content,
                url=post_url,
                status=ActivityStatus.PENDING,
            )
        )

        try:
            result = await adapter.create_comment(post_id, comment_content)

            if result.success:
                await self._activity_repo.update_status(
                    activity.id, ActivityStatus.POSTED.value
                )
                await self._event_bus.publish(
                    CommentPostedEvent(
                        platform=platform,
                        activity_id=activity.id,
                        post_id=post_id,
                        comment_id=result.comment_id or "",
                    )
                )
                logger.info(
                    "Comment posted on %s post %s (activity_id=%d)",
                    platform,
                    post_id,
                    activity.id,
                )
            else:
                await self._activity_repo.update_status(
                    activity.id,
                    ActivityStatus.FAILED.value,
                    error_message=result.error,
                )
                logger.warning(
                    "Comment failed on %s post %s: %s",
                    platform,
                    post_id,
                    result.error,
                )
        except Exception as exc:
            await self._activity_repo.update_status(
                activity.id,
                ActivityStatus.FAILED.value,
                error_message=str(exc),
            )
            logger.error(
                "Exception posting comment on %s post %s: %s",
                platform,
                post_id,
                exc,
            )
            raise
