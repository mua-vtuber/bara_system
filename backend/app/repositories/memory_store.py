"""Unified repository for the redesigned memory system.

Manages knowledge_nodes (with FTS5), knowledge_edges, entity_profiles,
sentiment_history, consolidation_log, and memory_sessions tables.
"""

from __future__ import annotations

import json
import re
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

from app.models.memory import (
    EntityProfile,
    EntityProfileCreate,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeNodeCreate,
)
from app.repositories.base import BaseRepository


class MemoryStoreRepository(BaseRepository):
    """Unified data access for the knowledge-graph memory system."""

    _table_name = "knowledge_nodes"

    # ── FTS5 query sanitization ──────────────────────────────────────

    _FTS_SPECIAL = re.compile(r"[\"'\-+*(){}^\[\]:~@!&|]")

    @classmethod
    def _sanitize_fts_query(cls, query: str) -> str:
        """Escape FTS5 special characters to prevent syntax errors."""
        cleaned = cls._FTS_SPECIAL.sub(" ", query)
        tokens = cleaned.split()
        if not tokens:
            return ""
        # Quote each token for safety, join with OR for broad matching
        return " OR ".join(f'"{t}"' for t in tokens if t)

    # ==================================================================
    # Knowledge Nodes
    # ==================================================================

    async def add_node(self, create: KnowledgeNodeCreate) -> KnowledgeNode:
        """Insert a knowledge node and return the created record."""
        now = datetime.now(timezone.utc).isoformat()
        row_id = await self.execute_write(
            "INSERT INTO knowledge_nodes "
            "(content, memory_type, source_type, importance, confidence, "
            " platform, author, created_at, last_accessed_at, embedding, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                create.content,
                create.memory_type.value if hasattr(create.memory_type, "value") else create.memory_type,
                create.source_type.value if hasattr(create.source_type, "value") else create.source_type,
                create.importance,
                create.confidence,
                create.platform,
                create.author,
                now,
                now,
                create.embedding,
                create.metadata_json,
            ),
        )
        row = await self.fetch_one(
            "SELECT * FROM knowledge_nodes WHERE id = ?", (row_id,)
        )
        assert row is not None
        return KnowledgeNode(**row)

    async def get_node(self, node_id: int) -> Optional[KnowledgeNode]:
        row = await self.fetch_one(
            "SELECT * FROM knowledge_nodes WHERE id = ?", (node_id,)
        )
        if row is None:
            return None
        return KnowledgeNode(**row)

    async def get_nodes_by_ids(self, ids: list[int]) -> list[KnowledgeNode]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = await self.fetch_all(
            f"SELECT * FROM knowledge_nodes WHERE id IN ({placeholders})",
            tuple(ids),
        )
        return [KnowledgeNode(**r) for r in rows]

    async def touch_node(self, node_id: int) -> None:
        """Update last_accessed_at and increment access_count."""
        now = datetime.now(timezone.utc).isoformat()
        await self.execute_write(
            "UPDATE knowledge_nodes SET "
            "last_accessed_at = ?, access_count = access_count + 1 "
            "WHERE id = ?",
            (now, node_id),
        )

    async def update_node_importance(
        self, node_id: int, importance: float
    ) -> None:
        await self.execute_write(
            "UPDATE knowledge_nodes SET importance = ? WHERE id = ?",
            (importance, node_id),
        )

    async def update_node_embedding(
        self, node_id: int, embedding: bytes
    ) -> None:
        await self.execute_write(
            "UPDATE knowledge_nodes SET embedding = ? WHERE id = ?",
            (embedding, node_id),
        )

    async def delete_node(self, node_id: int) -> None:
        await self.execute_write(
            "DELETE FROM knowledge_nodes WHERE id = ?", (node_id,)
        )

    async def get_embedding_candidates(
        self,
        limit: int = 100,
        memory_type: str | None = None,
        author: str | None = None,
    ) -> list[tuple[int, bytes]]:
        """Fetch (id, embedding_blob) pairs for vector similarity search."""
        conditions = ["embedding IS NOT NULL"]
        params: list[object] = []

        if memory_type is not None:
            conditions.append("memory_type = ?")
            params.append(memory_type)
        if author is not None:
            conditions.append("author = ?")
            params.append(author)

        where = "WHERE " + " AND ".join(conditions)
        sql = (
            f"SELECT id, embedding FROM knowledge_nodes {where} "
            "ORDER BY last_accessed_at DESC LIMIT ?"
        )
        params.append(limit)

        rows = await self.fetch_all(sql, tuple(params))
        return [(r["id"], r["embedding"]) for r in rows]

    async def get_all_embeddings_for_merge(
        self, limit: int = 500
    ) -> list[dict[str, Any]]:
        """Fetch nodes with embeddings for merge candidate evaluation."""
        rows = await self.fetch_all(
            "SELECT id, content, importance, last_accessed_at, embedding "
            "FROM knowledge_nodes WHERE embedding IS NOT NULL "
            "ORDER BY last_accessed_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    async def get_nodes_for_pruning(self, limit: int = 1000) -> list[dict[str, Any]]:
        """Fetch low-importance, never-accessed nodes as prune candidates."""
        rows = await self.fetch_all(
            "SELECT id, importance, access_count, created_at "
            "FROM knowledge_nodes "
            "WHERE access_count = 0 "
            "ORDER BY importance ASC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    async def count_nodes_since(self, since: str) -> int:
        """Count nodes created after a given ISO timestamp."""
        row = await self.fetch_one(
            "SELECT COUNT(*) AS cnt FROM knowledge_nodes WHERE created_at > ?",
            (since,),
        )
        return row["cnt"] if row else 0

    async def get_recent_nodes(
        self, limit: int = 20, since: str | None = None
    ) -> list[KnowledgeNode]:
        """Fetch the most recent knowledge nodes."""
        if since:
            rows = await self.fetch_all(
                "SELECT * FROM knowledge_nodes WHERE created_at > ? "
                "ORDER BY created_at DESC LIMIT ?",
                (since, limit),
            )
        else:
            rows = await self.fetch_all(
                "SELECT * FROM knowledge_nodes ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [KnowledgeNode(**r) for r in rows]

    # ==================================================================
    # FTS5 Search
    # ==================================================================

    async def fts_search(
        self, query: str, limit: int = 20
    ) -> list[tuple[int, float]]:
        """Full-text search returning (node_id, rank) pairs.

        Uses FTS5 ``rank`` which is a negative BM25 score (more negative = better).
        We negate it so higher values are better matches.
        """
        sanitized = self._sanitize_fts_query(query)
        if not sanitized:
            return []

        rows = await self.fetch_all(
            "SELECT rowid, rank FROM knowledge_nodes_fts "
            "WHERE knowledge_nodes_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (sanitized, limit),
        )
        return [(r["rowid"], -r["rank"]) for r in rows]

    # ==================================================================
    # Knowledge Edges
    # ==================================================================

    async def add_edge(
        self,
        source_id: int,
        target_id: int,
        relation: str = "related_to",
        weight: float = 1.0,
    ) -> Optional[int]:
        """Insert a knowledge edge. Returns row id or None on conflict."""
        try:
            return await self.execute_write(
                "INSERT OR IGNORE INTO knowledge_edges "
                "(source_id, target_id, relation, weight) "
                "VALUES (?, ?, ?, ?)",
                (source_id, target_id, relation, weight),
            )
        except Exception:
            return None

    async def get_neighbors(
        self, node_id: int, limit: int = 20
    ) -> list[KnowledgeEdge]:
        """Get edges where node_id is source or target."""
        rows = await self.fetch_all(
            "SELECT * FROM knowledge_edges "
            "WHERE source_id = ? OR target_id = ? "
            "ORDER BY weight DESC LIMIT ?",
            (node_id, node_id, limit),
        )
        return [KnowledgeEdge(**r) for r in rows]

    async def get_connected_nodes(
        self,
        seed_ids: list[int],
        max_hops: int = 2,
        limit: int = 30,
    ) -> list[tuple[int, float]]:
        """BFS graph traversal returning (node_id, max_edge_weight) pairs.

        Starts from seed_ids, expands up to ``max_hops`` levels via edges.
        Returns discovered node IDs (excluding seeds) with the maximum
        edge weight encountered on the path.
        """
        if not seed_ids:
            return []

        visited: set[int] = set(seed_ids)
        frontier: deque[int] = deque(seed_ids)
        discovered: dict[int, float] = {}  # node_id -> max_weight

        for _hop in range(max_hops):
            next_frontier: list[int] = []
            if not frontier:
                break

            placeholders = ",".join("?" for _ in frontier)
            rows = await self.fetch_all(
                f"SELECT source_id, target_id, weight FROM knowledge_edges "
                f"WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})",
                tuple(frontier) + tuple(frontier),
            )

            for row in rows:
                for neighbor_id in (row["source_id"], row["target_id"]):
                    if neighbor_id in visited:
                        continue
                    visited.add(neighbor_id)
                    weight = row["weight"]
                    if neighbor_id in discovered:
                        discovered[neighbor_id] = max(discovered[neighbor_id], weight)
                    else:
                        discovered[neighbor_id] = weight
                    next_frontier.append(neighbor_id)

            frontier = deque(next_frontier)

        # Sort by weight descending, apply limit
        result = sorted(discovered.items(), key=lambda x: x[1], reverse=True)
        return result[:limit]

    # ==================================================================
    # Entity Profiles
    # ==================================================================

    async def upsert_entity(self, create: EntityProfileCreate) -> EntityProfile:
        """Insert or update an entity profile."""
        now = datetime.now(timezone.utc).isoformat()
        await self.execute_write(
            "INSERT INTO entity_profiles "
            "(platform, entity_name, entity_type, display_name, "
            " first_seen_at, last_interaction_at, interaction_count) "
            "VALUES (?, ?, ?, ?, ?, ?, 1) "
            "ON CONFLICT(platform, entity_name) DO UPDATE SET "
            "  interaction_count = interaction_count + 1, "
            "  last_interaction_at = ?, "
            "  display_name = CASE "
            "    WHEN ? = '' THEN display_name "
            "    ELSE ? "
            "  END",
            (
                create.platform,
                create.entity_name,
                create.entity_type,
                create.display_name,
                now,
                now,
                # ON CONFLICT params:
                now,
                create.display_name,
                create.display_name,
            ),
        )
        return await self.get_entity(create.platform, create.entity_name)  # type: ignore[return-value]

    async def get_entity(
        self, platform: str, entity_name: str
    ) -> Optional[EntityProfile]:
        row = await self.fetch_one(
            "SELECT * FROM entity_profiles "
            "WHERE platform = ? AND entity_name = ?",
            (platform, entity_name),
        )
        if row is None:
            return None
        return EntityProfile(**row)

    async def get_entity_by_id(self, entity_id: int) -> Optional[EntityProfile]:
        row = await self.fetch_one(
            "SELECT * FROM entity_profiles WHERE id = ?", (entity_id,)
        )
        if row is None:
            return None
        return EntityProfile(**row)

    async def increment_interaction(
        self, platform: str, entity_name: str
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.execute_write(
            "UPDATE entity_profiles SET "
            "interaction_count = interaction_count + 1, "
            "last_interaction_at = ? "
            "WHERE platform = ? AND entity_name = ?",
            (now, platform, entity_name),
        )

    async def update_entity_summary(
        self, entity_id: int, summary: str
    ) -> None:
        await self.execute_write(
            "UPDATE entity_profiles SET summary = ? WHERE id = ?",
            (summary, entity_id),
        )

    async def update_entity_sentiment(
        self,
        entity_id: int,
        sentiment: str,
        sentiment_score: float,
    ) -> None:
        await self.execute_write(
            "UPDATE entity_profiles SET sentiment = ?, sentiment_score = ? "
            "WHERE id = ?",
            (sentiment, sentiment_score, entity_id),
        )

    async def update_entity_embedding(
        self, entity_id: int, embedding: bytes
    ) -> None:
        await self.execute_write(
            "UPDATE entity_profiles SET embedding = ? WHERE id = ?",
            (embedding, entity_id),
        )

    async def get_frequent_entities(
        self, platform: str | None = None, limit: int = 10
    ) -> list[EntityProfile]:
        if platform:
            rows = await self.fetch_all(
                "SELECT * FROM entity_profiles WHERE platform = ? "
                "ORDER BY interaction_count DESC LIMIT ?",
                (platform, limit),
            )
        else:
            rows = await self.fetch_all(
                "SELECT * FROM entity_profiles "
                "ORDER BY interaction_count DESC LIMIT ?",
                (limit,),
            )
        return [EntityProfile(**r) for r in rows]

    # ==================================================================
    # Sentiment History
    # ==================================================================

    async def add_sentiment_entry(
        self,
        entity_profile_id: int,
        sentiment_label: str,
        sentiment_score: float,
        context: str = "",
    ) -> Optional[int]:
        return await self.execute_write(
            "INSERT INTO sentiment_history "
            "(entity_profile_id, sentiment_label, sentiment_score, context) "
            "VALUES (?, ?, ?, ?)",
            (entity_profile_id, sentiment_label, sentiment_score, context),
        )

    async def get_sentiment_trajectory(
        self, entity_profile_id: int, limit: int = 20
    ) -> list[dict[str, Any]]:
        rows = await self.fetch_all(
            "SELECT * FROM sentiment_history "
            "WHERE entity_profile_id = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (entity_profile_id, limit),
        )
        return [dict(r) for r in rows]

    # ==================================================================
    # Consolidation Log
    # ==================================================================

    async def log_consolidation(
        self,
        operation: str,
        details: dict[str, Any] | None = None,
        nodes_affected: int = 0,
    ) -> None:
        await self.execute_write(
            "INSERT INTO consolidation_log "
            "(operation, details_json, nodes_affected) VALUES (?, ?, ?)",
            (
                operation,
                json.dumps(details or {}, ensure_ascii=False),
                nodes_affected,
            ),
        )

    async def get_last_consolidation(
        self, operation: str
    ) -> Optional[dict[str, Any]]:
        row = await self.fetch_one(
            "SELECT * FROM consolidation_log "
            "WHERE operation = ? ORDER BY timestamp DESC LIMIT 1",
            (operation,),
        )
        return dict(row) if row else None

    # ==================================================================
    # Memory Sessions
    # ==================================================================

    async def start_session(self, platform: str = "chat") -> int:
        """Start a new memory session and return its ID."""
        row_id = await self.execute_write(
            "INSERT INTO memory_sessions (platform) VALUES (?)",
            (platform,),
        )
        assert row_id is not None
        return row_id

    async def end_session(
        self, session_id: int, summary: str = "", topic: str = ""
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.execute_write(
            "UPDATE memory_sessions SET ended_at = ?, summary = ?, topic = ? "
            "WHERE id = ?",
            (now, summary, topic, session_id),
        )

    async def increment_session_turns(self, session_id: int) -> None:
        await self.execute_write(
            "UPDATE memory_sessions SET turn_count = turn_count + 1 "
            "WHERE id = ?",
            (session_id,),
        )
