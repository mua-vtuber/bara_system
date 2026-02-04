from __future__ import annotations

import random
from typing import TYPE_CHECKING

from app.core.config import Config
from app.core.logging import get_logger
from app.models.events import MissionResponseReceivedEvent
from app.models.mission import MissionStatus

if TYPE_CHECKING:
    from app.core.events import EventBus
    from app.platforms.registry import PlatformRegistry
    from app.services.memory import MemoryService
    from app.services.mission import MissionService

logger = get_logger(__name__)


class ResponseCollector:
    """Collects and processes responses to the bot's mission posts.

    Called periodically by the scheduler to check for new comments
    on posts the bot published as part of missions.
    """

    def __init__(
        self,
        mission_service: MissionService,
        memory_service: MemoryService,
        platform_registry: PlatformRegistry,
        event_bus: EventBus,
        config: Config,
    ) -> None:
        self._missions = mission_service
        self._memory = memory_service
        self._platforms = platform_registry
        self._event_bus = event_bus
        self._config = config

    # ------------------------------------------------------------------
    # Main check loop (called by scheduler)
    # ------------------------------------------------------------------

    async def check_all_active_posts(self) -> None:
        """Check all collecting/posted missions for new responses."""
        active = await self._missions.get_active_missions()

        missions_to_check = [
            m for m in active
            if m.status in (MissionStatus.POSTED, MissionStatus.COLLECTING)
            and m.post_id
            and m.post_platform
        ]

        if not missions_to_check:
            return

        logger.debug(
            "Checking %d mission posts for new responses",
            len(missions_to_check),
        )

        for mission in missions_to_check:
            try:
                await self._check_mission_responses(mission)
            except Exception as exc:
                logger.error(
                    "Error checking responses for mission #%d: %s",
                    mission.id,
                    exc,
                )

    # ------------------------------------------------------------------
    # Per-mission check
    # ------------------------------------------------------------------

    async def _check_mission_responses(self, mission: object) -> None:
        """Check a single mission's post for new comments."""
        from app.models.mission import Mission

        if not isinstance(mission, Mission):
            return

        try:
            adapter = self._platforms.get_adapter(mission.post_platform)
        except KeyError:
            logger.warning(
                "Platform '%s' not available for mission #%d",
                mission.post_platform,
                mission.id,
            )
            return

        try:
            comments = await adapter.get_comments(mission.post_id)
        except Exception as exc:
            logger.warning(
                "Failed to fetch comments for mission #%d post %s: %s",
                mission.id,
                mission.post_id,
                exc,
            )
            return

        # Filter out already-collected responses
        existing_ids = {
            r.get("comment_id")
            for r in (mission.collected_responses or [])
            if r.get("comment_id")
        }

        # Also filter out our own bot's comments
        bot_name = self._config.bot.name

        new_comments = [
            c for c in comments
            if c.comment_id not in existing_ids
            and c.author != bot_name
            and c.content
        ]

        if not new_comments:
            return

        logger.info(
            "Mission #%d: found %d new responses",
            mission.id,
            len(new_comments),
        )

        for comment in new_comments:
            await self._process_response(mission, comment)

        # Advance mission state if needed (posted -> collecting)
        if mission.status == MissionStatus.POSTED:
            await self._missions.advance_mission(mission)

        # Check if mission should complete
        updated = await self._missions.get_mission(mission.id)
        if updated and await self._missions.should_complete(updated):
            await self._missions.complete_mission(updated)

    async def _process_response(
        self, mission: object, comment: object
    ) -> None:
        """Process a single new response."""
        from app.models.mission import Mission
        from app.models.platform import PlatformComment

        if not isinstance(mission, Mission) or not isinstance(comment, PlatformComment):
            return

        # Build response dict
        response_data = {
            "comment_id": comment.comment_id,
            "author": comment.author or "unknown",
            "content": comment.content or "",
            "platform": mission.post_platform,
        }

        # Save to mission
        await self._missions.add_response(mission.id, response_data)

        # Remember the responder
        if comment.author:
            topic_hints = mission.topic.split()[:3]
            await self._memory.remember_interaction(
                platform=mission.post_platform,
                entity_name=comment.author,
                context=f"mission_response:{mission.topic}",
                topic_hints=topic_hints,
            )

        # Publish event
        content_preview = (comment.content or "")[:100]
        await self._event_bus.publish(
            MissionResponseReceivedEvent(
                mission_id=mission.id,
                platform=mission.post_platform,
                responder=comment.author or "unknown",
                content_preview=content_preview,
            )
        )

        # Optionally generate a follow-up response (not every time)
        if self._should_followup(mission, comment):
            followup = await self._missions.generate_followup(
                mission, response_data
            )
            if followup:
                try:
                    adapter = self._platforms.get_adapter(mission.post_platform)
                    await adapter.create_comment(
                        post_id=mission.post_id,
                        content=followup,
                        parent_comment_id=comment.comment_id,
                    )
                    logger.info(
                        "Posted follow-up to %s on mission #%d",
                        comment.author,
                        mission.id,
                    )
                except Exception as exc:
                    logger.warning("Failed to post follow-up: %s", exc)

    @staticmethod
    def _should_followup(mission: object, comment: object) -> bool:
        """Decide whether to generate a follow-up for this response.

        Not every response gets a follow-up — that would look unnatural.
        """
        from app.models.platform import PlatformComment

        if not isinstance(comment, PlatformComment):
            return False

        content = comment.content or ""

        # Follow up on substantial responses (more than 50 chars)
        if len(content) < 50:
            return False

        # ~40% chance for substantial responses
        return random.random() < 0.4  # noqa: S311
