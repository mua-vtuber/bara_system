"""Stanford Generative Agents inspired 3-factor scoring.

Combines recency, relevance, and importance into a single retrieval score.
Recency uses exponential decay so memories gradually fade unless accessed.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone


def compute_recency(
    last_accessed_at: str | datetime,
    half_life_days: float = 30.0,
) -> float:
    """Compute recency score using exponential decay.

    Score is 1.0 when just accessed, decaying to 0.5 after ``half_life_days``.

    Args:
        last_accessed_at: ISO timestamp or datetime of last access.
        half_life_days: Number of days for the score to halve.

    Returns:
        Recency score in [0.0, 1.0].
    """
    now = datetime.now(timezone.utc)

    if isinstance(last_accessed_at, str):
        try:
            dt = datetime.fromisoformat(last_accessed_at)
        except (ValueError, TypeError):
            return 0.0
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = last_accessed_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

    age_hours = max(0.0, (now - dt).total_seconds() / 3600.0)
    half_life_hours = half_life_days * 24.0

    if half_life_hours <= 0:
        return 1.0 if age_hours == 0 else 0.0

    # Exponential decay: score = 2^(-age/half_life)
    decay = math.pow(2.0, -age_hours / half_life_hours)
    return max(0.0, min(1.0, decay))


def compute_combined_score(
    recency: float,
    relevance: float,
    importance: float,
    *,
    w_recency: float = 0.3,
    w_relevance: float = 0.5,
    w_importance: float = 0.2,
) -> float:
    """Compute weighted combination of the three scoring factors.

    Args:
        recency: Recency score [0, 1].
        relevance: Relevance score [0, 1] (e.g. cosine similarity or FTS rank).
        importance: Importance score [0, 1].
        w_recency: Weight for recency factor.
        w_relevance: Weight for relevance factor.
        w_importance: Weight for importance factor.

    Returns:
        Combined score in [0.0, 1.0].
    """
    score = (w_recency * recency) + (w_relevance * relevance) + (w_importance * importance)
    return max(0.0, min(1.0, score))
