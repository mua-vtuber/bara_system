from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.core.logging import get_logger
from app.models.good_example import GoodExampleCreate

if TYPE_CHECKING:
    from app.platforms.registry import PlatformRegistry
    from app.repositories.activity import ActivityRepository
    from app.repositories.good_example import GoodExampleRepository
    from app.services.embedding import EmbeddingService

logger = get_logger(__name__)

# Engagement scoring weights
_UPVOTE_WEIGHT: float = 1.0
_REPLY_WEIGHT: float = 2.0
_MIN_ENGAGEMENT_SCORE: float = 2.0
_MIN_REPLY_COUNT: int = 1


class ExampleEvaluatorService:
    """Evaluates recent bot activities for high-engagement responses.

    Periodically checks posted activities to see if they received
    good engagement (upvotes, replies). High-engagement responses
    are stored as good_examples for few-shot learning.

    Designed to be called by the scheduler every ~1 hour.
    """

    def __init__(
        self,
        activity_repo: ActivityRepository,
        example_repo: GoodExampleRepository,
        platform_registry: PlatformRegistry,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self._activity_repo = activity_repo
        self._example_repo = example_repo
        self._platform_registry = platform_registry
        self._embedding = embedding_service

    async def evaluate_recent_activities(self) -> int:
        """Evaluate recent posted activities for engagement.

        Returns the number of new good examples stored.
        """
        stored_count = 0

        # Check recent activities across all platforms
        for platform_name in ("moltbook", "botmadang"):
            try:
                adapter = self._platform_registry.get_adapter(platform_name)
                if adapter is None:
                    continue
            except Exception:
                continue

            try:
                activities = await self._activity_repo.get_timeline(
                    platform_filter=platform_name,
                    limit=50,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to fetch activities for %s: %s", platform_name, exc
                )
                continue

            for activity in activities:
                if activity.status != "posted":
                    continue
                if activity.action_type not in ("comment", "reply", "post"):
                    continue
                if not activity.platform_post_id:
                    continue

                # Skip if already evaluated
                try:
                    if await self._example_repo.exists_for_activity(activity.id):
                        continue
                except Exception:
                    continue

                # Check engagement on the platform
                try:
                    result = await self._check_engagement(
                        adapter, activity, platform_name
                    )
                    if result:
                        stored_count += 1
                except Exception as exc:
                    logger.debug(
                        "Engagement check failed for activity %d: %s",
                        activity.id,
                        exc,
                    )

        if stored_count > 0:
            logger.info("Stored %d new good examples", stored_count)

        return stored_count

    async def _check_engagement(
        self,
        adapter: object,
        activity: object,
        platform_name: str,
    ) -> bool:
        """Check if an activity received good engagement and store if so."""
        post_id = activity.platform_post_id

        # Get current post stats from platform
        try:
            post = await adapter.get_post(post_id)
        except Exception:
            return False

        if post is None:
            return False

        # Count replies to our comment/post
        reply_count = 0
        upvote_count = getattr(post, "upvote_count", 0) or 0

        try:
            comments = await adapter.get_comments(post_id)
            # Count comments that came after our activity
            bot_name = ""
            try:
                from app.core.config import Config
                bot_name = Config.get_instance().bot.name
            except Exception:
                pass

            # Simple heuristic: count comments not by us
            reply_count = sum(
                1 for c in (comments or [])
                if getattr(c, "author", "") != bot_name
            )
        except Exception:
            pass

        # Calculate engagement score
        engagement_score = (
            upvote_count * _UPVOTE_WEIGHT + reply_count * _REPLY_WEIGHT
        )

        # Check if it meets the threshold
        if engagement_score < _MIN_ENGAGEMENT_SCORE and reply_count < _MIN_REPLY_COUNT:
            return False

        # Generate embedding for the response
        embedding_blob: bytes | None = None
        if self._embedding and self._embedding.enabled:
            try:
                vec = await self._embedding.embed_text(activity.content or "")
                if vec is not None:
                    embedding_blob = self._embedding.vector_to_blob(vec)
            except Exception:
                pass

        # Store as good example
        try:
            await self._example_repo.add(
                GoodExampleCreate(
                    platform=platform_name,
                    action_type=activity.action_type,
                    context_title=post.title or "",
                    context_content=(post.content or "")[:500],
                    bot_response=(activity.content or "")[:1000],
                    engagement_score=engagement_score,
                    reply_count=reply_count,
                    upvote_count=upvote_count,
                    activity_id=activity.id,
                    post_id=post_id,
                    embedding=embedding_blob,
                )
            )
            logger.debug(
                "Stored good example from activity %d (score=%.1f, replies=%d)",
                activity.id,
                engagement_score,
                reply_count,
            )
            return True
        except Exception as exc:
            logger.warning("Failed to store good example: %s", exc)
            return False
