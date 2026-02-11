"""Hybrid retriever combining vector search, FTS5, and knowledge graph.

Implements Stanford Generative Agents inspired 3-factor scoring
(recency, relevance, importance) with weighted fusion across three
retrieval sources.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.models.memory import KnowledgeNode, RetrievalResult
from app.services.memory.scoring import compute_combined_score, compute_recency

if TYPE_CHECKING:
    from app.core.config import MemoryConfig
    from app.repositories.memory_store import MemoryStoreRepository
    from app.services.embedding import EmbeddingService

logger = get_logger(__name__)

# Fusion weights for merging results from multiple sources
_W_VECTOR: float = 0.5
_W_FTS: float = 0.3
_W_GRAPH: float = 0.2


class HybridRetriever:
    """3-source hybrid retrieval with Stanford 3-factor scoring.

    Sources:
        1. Vector similarity (cosine) on embeddings
        2. FTS5 full-text search (BM25 rank)
        3. Knowledge graph expansion (BFS from top results)

    Results are fused: if the same node appears in multiple sources,
    scores are combined with source-specific weights.
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

    async def retrieve(
        self,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievalResult]:
        """Run hybrid retrieval for a query string.

        Args:
            query: Natural language search query.
            limit: Max results to return (defaults to config.retrieval_limit).

        Returns:
            Scored and sorted list of RetrievalResult.
        """
        if limit is None:
            limit = self._config.retrieval_limit

        # Run vector and FTS searches
        vector_scores = await self._vector_search(query)
        fts_scores = await self._fts_search(query) if self._config.fts_enabled else {}

        # Graph expansion from top vector + FTS seeds
        seed_ids = self._get_seed_ids(vector_scores, fts_scores, top_k=5)
        graph_scores = await self._graph_expand(seed_ids)

        # Fuse results
        fused = self._fuse_scores(vector_scores, fts_scores, graph_scores)

        if not fused:
            return []

        # Fetch full nodes and build results
        node_ids = list(fused.keys())
        nodes = await self._store.get_nodes_by_ids(node_ids)
        node_map = {n.id: n for n in nodes}

        results: list[RetrievalResult] = []
        for node_id, (score, source) in fused.items():
            node = node_map.get(node_id)
            if node is None:
                continue
            results.append(RetrievalResult(node=node, score=score, source=source))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        results = results[:limit]

        # Touch accessed nodes to update recency
        for r in results:
            await self._store.touch_node(r.node.id)

        logger.debug(
            "Hybrid retrieval for %r: %d results (vector=%d, fts=%d, graph=%d)",
            query[:50],
            len(results),
            len(vector_scores),
            len(fts_scores),
            len(graph_scores),
        )

        return results

    # ------------------------------------------------------------------
    # Vector search
    # ------------------------------------------------------------------

    async def _vector_search(self, query: str) -> dict[int, float]:
        """Embed query and rank against stored embeddings.

        Returns dict of {node_id: 3-factor-score}.
        """
        query_vec = await self._embedding.embed_text(query)
        if query_vec is None:
            return {}

        candidates = await self._store.get_embedding_candidates(limit=100)
        if not candidates:
            return {}

        ranked = self._embedding.rank_by_similarity(query_vec, candidates)

        scores: dict[int, float] = {}
        for node_id, cosine_sim in ranked:
            node = await self._store.get_node(node_id)
            if node is None:
                continue

            recency = compute_recency(
                node.last_accessed_at,
                half_life_days=self._config.recency_half_life_days,
            )
            combined = compute_combined_score(
                recency=recency,
                relevance=cosine_sim,
                importance=node.importance,
                w_recency=self._config.score_w_recency,
                w_relevance=self._config.score_w_relevance,
                w_importance=self._config.score_w_importance,
            )
            scores[node_id] = combined

        return scores

    # ------------------------------------------------------------------
    # FTS5 search
    # ------------------------------------------------------------------

    async def _fts_search(self, query: str) -> dict[int, float]:
        """Full-text search with BM25 scoring.

        Returns dict of {node_id: 3-factor-score}.
        """
        fts_results = await self._store.fts_search(query, limit=20)
        if not fts_results:
            return {}

        # Normalize FTS ranks to [0, 1]
        max_rank = max(r for _, r in fts_results) if fts_results else 1.0
        if max_rank <= 0:
            max_rank = 1.0

        scores: dict[int, float] = {}
        for node_id, rank in fts_results:
            node = await self._store.get_node(node_id)
            if node is None:
                continue

            relevance = rank / max_rank

            recency = compute_recency(
                node.last_accessed_at,
                half_life_days=self._config.recency_half_life_days,
            )
            combined = compute_combined_score(
                recency=recency,
                relevance=relevance,
                importance=node.importance,
                w_recency=self._config.score_w_recency,
                w_relevance=self._config.score_w_relevance,
                w_importance=self._config.score_w_importance,
            )
            scores[node_id] = combined

        return scores

    # ------------------------------------------------------------------
    # Graph expansion
    # ------------------------------------------------------------------

    async def _graph_expand(self, seed_ids: list[int]) -> dict[int, float]:
        """BFS expansion from seed nodes using knowledge edges.

        Uses edge weight as relevance proxy for the 3-factor score.
        """
        if not seed_ids:
            return {}

        connected = await self._store.get_connected_nodes(
            seed_ids,
            max_hops=self._config.graph_max_hops,
            limit=30,
        )

        scores: dict[int, float] = {}
        for node_id, edge_weight in connected:
            node = await self._store.get_node(node_id)
            if node is None:
                continue

            recency = compute_recency(
                node.last_accessed_at,
                half_life_days=self._config.recency_half_life_days,
            )
            combined = compute_combined_score(
                recency=recency,
                relevance=edge_weight,
                importance=node.importance,
                w_recency=self._config.score_w_recency,
                w_relevance=self._config.score_w_relevance,
                w_importance=self._config.score_w_importance,
            )
            scores[node_id] = combined

        return scores

    # ------------------------------------------------------------------
    # Fusion
    # ------------------------------------------------------------------

    @staticmethod
    def _get_seed_ids(
        vector_scores: dict[int, float],
        fts_scores: dict[int, float],
        top_k: int = 5,
    ) -> list[int]:
        """Pick top node IDs from vector + FTS results as graph seeds."""
        merged: dict[int, float] = {}
        for nid, score in vector_scores.items():
            merged[nid] = merged.get(nid, 0) + score
        for nid, score in fts_scores.items():
            merged[nid] = merged.get(nid, 0) + score

        sorted_ids = sorted(merged, key=merged.get, reverse=True)  # type: ignore[arg-type]
        return sorted_ids[:top_k]

    @staticmethod
    def _fuse_scores(
        vector_scores: dict[int, float],
        fts_scores: dict[int, float],
        graph_scores: dict[int, float],
    ) -> dict[int, tuple[float, str]]:
        """Weighted fusion of scores from multiple sources.

        If a node appears in multiple sources, combine with source weights.
        Returns {node_id: (fused_score, primary_source)}.
        """
        all_ids = set(vector_scores) | set(fts_scores) | set(graph_scores)
        fused: dict[int, tuple[float, str]] = {}

        for nid in all_ids:
            v = vector_scores.get(nid, 0.0)
            f = fts_scores.get(nid, 0.0)
            g = graph_scores.get(nid, 0.0)

            total_weight = 0.0
            weighted_sum = 0.0

            if v > 0:
                weighted_sum += _W_VECTOR * v
                total_weight += _W_VECTOR
            if f > 0:
                weighted_sum += _W_FTS * f
                total_weight += _W_FTS
            if g > 0:
                weighted_sum += _W_GRAPH * g
                total_weight += _W_GRAPH

            if total_weight > 0:
                score = weighted_sum / total_weight
            else:
                continue

            # Determine primary source
            source = "vector"
            if f > v and f > g:
                source = "fts"
            elif g > v and g > f:
                source = "graph"

            fused[nid] = (score, source)

        return fused
