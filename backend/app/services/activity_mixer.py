from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from app.core.config import Config
from app.core.constants import (
    ACTIVITY_WEIGHT_COMMENT,
    ACTIVITY_WEIGHT_POST,
    ACTIVITY_WEIGHT_SKIP,
    ACTIVITY_WEIGHT_UPVOTE,
)
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.models.mission import Mission
    from app.models.platform import PlatformPost
    from app.services.strategy import StrategyContext

logger = get_logger(__name__)


class ActivityMixer:
    """Probabilistically selects bot actions for feed posts.

    Instead of always commenting, the bot now chooses between:
    - comment: Engage with the post (50% base)
    - upvote: Just upvote without commenting (30% base)
    - skip: Lurk / pass without acting (10% base)
    - warmup: Mission-related warmup comment (10% base, increases for related posts)

    This creates more natural-looking activity patterns.
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Action selection
    # ------------------------------------------------------------------

    def choose_action(
        self,
        post: PlatformPost,
        context: StrategyContext,
        active_missions: list[Mission] | None = None,
    ) -> str:
        """Choose an action for a feed post.

        Returns one of: "comment", "upvote", "skip", "warmup"
        """
        weights = self._calculate_weights(post, context, active_missions)

        actions = list(weights.keys())
        probs = list(weights.values())

        # Normalize
        total = sum(probs)
        if total <= 0:
            return "skip"
        probs = [p / total for p in probs]

        chosen = random.choices(actions, weights=probs, k=1)[0]  # noqa: S311

        logger.debug(
            "ActivityMixer chose '%s' for post '%s' (weights: %s)",
            chosen,
            (post.title or "")[:30],
            {k: f"{v:.2f}" for k, v in weights.items()},
        )

        return chosen

    def should_proactive_post(
        self,
        context: StrategyContext,
        active_missions: list[Mission] | None = None,
    ) -> dict | None:
        """Decide whether to make a proactive post.

        Returns {"type": "interest"|"mission", "topic": str, "mission_id": int|None}
        or None if no post should be made.
        """
        # Check daily limit
        if context.daily_counts.posts >= context.daily_limits.max_posts:
            return None

        # Random chance (low probability per check)
        if random.random() > 0.15:  # noqa: S311
            return None

        # Check for active missions that need posting
        if active_missions:
            from app.models.mission import MissionStatus
            active_ready = [
                m for m in active_missions
                if m.status == MissionStatus.ACTIVE
            ]
            if active_ready:
                mission = active_ready[0]
                return {
                    "type": "mission",
                    "topic": mission.topic,
                    "mission_id": mission.id,
                }

        # Interest-based proactive post
        interests = list(self._config.personality.interests)
        if not interests:
            interests = list(self._config.behavior.interest_keywords)

        if interests:
            topic = random.choice(interests)  # noqa: S311
            return {
                "type": "interest",
                "topic": topic,
                "mission_id": None,
            }

        return None

    # ------------------------------------------------------------------
    # Weight calculation
    # ------------------------------------------------------------------

    def _calculate_weights(
        self,
        post: PlatformPost,
        context: StrategyContext,
        active_missions: list[Mission] | None = None,
    ) -> dict[str, float]:
        """Calculate action weights based on context."""
        weights = {
            "comment": ACTIVITY_WEIGHT_COMMENT,
            "upvote": ACTIVITY_WEIGHT_UPVOTE,
            "skip": ACTIVITY_WEIGHT_SKIP,
            "warmup": 0.0,
        }

        # Approaching daily comment limit → reduce comment, increase skip
        if context.daily_limits.max_comments > 0:
            comment_ratio = (
                context.daily_counts.comments / context.daily_limits.max_comments
            )
            if comment_ratio > 0.8:
                weights["comment"] *= 0.3
                weights["skip"] += 0.3
            elif comment_ratio > 0.5:
                weights["comment"] *= 0.7

        # Approaching upvote limit → reduce upvote
        if context.daily_limits.max_upvotes > 0:
            upvote_ratio = (
                context.daily_counts.upvotes / context.daily_limits.max_upvotes
            )
            if upvote_ratio > 0.8:
                weights["upvote"] *= 0.3

        # Mission warmup: boost warmup weight for related posts
        if active_missions:
            related_mission = self._find_related_mission(
                post, active_missions
            )
            if related_mission is not None:
                from app.models.mission import MissionStatus
                if related_mission.status == MissionStatus.WARMUP:
                    weights["warmup"] = ACTIVITY_WEIGHT_COMMENT * 0.8
                    # Reduce other weights slightly
                    weights["comment"] *= 0.5
                    weights["upvote"] *= 0.7

        # Remove warmup if weight is 0
        if weights["warmup"] <= 0:
            del weights["warmup"]

        return weights

    def _find_related_mission(
        self,
        post: PlatformPost,
        missions: list[Mission],
    ) -> Optional[Mission]:
        """Find a mission whose topic relates to the post content."""
        text = f"{post.title or ''} {post.content or ''}".lower()
        if not text.strip():
            return None

        for mission in missions:
            topic_words = mission.topic.lower().split()
            if any(word in text for word in topic_words if len(word) >= 2):
                return mission

        return None

    def get_related_mission(
        self,
        post: PlatformPost,
        missions: list[Mission],
    ) -> Optional[Mission]:
        """Public wrapper for finding related missions."""
        return self._find_related_mission(post, missions)
