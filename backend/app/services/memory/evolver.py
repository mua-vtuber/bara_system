"""Memory evolution: merge similar nodes and prune stale ones.

Inspired by A-MEM's structural evolution operations, adapted for
bara_system's Ollama-based embedding stack.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.embedding import EmbeddingService

if TYPE_CHECKING:
    from app.core.config import MemoryConfig
    from app.repositories.memory_store import MemoryStoreRepository

logger = get_logger(__name__)


class MemoryEvolver:
    """Structural memory evolution: merge duplicates and prune stale nodes.

    Merge: When two nodes exceed the similarity threshold, keep the
    higher-importance one, delete the other, and record a ``merged_from``
    edge for provenance.

    Prune: Nodes with very low importance, zero access count, and age
    exceeding 2x the configured decay half-life are permanently removed.
    """

    def __init__(
        self,
        store: MemoryStoreRepository,
        embedding_service: EmbeddingService,
        config: MemoryConfig,
    ) -> None:
        self._store = store
        self._embedding = embedding_service
        self._config = config

    async def evolve(self) -> dict[str, int]:
        """Run all evolution operations.

        Returns:
            Dict with operation counts: {"merged": N, "pruned": N}.
        """
        merge_count = await self._merge_similar()
        prune_count = await self._prune_stale()

        if merge_count > 0 or prune_count > 0:
            await self._store.log_consolidation(
                operation="evolution",
                details={"merged": merge_count, "pruned": prune_count},
                nodes_affected=merge_count + prune_count,
            )

        logger.info(
            "Evolution complete: merged=%d, pruned=%d",
            merge_count,
            prune_count,
        )
        return {"merged": merge_count, "pruned": prune_count}

    # ------------------------------------------------------------------
    # Merge similar
    # ------------------------------------------------------------------

    async def _merge_similar(self) -> int:
        """Merge nodes with high cosine similarity."""
        candidates = await self._store.get_all_embeddings_for_merge(
            limit=self._config.merge_max_candidates,
        )
        if len(candidates) < 2:
            return 0

        # Deserialize embeddings
        node_embs: list[tuple[dict, list[float]]] = []
        for row in candidates:
            blob = row.get("embedding")
            if not blob:
                continue
            try:
                vec = EmbeddingService.blob_to_vector(blob)
                node_embs.append((row, vec))
            except Exception:
                continue

        if len(node_embs) < 2:
            return 0

        threshold = self._config.merge_similarity_threshold
        merged_ids: set[int] = set()
        merge_count = 0

        for i in range(len(node_embs)):
            node_a, emb_a = node_embs[i]
            aid = node_a["id"]
            if aid in merged_ids:
                continue

            for j in range(i + 1, len(node_embs)):
                node_b, emb_b = node_embs[j]
                bid = node_b["id"]
                if bid in merged_ids:
                    continue

                similarity = EmbeddingService.cosine_similarity(emb_a, emb_b)
                if similarity < threshold:
                    continue

                # Keep higher importance
                imp_a = node_a.get("importance", 0.5)
                imp_b = node_b.get("importance", 0.5)

                if imp_a >= imp_b:
                    keep_id, discard_id = aid, bid
                else:
                    keep_id, discard_id = bid, aid

                # Record merge provenance
                await self._store.add_edge(
                    source_id=keep_id,
                    target_id=discard_id,
                    relation="merged_from",
                    weight=similarity,
                )

                await self._store.delete_node(discard_id)
                merged_ids.add(discard_id)
                merge_count += 1

                logger.debug(
                    "Merged node %d into %d (similarity=%.3f)",
                    discard_id,
                    keep_id,
                    similarity,
                )

        return merge_count

    # ------------------------------------------------------------------
    # Prune stale
    # ------------------------------------------------------------------

    async def _prune_stale(self) -> int:
        """Remove old, unaccessed, low-importance nodes.

        A node is pruned when ALL conditions are met:
        - importance <= prune_importance_threshold
        - access_count == 0
        - age > 2x recency_half_life_days
        """
        candidates = await self._store.get_nodes_for_pruning(limit=1000)
        if not candidates:
            return 0

        now = datetime.now(timezone.utc)
        max_age_hours = self._config.recency_half_life_days * 24.0 * 2
        prune_threshold = self._config.prune_importance_threshold
        prune_count = 0

        for row in candidates:
            if row.get("importance", 0.5) > prune_threshold:
                continue

            created_at = row.get("created_at")
            if not created_at:
                continue

            try:
                created_dt = datetime.fromisoformat(created_at)
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                age_hours = (now - created_dt).total_seconds() / 3600.0
                if age_hours < max_age_hours:
                    continue
            except (ValueError, TypeError):
                continue

            await self._store.delete_node(row["id"])
            prune_count += 1
            logger.debug("Pruned stale node: %d", row["id"])

        return prune_count
