"""Reflection engine inspired by Stanford Generative Agents.

Periodically synthesizes accumulated knowledge nodes into higher-level
insights, making the bot genuinely "smarter" over time by recognizing
patterns, trends, and relationships across its memories.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.models.memory import KnowledgeNode, KnowledgeNodeCreate, MemoryType, SourceType

if TYPE_CHECKING:
    from app.core.config import MemoryConfig
    from app.repositories.memory_store import MemoryStoreRepository
    from app.services.embedding import EmbeddingService
    from app.services.llm import LLMService

logger = get_logger(__name__)

_REFLECTION_SYSTEM_PROMPT = """\
You are a reflective AI assistant. Given a set of factual memories about \
people and interactions, synthesize higher-level insights.

For each group of related memories, generate insights that:
1. Identify patterns in behavior, interests, or preferences
2. Recognize relationship dynamics
3. Note trends over time (increasing interest, changing sentiment, etc.)
4. Summarize what you've learned about each person or topic

Return a JSON array of insights. Each element must have:
- "content": the insight statement (string, 1-3 sentences)
- "importance": how significant this insight is, 0.5 to 1.0 (number)
- "related_to": list of entity names this insight relates to (array of strings)

Write insights in the same language as the source memories.
Return ONLY the JSON array. No markdown, no explanation.
If no meaningful insights can be drawn, return: []\
"""

_ENTITY_SUMMARY_SYSTEM_PROMPT = """\
You are a relationship memory assistant. Given a set of facts about a person, \
write a concise 2-4 sentence summary of who they are and your relationship \
with them. Write in the same language as the source facts.

Return ONLY the summary text, no JSON, no markdown.\
"""


class ReflectionEngine:
    """Generates higher-level insights from accumulated knowledge.

    Triggered when the number of new nodes since the last reflection
    exceeds the configured threshold. Groups recent nodes by topic/entity,
    sends them to the LLM, and stores resulting insights as new
    knowledge nodes with ``memory_type='insight'``.
    """

    def __init__(
        self,
        llm: LLMService,
        store: MemoryStoreRepository,
        embedding_service: EmbeddingService,
        config: MemoryConfig,
    ) -> None:
        self._llm = llm
        self._store = store
        self._embedding = embedding_service
        self._config = config

    async def should_reflect(self) -> bool:
        """Check if enough new nodes have accumulated since last reflection."""
        last = await self._store.get_last_consolidation("reflection")
        since = last["timestamp"] if last else "1970-01-01T00:00:00"
        count = await self._store.count_nodes_since(since)
        return count >= self._config.reflection_threshold

    async def reflect(self) -> int:
        """Run the reflection process.

        Returns the number of insight nodes created.
        """
        last = await self._store.get_last_consolidation("reflection")
        since = last["timestamp"] if last else "1970-01-01T00:00:00"

        recent_nodes = await self._store.get_recent_nodes(
            limit=50, since=since
        )
        if len(recent_nodes) < self._config.reflection_threshold:
            return 0

        # Group nodes by author (entity)
        groups = self._group_by_author(recent_nodes)

        total_insights = 0

        # Generate insights for each group
        for author, nodes in groups.items():
            if len(nodes) < 3:
                continue

            insights = await self._generate_insights(nodes)
            for insight_data in insights:
                node = await self._store_insight(insight_data, author)
                if node:
                    # Create derived_from edges to source nodes
                    for source_node in nodes:
                        await self._store.add_edge(
                            source_id=node.id,
                            target_id=source_node.id,
                            relation="derived_from",
                            weight=0.8,
                        )
                    total_insights += 1

            # Update entity profile summary if author is known
            if author:
                await self._update_entity_summary(author, nodes)

        # Also generate cross-entity insights if enough nodes
        if len(recent_nodes) >= 10:
            cross_insights = await self._generate_insights(recent_nodes)
            for insight_data in cross_insights:
                node = await self._store_insight(insight_data, "")
                if node:
                    total_insights += 1

        # Log the reflection
        await self._store.log_consolidation(
            operation="reflection",
            details={"insights_created": total_insights, "nodes_processed": len(recent_nodes)},
            nodes_affected=total_insights,
        )

        logger.info(
            "Reflection complete: %d insights from %d nodes",
            total_insights,
            len(recent_nodes),
        )
        return total_insights

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _group_by_author(
        nodes: list[KnowledgeNode],
    ) -> dict[str, list[KnowledgeNode]]:
        groups: dict[str, list[KnowledgeNode]] = {}
        for node in nodes:
            key = node.author or "_general"
            groups.setdefault(key, []).append(node)
        return groups

    async def _generate_insights(
        self, nodes: list[KnowledgeNode]
    ) -> list[dict]:
        """Ask LLM to synthesize insights from a group of memory nodes."""
        memories_text = "\n".join(
            f"- [{n.memory_type}] {n.content} (importance: {n.importance})"
            for n in nodes
        )

        messages = [
            {"role": "system", "content": _REFLECTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Here are the accumulated memories to reflect on:\n\n"
                    f"{memories_text}\n\n"
                    "Generate higher-level insights from these memories."
                ),
            },
        ]

        try:
            response = await self._llm.chat(messages, stream=False)
            if not isinstance(response, str):
                return []
            return self._parse_insights(response.strip())
        except Exception as exc:
            logger.error("Reflection LLM call failed: %s", exc)
            return []

    @staticmethod
    def _parse_insights(raw_json: str) -> list[dict]:
        text = raw_json.strip()
        if text.startswith("```"):
            first_nl = text.find("\n")
            if first_nl != -1:
                text = text[first_nl + 1:]
            if text.endswith("```"):
                text = text[:-3].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse reflection JSON: %s", exc)
            return []

        if not isinstance(data, list):
            return []

        results: list[dict] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            content = item.get("content", "").strip()
            if not content:
                continue
            results.append({
                "content": content,
                "importance": max(0.5, min(1.0, float(item.get("importance", 0.7)))),
                "related_to": item.get("related_to", []),
            })
        return results

    async def _store_insight(
        self, insight_data: dict, author: str
    ) -> KnowledgeNode | None:
        """Store an insight as a knowledge node."""
        content = insight_data["content"]

        # Generate embedding
        embedding_blob = None
        vec = await self._embedding.embed_text(content)
        if vec is not None:
            embedding_blob = self._embedding.vector_to_blob(vec)

        metadata = {}
        related_to = insight_data.get("related_to", [])
        if related_to:
            metadata["related_to"] = related_to

        try:
            node = await self._store.add_node(
                KnowledgeNodeCreate(
                    content=content,
                    memory_type=MemoryType.INSIGHT,
                    source_type=SourceType.REFLECTION,
                    importance=insight_data["importance"],
                    confidence=0.7,
                    author=author,
                    embedding=embedding_blob,
                    metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else "{}",
                )
            )
            return node
        except Exception as exc:
            logger.error("Failed to store insight: %s", exc)
            return None

    async def _update_entity_summary(
        self, author: str, nodes: list[KnowledgeNode]
    ) -> None:
        """Update an entity profile's summary based on accumulated facts."""
        # Find the entity profile across platforms
        entities = await self._store.get_frequent_entities(limit=100)
        target = None
        for entity in entities:
            if entity.entity_name == author:
                target = entity
                break

        if target is None:
            return

        facts_text = "\n".join(
            f"- {n.content}" for n in nodes[:20]  # Cap to avoid prompt overflow
        )

        messages = [
            {"role": "system", "content": _ENTITY_SUMMARY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Facts about {author}:\n{facts_text}",
            },
        ]

        try:
            response = await self._llm.chat(messages, stream=False)
            if isinstance(response, str) and response.strip():
                await self._store.update_entity_summary(
                    target.id, response.strip()
                )
                logger.debug("Updated entity summary for %s", author)
        except Exception as exc:
            logger.warning("Entity summary update failed for %s: %s", author, exc)
