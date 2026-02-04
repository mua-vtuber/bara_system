from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import Config
from app.core.logging import get_logger
from app.models.collected_info import CollectedInfo, CollectedInfoCreate
from app.models.memory import BotMemory, BotMemoryCreate
from app.repositories.collected_info import CollectedInfoRepository
from app.repositories.memory import BotMemoryRepository

if TYPE_CHECKING:
    from app.models.platform import PlatformPost

logger = get_logger(__name__)


class MemoryService:
    """Manages the bot's memory of interactions and interesting content.

    Provides:
    - Automatic recording of interesting posts (via interest keyword matching)
    - Tracking interactions with other bots
    - Querying related memories for context injection
    """

    def __init__(
        self,
        memory_repo: BotMemoryRepository,
        collected_info_repo: CollectedInfoRepository,
        config: Config,
    ) -> None:
        self._memory_repo = memory_repo
        self._info_repo = collected_info_repo
        self._config = config

    # ------------------------------------------------------------------
    # Record methods (called by event handlers or directly)
    # ------------------------------------------------------------------

    async def remember_post(self, post: PlatformPost, platform: str) -> bool:
        """Save an interesting post to collected_info.

        Returns True if the post was saved (matched interests).
        """
        if not self._is_interesting(post):
            return False

        try:
            tags = self._extract_topic_tags(post)
            await self._info_repo.add(
                CollectedInfoCreate(
                    platform=platform,
                    author=post.author,
                    category="auto_collected",
                    title=post.title or "",
                    content=(post.content or "")[:2000],
                    source_url=post.url or "",
                    tags=",".join(tags) if tags else None,
                )
            )
            logger.debug(
                "Remembered post '%s' from %s on %s",
                (post.title or "")[:50],
                post.author,
                platform,
            )
            return True
        except Exception as exc:
            logger.warning("Failed to remember post: %s", exc)
            return False

    async def remember_interaction(
        self,
        platform: str,
        entity_name: str,
        context: str = "",
        topic_hints: list[str] | None = None,
    ) -> None:
        """Record an interaction with another bot/user."""
        try:
            await self._memory_repo.add_or_update(
                BotMemoryCreate(
                    platform=platform,
                    entity_name=entity_name,
                    entity_type="bot",
                    topics=topic_hints or [],
                    relationship_notes="",
                )
            )
            logger.debug(
                "Recorded interaction with %s on %s", entity_name, platform
            )
        except Exception as exc:
            logger.warning("Failed to record interaction: %s", exc)

    # ------------------------------------------------------------------
    # Query methods (used by PromptBuilder and other services)
    # ------------------------------------------------------------------

    async def recall_related(
        self,
        topic: str,
        platform: str = "",
        limit: int = 5,
    ) -> list[CollectedInfo]:
        """Find collected info related to a topic."""
        try:
            results = await self._info_repo.search(
                query=topic, limit=limit
            )
            return results
        except Exception as exc:
            logger.warning("Failed to recall related info: %s", exc)
            return []

    async def recall_bot(
        self, platform: str, entity_name: str
    ) -> BotMemory | None:
        """Get memory about a specific bot."""
        try:
            return await self._memory_repo.get_by_name(platform, entity_name)
        except Exception as exc:
            logger.warning("Failed to recall bot %s: %s", entity_name, exc)
            return None

    async def get_context_for_post(
        self, post: PlatformPost, platform: str
    ) -> dict:
        """Build full context for a post: related memories + author memory.

        Returns dict with keys: 'memories' (list[BotMemory]),
        'related_info' (list[CollectedInfo])
        """
        memories: list[BotMemory] = []
        related_info: list[CollectedInfo] = []

        # Get memory about the post author
        if post.author:
            author_mem = await self.recall_bot(platform, post.author)
            if author_mem:
                memories.append(author_mem)

        # Get related collected info
        topic_text = f"{post.title or ''} {post.content or ''}"[:200]
        if topic_text.strip():
            keywords = self._get_all_interests()
            matching_keywords = [
                kw for kw in keywords
                if kw.lower() in topic_text.lower()
            ]
            if matching_keywords:
                related_info = await self.recall_related(
                    matching_keywords[0], platform, limit=3
                )

        return {"memories": memories, "related_info": related_info}

    async def get_frequent_contacts(
        self, platform: str, limit: int = 10
    ) -> list[BotMemory]:
        """Get the most frequently interacted-with bots."""
        return await self._memory_repo.get_frequent_contacts(platform, limit)

    async def find_bots_by_topic(
        self, topic: str, limit: int = 10
    ) -> list[BotMemory]:
        """Find bots associated with a topic."""
        return await self._memory_repo.get_by_topic(topic, limit)

    # ------------------------------------------------------------------
    # Event handlers (for EventBus subscription)
    # ------------------------------------------------------------------

    async def on_new_post(self, event: object) -> None:
        """Handle NewPostDiscoveredEvent."""
        from app.models.events import NewPostDiscoveredEvent
        from app.models.platform import PlatformPost

        if not isinstance(event, NewPostDiscoveredEvent):
            return

        post = PlatformPost(
            post_id=event.post_id,
            title=event.title,
            author=event.author,
            url=event.url,
        )
        await self.remember_post(post, event.platform)

    async def on_comment_posted(self, event: object) -> None:
        """Handle CommentPostedEvent — record that we interacted on a post."""
        from app.models.events import CommentPostedEvent

        if not isinstance(event, CommentPostedEvent):
            return

        # We don't have the author name from the event, but we record
        # the platform interaction
        logger.debug(
            "Comment posted on %s post %s", event.platform, event.post_id
        )

    async def on_notification(self, event: object) -> None:
        """Handle NotificationReceivedEvent — remember who interacted with us."""
        from app.models.events import NotificationReceivedEvent

        if not isinstance(event, NotificationReceivedEvent):
            return

        if event.actor_name:
            await self.remember_interaction(
                platform=event.platform,
                entity_name=event.actor_name,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_all_interests(self) -> list[str]:
        """Combine behavior.interest_keywords + personality.interests."""
        keywords = list(self._config.behavior.interest_keywords)
        keywords.extend(self._config.personality.interests)
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for kw in keywords:
            lower = kw.lower()
            if lower not in seen:
                seen.add(lower)
                unique.append(kw)
        return unique

    def _is_interesting(self, post: PlatformPost) -> bool:
        """Check if a post matches any interest keywords."""
        text = f"{post.title or ''} {post.content or ''}".lower()
        if not text.strip():
            return False

        keywords = self._get_all_interests()
        return any(kw.lower() in text for kw in keywords)

    def _extract_topic_tags(self, post: PlatformPost) -> list[str]:
        """Extract matching interest keywords as tags from a post."""
        text = f"{post.title or ''} {post.content or ''}".lower()
        keywords = self._get_all_interests()
        return [kw for kw in keywords if kw.lower() in text][:5]
