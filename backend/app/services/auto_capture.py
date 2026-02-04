from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from app.core.constants import (
    AUTO_CAPTURE_MAX_PER_INTERACTION,
    AUTO_CAPTURE_MIN_TEXT_LENGTH,
    AUTO_CAPTURE_MAX_TEXT_LENGTH,
    EMBEDDING_CANDIDATE_FETCH_LIMIT,
)
from app.core.logging import get_logger
from app.models.collected_info import CollectedInfoCreate
from app.models.events import BotResponseGeneratedEvent, NotificationReceivedEvent

if TYPE_CHECKING:
    from app.repositories.collected_info import CollectedInfoRepository
    from app.services.embedding import EmbeddingService

logger = get_logger(__name__)

# Korean trigger patterns: (pattern, category)
_TRIGGER_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"기억해\s*줘|기억해\s*주|기억해\s*달|잊지\s*마"), "preference"),
    (re.compile(r"좋아해|좋아하는|싫어해|싫어하는|좋아함|싫어함"), "preference"),
    (re.compile(r"나는\s+.{2,20}(이야|입니다|이에요|인데|거든)"), "fact"),
    (re.compile(r"결정했|결심했|결정함|하기로\s*했"), "decision"),
    (re.compile(r"앞으로\s+.{2,30}(할|하겠|할게|할거)"), "decision"),
    (re.compile(r"https?://\S+"), "entity"),
    (re.compile(r"@\w+"), "entity"),
]


class AutoCaptureService:
    """Automatically captures memory-worthy content from bot interactions.

    Listens to BotResponseGeneratedEvent and NotificationReceivedEvent,
    extracts relevant segments using Korean trigger patterns, and stores
    them in collected_info with optional embedding for deduplication.
    """

    def __init__(
        self,
        collected_info_repo: CollectedInfoRepository,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self._info_repo = collected_info_repo
        self._embedding = embedding_service

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_bot_response(self, event: object) -> None:
        """Handle BotResponseGeneratedEvent — scan original content for triggers."""
        if not isinstance(event, BotResponseGeneratedEvent):
            return

        texts_to_scan = [event.original_content, event.bot_response]
        captured = 0

        for text in texts_to_scan:
            if captured >= AUTO_CAPTURE_MAX_PER_INTERACTION:
                break

            matches = self._find_triggers(text)
            for segment, category in matches:
                if captured >= AUTO_CAPTURE_MAX_PER_INTERACTION:
                    break

                stored = await self._store_if_unique(
                    content=segment,
                    category=f"auto_{category}",
                    platform=event.platform,
                    author=event.author,
                )
                if stored:
                    captured += 1
                    logger.debug(
                        "Auto-captured [%s] from %s: %.50s...",
                        category,
                        event.platform,
                        segment,
                    )

    async def on_notification_for_capture(self, event: object) -> None:
        """Handle NotificationReceivedEvent — check notification content for triggers."""
        if not isinstance(event, NotificationReceivedEvent):
            return

        # Notifications have limited content, but we can still check
        text = getattr(event, "content_preview", "") or ""
        if not text:
            return

        matches = self._find_triggers(text)
        for segment, category in matches[:AUTO_CAPTURE_MAX_PER_INTERACTION]:
            await self._store_if_unique(
                content=segment,
                category=f"auto_{category}",
                platform=event.platform,
                author=event.actor_name,
            )

    # ------------------------------------------------------------------
    # Internal: pattern matching
    # ------------------------------------------------------------------

    def _find_triggers(self, text: str) -> list[tuple[str, str]]:
        """Find all trigger pattern matches in text, return (segment, category) pairs."""
        if not self._passes_filters(text):
            return []

        results: list[tuple[str, str]] = []
        seen_segments: set[str] = set()

        for pattern, category in _TRIGGER_PATTERNS:
            for match in pattern.finditer(text):
                segment = self._extract_segment(text, match.start(), match.end())
                if segment and segment not in seen_segments:
                    seen_segments.add(segment)
                    results.append((segment, category))

        return results

    @staticmethod
    def _passes_filters(text: str) -> bool:
        """Check if text is worth scanning (length, not bot-generated format)."""
        if not text:
            return False
        stripped = text.strip()
        if len(stripped) < AUTO_CAPTURE_MIN_TEXT_LENGTH:
            return False
        if len(stripped) > AUTO_CAPTURE_MAX_TEXT_LENGTH * 2:
            # Still scan, but we'll extract segments
            pass
        # Skip obvious bot-generated formatting
        if stripped.startswith("```") or stripped.startswith("---"):
            return False
        return True

    @staticmethod
    def _extract_segment(text: str, start: int, end: int) -> str:
        """Extract the sentence containing the match."""
        # Find sentence boundaries (Korean period, question mark, or newline)
        sentence_start = start
        for i in range(start - 1, max(start - 200, -1), -1):
            if i < 0:
                sentence_start = 0
                break
            if text[i] in ".!?\n":
                sentence_start = i + 1
                break
        else:
            sentence_start = max(0, start - 200)

        sentence_end = end
        for i in range(end, min(end + 200, len(text))):
            if text[i] in ".!?\n":
                sentence_end = i + 1
                break
        else:
            sentence_end = min(len(text), end + 200)

        segment = text[sentence_start:sentence_end].strip()

        # Enforce length limits
        if len(segment) < AUTO_CAPTURE_MIN_TEXT_LENGTH:
            return ""
        if len(segment) > AUTO_CAPTURE_MAX_TEXT_LENGTH:
            segment = segment[:AUTO_CAPTURE_MAX_TEXT_LENGTH]

        return segment

    # ------------------------------------------------------------------
    # Internal: store with deduplication
    # ------------------------------------------------------------------

    async def _store_if_unique(
        self,
        content: str,
        category: str,
        platform: str,
        author: str,
    ) -> bool:
        """Store content if it's not a near-duplicate of existing entries."""
        # Check embedding-based deduplication if available
        if self._embedding and self._embedding.enabled:
            try:
                candidates = await self._info_repo.get_embedding_candidates(
                    limit=EMBEDDING_CANDIDATE_FETCH_LIMIT,
                    category=category,
                )
                if candidates:
                    is_dup = await self._embedding.is_duplicate(
                        content, candidates
                    )
                    if is_dup:
                        logger.debug("Skipped duplicate auto-capture: %.50s...", content)
                        return False
            except Exception as exc:
                logger.warning("Dedup check failed, storing anyway: %s", exc)

        # Generate embedding for the new content
        embedding_blob: bytes | None = None
        if self._embedding and self._embedding.enabled:
            try:
                vec = await self._embedding.embed_text(content)
                if vec is not None:
                    embedding_blob = self._embedding.vector_to_blob(vec)
            except Exception as exc:
                logger.warning("Failed to embed auto-captured content: %s", exc)

        try:
            await self._info_repo.add(
                CollectedInfoCreate(
                    platform=platform,
                    author=author,
                    category=category,
                    title="",
                    content=content,
                    source_url="",
                    tags=None,
                    embedding=embedding_blob,
                )
            )
            return True
        except Exception as exc:
            logger.warning("Failed to store auto-captured content: %s", exc)
            return False
