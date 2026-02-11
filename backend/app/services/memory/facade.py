"""MemoryFacade: top-level coordinator for the redesigned memory system.

Integrates all memory subsystems (retriever, extractor, evolver, reflector,
context assembler) behind a single interface. Provides backward-compatible
API methods that mirror the original MemoryService, plus new enhanced APIs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from app.core.logging import get_logger
from app.models.memory import (
    EntityProfile,
    EntityProfileCreate,
    KnowledgeNodeCreate,
    MemoryType,
    RetrievalResult,
    SourceType,
)
from app.services.memory.context_assembler import AssembledContext, ContextAssembler
from app.services.memory.evolver import MemoryEvolver
from app.services.memory.extractor import MemoryExtractor
from app.services.memory.reflector import ReflectionEngine
from app.services.memory.retriever import HybridRetriever

if TYPE_CHECKING:
    from app.core.config import Config
    from app.repositories.memory_store import MemoryStoreRepository
    from app.services.embedding import EmbeddingService
    from app.services.llm import LLMService

logger = get_logger(__name__)


class MemoryFacade:
    """Unified interface for the knowledge-graph memory system.

    Coordinates retrieval, extraction, evolution, reflection, and
    context assembly. Acts as the single entry point for all memory
    operations in the application.
    """

    def __init__(
        self,
        config: Config,
        store: MemoryStoreRepository,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
    ) -> None:
        self._config = config
        self._memory_config = config.memory
        self._store = store
        self._embedding = embedding_service
        self._llm = llm_service

        # Sub-components (lazily described but eagerly initialized)
        self._retriever = HybridRetriever(store, embedding_service, self._memory_config)
        self._extractor = MemoryExtractor(llm_service, store, embedding_service, self._memory_config)
        self._evolver = MemoryEvolver(store, embedding_service, self._memory_config)
        self._reflector = ReflectionEngine(llm_service, store, embedding_service, self._memory_config)
        self._assembler = ContextAssembler(self._memory_config)

        # Session tracking
        self._current_session_id: int | None = None

    # ==================================================================
    # Session management
    # ==================================================================

    async def start_session(self, platform: str = "chat") -> int:
        """Start a new memory session for episode tracking."""
        self._current_session_id = await self._store.start_session(platform)
        logger.debug("Memory session started: %d", self._current_session_id)
        return self._current_session_id

    async def end_session(self, summary: str = "", topic: str = "") -> None:
        """End the current session and run consolidation."""
        if self._current_session_id is not None:
            await self._store.end_session(
                self._current_session_id, summary=summary, topic=topic
            )

            # Flush extraction buffer
            if self._extractor.buffer_size > 0:
                await self._extractor.extract_and_store(force=True)

            # Run evolution if enabled
            if self._memory_config.evolution_enabled:
                await self._evolver.evolve()

            # Run reflection if threshold met
            if self._memory_config.reflection_enabled:
                if await self._reflector.should_reflect():
                    await self._reflector.reflect()

            logger.debug("Memory session ended: %d", self._current_session_id)
            self._current_session_id = None

    # ==================================================================
    # Core new API
    # ==================================================================

    async def retrieve_memories(
        self, query: str, limit: int | None = None
    ) -> list[RetrievalResult]:
        """Hybrid retrieval of relevant memories for a query."""
        return await self._retriever.retrieve(query, limit=limit)

    async def get_assembled_context(
        self,
        query: str,
        platform: str = "",
        author: str = "",
        user_content: str = "",
        system_prompt: str = "",
        few_shot_examples: list[str] | None = None,
    ) -> AssembledContext:
        """Retrieve memories and assemble them into prompt context.

        This is the primary method for getting memory-enriched context
        for prompt construction.
        """
        memories = await self._retriever.retrieve(query)

        entity = None
        if platform and author:
            entity = await self._store.get_entity(platform, author)

        return self._assembler.assemble(
            memories=memories,
            entity=entity,
            few_shot_examples=few_shot_examples,
            user_content=user_content,
            system_prompt=system_prompt,
        )

    async def process_turn(
        self,
        user_content: str,
        bot_content: str,
        author: str = "",
        platform: str = "",
    ) -> None:
        """Process a conversation turn: buffer for extraction and track session.

        Call this after each bot response to feed the memory system.
        """
        # Track session turn
        if self._current_session_id is not None:
            await self._store.increment_session_turns(self._current_session_id)

        # Update entity interaction count
        if platform and author:
            await self._store.upsert_entity(
                EntityProfileCreate(
                    platform=platform,
                    entity_name=author,
                )
            )

        # Buffer turn for LLM extraction
        if self._memory_config.extraction_enabled:
            self._extractor.add_turn(
                user_content=user_content,
                bot_content=bot_content,
                author=author,
                platform=platform,
            )

            # Auto-extract when buffer is large enough
            if self._extractor.buffer_size >= 3:
                await self._extractor.extract_and_store(
                    default_platform=platform,
                    default_author=author,
                )

    async def store_fact(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        source_type: SourceType = SourceType.AUTO_CAPTURE,
        importance: float = 0.5,
        platform: str = "",
        author: str = "",
    ) -> int:
        """Directly store a fact as a knowledge node.

        Used by AutoCaptureService and other direct-capture paths.
        Returns the node ID.
        """
        embedding_blob = None
        vec = await self._embedding.embed_text(content)
        if vec is not None:
            embedding_blob = self._embedding.vector_to_blob(vec)

            # Dedup check
            existing = await self._store.get_embedding_candidates(limit=50)
            if existing and await self._embedding.is_duplicate(content, existing):
                logger.debug("Skipping duplicate fact: %s", content[:60])
                return -1

        node = await self._store.add_node(
            KnowledgeNodeCreate(
                content=content,
                memory_type=memory_type,
                source_type=source_type,
                importance=importance,
                confidence=0.8,
                platform=platform,
                author=author,
                embedding=embedding_blob,
            )
        )
        return node.id

    async def get_entity_profile(
        self, platform: str, entity_name: str
    ) -> Optional[EntityProfile]:
        """Get entity profile for a user/bot."""
        return await self._store.get_entity(platform, entity_name)

    async def get_frequent_contacts(
        self, platform: str | None = None, limit: int = 10
    ) -> list[EntityProfile]:
        """Get entities with the most interactions."""
        return await self._store.get_frequent_entities(platform, limit)

    # ==================================================================
    # Maintenance
    # ==================================================================

    async def run_maintenance(self) -> dict[str, Any]:
        """Run all maintenance operations (evolution + reflection).

        Intended to be called periodically by a scheduler.
        """
        results: dict[str, Any] = {}

        if self._memory_config.evolution_enabled:
            results["evolution"] = await self._evolver.evolve()

        if self._memory_config.reflection_enabled:
            if await self._reflector.should_reflect():
                results["reflection_insights"] = await self._reflector.reflect()

        return results

    # ==================================================================
    # Backward-compatible API (mirrors original MemoryService)
    # ==================================================================

    async def remember_interaction(
        self,
        platform: str,
        entity_name: str,
        entity_type: str = "user",
        topics: list[str] | None = None,
    ) -> None:
        """Record an interaction with an entity (backward compat)."""
        await self._store.upsert_entity(
            EntityProfileCreate(
                platform=platform,
                entity_name=entity_name,
                entity_type=entity_type,
            )
        )

        # Store topics as knowledge nodes if provided
        if topics:
            for topic in topics:
                await self.store_fact(
                    content=f"{entity_name}의 관심사: {topic}",
                    memory_type=MemoryType.FACT,
                    source_type=SourceType.AUTO_CAPTURE,
                    importance=0.5,
                    platform=platform,
                    author=entity_name,
                )

    async def recall_related(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Retrieve related memories as dicts (backward compat)."""
        results = await self._retriever.retrieve(query, limit=limit)
        return [
            {
                "id": r.node.id,
                "content": r.node.content,
                "score": r.score,
                "source": r.source,
                "memory_type": r.node.memory_type,
                "importance": r.node.importance,
            }
            for r in results
        ]

    async def recall_bot(
        self, platform: str, bot_name: str
    ) -> Optional[dict[str, Any]]:
        """Get information about a known bot (backward compat)."""
        entity = await self._store.get_entity(platform, bot_name)
        if entity is None:
            return None
        return {
            "entity_name": entity.entity_name,
            "platform": entity.platform,
            "interaction_count": entity.interaction_count,
            "summary": entity.summary,
            "sentiment": entity.sentiment,
            "trust_level": entity.trust_level,
        }

    async def get_context_for_post(
        self,
        post_content: str,
        author_name: str,
        platform: str,
    ) -> str:
        """Get memory context string for prompt injection (backward compat)."""
        ctx = await self.get_assembled_context(
            query=post_content,
            platform=platform,
            author=author_name,
            user_content=post_content,
        )

        parts: list[str] = []
        if ctx.entity_context:
            parts.append(ctx.entity_context)
        if ctx.memory_context:
            parts.append(ctx.memory_context)

        return "\n\n".join(parts)
