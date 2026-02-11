"""Non-destructive migration of legacy memory data into the new knowledge graph.

Migrates:
- bot_memory → entity_profiles (interaction counts, topics, sentiment)
- collected_info → knowledge_nodes (content, embeddings, categories)
- good_examples → knowledge_nodes (memory_type='episode')

The original tables are preserved. Migration is idempotent — it records
completion in consolidation_log and skips on subsequent runs.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.models.memory import (
    EntityProfileCreate,
    KnowledgeNodeCreate,
    MemoryType,
    SourceType,
)

if TYPE_CHECKING:
    from app.core.database import Database
    from app.repositories.memory_store import MemoryStoreRepository

logger = get_logger(__name__)

_MIGRATION_KEY = "legacy_data_migration_v1"


async def run_legacy_migration(
    db: Database,
    store: MemoryStoreRepository,
) -> dict[str, int]:
    """Run the one-time legacy data migration.

    Returns counts of migrated records. Skips if already completed.
    """
    # Check if already migrated
    last = await store.get_last_consolidation(_MIGRATION_KEY)
    if last is not None:
        logger.info("Legacy migration already completed, skipping")
        return {"skipped": True}

    logger.info("Starting legacy data migration...")

    counts = {
        "entity_profiles": 0,
        "knowledge_nodes_from_info": 0,
        "knowledge_nodes_from_examples": 0,
    }

    # 1. bot_memory → entity_profiles
    counts["entity_profiles"] = await _migrate_bot_memory(db, store)

    # 2. collected_info → knowledge_nodes
    counts["knowledge_nodes_from_info"] = await _migrate_collected_info(db, store)

    # 3. good_examples → knowledge_nodes (episode type)
    counts["knowledge_nodes_from_examples"] = await _migrate_good_examples(db, store)

    # Record completion
    await store.log_consolidation(
        operation=_MIGRATION_KEY,
        details=counts,
        nodes_affected=sum(counts.values()),
    )

    logger.info("Legacy migration complete: %s", counts)
    return counts


async def _migrate_bot_memory(
    db: Database,
    store: MemoryStoreRepository,
) -> int:
    """Migrate bot_memory rows to entity_profiles."""
    try:
        rows = await db.fetch_all(
            "SELECT * FROM bot_memory ORDER BY id", ()
        )
    except Exception as exc:
        logger.warning("Cannot read bot_memory (table may not exist): %s", exc)
        return 0

    count = 0
    for row in rows:
        try:
            # Upsert entity profile
            entity = await store.upsert_entity(
                EntityProfileCreate(
                    platform=row["platform"],
                    entity_name=row["entity_name"],
                    entity_type=row.get("entity_type", "bot"),
                )
            )

            # Update fields that upsert doesn't cover
            sentiment = row.get("sentiment", "neutral")
            if sentiment != "neutral":
                await store.update_entity_sentiment(
                    entity.id, sentiment, 0.0
                )

            # Migrate topics as interests
            topics_raw = row.get("topics", "[]")
            if isinstance(topics_raw, str):
                try:
                    topics = json.loads(topics_raw)
                except (json.JSONDecodeError, TypeError):
                    topics = []
            else:
                topics = topics_raw or []

            if topics:
                # Store each topic as a knowledge node
                for topic in topics[:10]:
                    await store.add_node(
                        KnowledgeNodeCreate(
                            content=f"{row['entity_name']}의 관심사: {topic}",
                            memory_type=MemoryType.FACT,
                            source_type=SourceType.AUTO_CAPTURE,
                            importance=0.4,
                            confidence=0.6,
                            platform=row["platform"],
                            author=row["entity_name"],
                        )
                    )

            # Migrate relationship_notes as a knowledge node
            notes = row.get("relationship_notes", "")
            if notes and notes.strip():
                await store.add_node(
                    KnowledgeNodeCreate(
                        content=f"{row['entity_name']}에 대한 메모: {notes}",
                        memory_type=MemoryType.FACT,
                        source_type=SourceType.AUTO_CAPTURE,
                        importance=0.5,
                        confidence=0.7,
                        platform=row["platform"],
                        author=row["entity_name"],
                    )
                )

            # Transfer embedding if present
            embedding = row.get("embedding")
            if embedding and entity:
                await store.update_entity_embedding(entity.id, embedding)

            count += 1
        except Exception as exc:
            logger.warning(
                "Failed to migrate bot_memory id=%s: %s",
                row.get("id"),
                exc,
            )

    logger.info("Migrated %d bot_memory records to entity_profiles", count)
    return count


async def _migrate_collected_info(
    db: Database,
    store: MemoryStoreRepository,
) -> int:
    """Migrate collected_info rows to knowledge_nodes."""
    try:
        rows = await db.fetch_all(
            "SELECT * FROM collected_info ORDER BY id", ()
        )
    except Exception as exc:
        logger.warning("Cannot read collected_info: %s", exc)
        return 0

    count = 0
    for row in rows:
        try:
            content = row.get("content", "")
            title = row.get("title", "")
            if not content and not title:
                continue

            # Combine title and content for the knowledge node
            node_content = title
            if content:
                node_content = f"{title}: {content}" if title else content

            # Truncate very long content
            if len(node_content) > 500:
                node_content = node_content[:500]

            # Determine memory type from category
            category = row.get("category", "")
            if "preference" in category:
                mem_type = MemoryType.PREFERENCE
            elif "entity" in category:
                mem_type = MemoryType.FACT
            else:
                mem_type = MemoryType.FACT

            await store.add_node(
                KnowledgeNodeCreate(
                    content=node_content,
                    memory_type=mem_type,
                    source_type=SourceType.AUTO_CAPTURE,
                    importance=0.5,
                    confidence=0.7,
                    platform=row.get("platform", ""),
                    author=row.get("author", ""),
                    embedding=row.get("embedding"),
                )
            )
            count += 1
        except Exception as exc:
            logger.warning(
                "Failed to migrate collected_info id=%s: %s",
                row.get("id"),
                exc,
            )

    logger.info("Migrated %d collected_info records to knowledge_nodes", count)
    return count


async def _migrate_good_examples(
    db: Database,
    store: MemoryStoreRepository,
) -> int:
    """Migrate good_examples rows to knowledge_nodes as episodes."""
    try:
        rows = await db.fetch_all(
            "SELECT * FROM good_examples ORDER BY id", ()
        )
    except Exception as exc:
        logger.warning("Cannot read good_examples: %s", exc)
        return 0

    count = 0
    for row in rows:
        try:
            bot_response = row.get("bot_response", "")
            if not bot_response:
                continue

            context_title = row.get("context_title", "")
            context_content = row.get("context_content", "")

            # Build episode content
            parts = []
            if context_title:
                parts.append(f"글: {context_title}")
            if context_content:
                parts.append(f"맥락: {context_content[:200]}")
            parts.append(f"응답: {bot_response[:300]}")

            node_content = "\n".join(parts)

            # Calculate importance from engagement
            engagement = row.get("engagement_score", 0.0) or 0.0
            importance = min(0.9, max(0.5, 0.5 + engagement * 0.1))

            metadata = {
                "action_type": row.get("action_type", "comment"),
                "engagement_score": engagement,
                "reply_count": row.get("reply_count", 0),
                "upvote_count": row.get("upvote_count", 0),
            }

            await store.add_node(
                KnowledgeNodeCreate(
                    content=node_content,
                    memory_type=MemoryType.EPISODE,
                    source_type=SourceType.AUTO_CAPTURE,
                    importance=importance,
                    confidence=0.9,
                    platform=row.get("platform", ""),
                    embedding=row.get("embedding"),
                    metadata_json=json.dumps(metadata, ensure_ascii=False),
                )
            )
            count += 1
        except Exception as exc:
            logger.warning(
                "Failed to migrate good_example id=%s: %s",
                row.get("id"),
                exc,
            )

    logger.info("Migrated %d good_examples to knowledge_nodes", count)
    return count
