from __future__ import annotations

import math
import struct
from typing import TYPE_CHECKING

from app.core.config import Config
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.services.llm import LLMService

logger = get_logger(__name__)


class EmbeddingService:
    """Manages text embeddings for semantic search.

    Provides embedding generation, serialization for SQLite BLOB storage,
    and cosine similarity ranking — all without external dependencies
    (no numpy required).
    """

    def __init__(self, llm_service: LLMService, config: Config) -> None:
        self._llm = llm_service
        self._config = config

    @property
    def enabled(self) -> bool:
        return self._config.embedding.enabled

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    async def embed_text(self, text: str) -> list[float] | None:
        """Embed a single text string. Returns None on failure."""
        if not self.enabled:
            return None
        try:
            results = await self._llm.embed(text)
            return results[0] if results else None
        except Exception as exc:
            logger.warning("Embedding failed for text (len=%d): %s", len(text), exc)
            return None

    async def embed_texts(self, texts: list[str]) -> list[list[float] | None]:
        """Embed multiple texts. Returns None for each that fails."""
        if not self.enabled:
            return [None] * len(texts)
        try:
            results = await self._llm.embed(texts)
            # Pad if fewer results than inputs
            out: list[list[float] | None] = list(results)
            while len(out) < len(texts):
                out.append(None)
            return out
        except Exception as exc:
            logger.warning("Batch embedding failed: %s", exc)
            return [None] * len(texts)

    # ------------------------------------------------------------------
    # Serialization (SQLite BLOB)
    # ------------------------------------------------------------------

    @staticmethod
    def vector_to_blob(vector: list[float]) -> bytes:
        """Pack a float vector into a compact bytes blob (4 bytes per float)."""
        return struct.pack(f"<{len(vector)}f", *vector)

    @staticmethod
    def blob_to_vector(blob: bytes) -> list[float]:
        """Unpack a bytes blob back into a float vector."""
        count = len(blob) // 4
        return list(struct.unpack(f"<{count}f", blob))

    # ------------------------------------------------------------------
    # Similarity
    # ------------------------------------------------------------------

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors (pure Python)."""
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def rank_by_similarity(
        self,
        query_vec: list[float],
        candidates: list[tuple[int, bytes]],
        threshold: float | None = None,
    ) -> list[tuple[int, float]]:
        """Rank candidate (id, blob) pairs by cosine similarity to query_vec.

        Returns list of (id, score) sorted by score descending,
        filtered by threshold.
        """
        if threshold is None:
            threshold = self._config.embedding.similarity_threshold

        scored: list[tuple[int, float]] = []
        for cid, blob in candidates:
            try:
                vec = self.blob_to_vector(blob)
                score = self.cosine_similarity(query_vec, vec)
                if score >= threshold:
                    scored.append((cid, score))
            except Exception:
                continue

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    async def is_duplicate(
        self,
        text: str,
        existing_blobs: list[tuple[int, bytes]],
        threshold: float | None = None,
    ) -> bool:
        """Check if text is a near-duplicate of any existing embedding."""
        if threshold is None:
            threshold = self._config.embedding.dedup_threshold

        vec = await self.embed_text(text)
        if vec is None:
            return False

        for _, blob in existing_blobs:
            try:
                existing_vec = self.blob_to_vector(blob)
                if self.cosine_similarity(vec, existing_vec) >= threshold:
                    return True
            except Exception:
                continue

        return False
