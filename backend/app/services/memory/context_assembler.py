"""Token-budgeted context assembly for prompt construction.

Allocates a total token budget across multiple context components
(system prompt, entity profile, memories, few-shot, user content,
response reserve) and assembles them into a structured prompt context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.models.memory import EntityProfile, RetrievalResult
from app.services.memory.token_counter import estimate_tokens, truncate_to_budget

if TYPE_CHECKING:
    from app.core.config import MemoryConfig

logger = get_logger(__name__)

# Budget allocation ratios (must sum to 1.0)
_BUDGET_SYSTEM: float = 0.15
_BUDGET_ENTITY: float = 0.10
_BUDGET_MEMORIES: float = 0.20
_BUDGET_FEW_SHOT: float = 0.05
_BUDGET_USER: float = 0.40
_BUDGET_RESERVE: float = 0.10

_BUDGET_RATIOS: dict[str, float] = {
    "system": _BUDGET_SYSTEM,
    "entity": _BUDGET_ENTITY,
    "memories": _BUDGET_MEMORIES,
    "few_shot": _BUDGET_FEW_SHOT,
    "user": _BUDGET_USER,
    "reserve": _BUDGET_RESERVE,
}


class AssembledContext:
    """Container for the assembled context components."""

    __slots__ = (
        "memory_context",
        "entity_context",
        "tokens_used",
    )

    def __init__(
        self,
        memory_context: str = "",
        entity_context: str = "",
        tokens_used: int = 0,
    ) -> None:
        self.memory_context = memory_context
        self.entity_context = entity_context
        self.tokens_used = tokens_used


class ContextAssembler:
    """Assembles prompt context within a token budget.

    Allocates budget proportionally across components, with unused
    budget from empty components redistributed to others.
    """

    def __init__(self, config: MemoryConfig) -> None:
        self._config = config

    def assemble(
        self,
        memories: list[RetrievalResult] | None = None,
        entity: EntityProfile | None = None,
        few_shot_examples: list[str] | None = None,
        user_content: str = "",
        system_prompt: str = "",
    ) -> AssembledContext:
        """Assemble context components within token budget.

        Args:
            memories: Retrieved memory results (scored and sorted).
            entity: Entity profile for the conversation partner.
            few_shot_examples: Good response examples for the prompt.
            user_content: The user's message or post content.
            system_prompt: The bot's system/personality prompt.

        Returns:
            AssembledContext with formatted memory_context and entity_context.
        """
        total_budget = self._config.context_total_budget
        budgets = self._calculate_budgets(
            total_budget=total_budget,
            has_entity=entity is not None,
            has_memories=bool(memories),
            has_few_shot=bool(few_shot_examples),
            has_user=bool(user_content),
            has_system=bool(system_prompt),
        )

        # Format entity context
        entity_text = ""
        if entity is not None:
            entity_text = self._format_entity(entity)
            entity_text = truncate_to_budget(entity_text, budgets["entity"])

        # Format memory context
        memory_text = ""
        if memories:
            memory_text = self._format_memories(memories, budgets["memories"])

        tokens_used = estimate_tokens(entity_text) + estimate_tokens(memory_text)

        return AssembledContext(
            memory_context=memory_text,
            entity_context=entity_text,
            tokens_used=tokens_used,
        )

    # ------------------------------------------------------------------
    # Budget calculation
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_budgets(
        total_budget: int,
        has_entity: bool,
        has_memories: bool,
        has_few_shot: bool,
        has_user: bool,
        has_system: bool,
    ) -> dict[str, int]:
        """Calculate per-component token budgets with redistribution.

        Empty components donate their budget proportionally to active ones.
        """
        active: dict[str, float] = {}
        inactive_budget = 0.0

        component_present = {
            "system": has_system,
            "entity": has_entity,
            "memories": has_memories,
            "few_shot": has_few_shot,
            "user": has_user,
            "reserve": True,  # Always active
        }

        for name, ratio in _BUDGET_RATIOS.items():
            if component_present.get(name, False):
                active[name] = ratio
            else:
                inactive_budget += ratio

        # Redistribute inactive budget proportionally
        if active and inactive_budget > 0:
            active_total = sum(active.values())
            if active_total > 0:
                for name in active:
                    active[name] += inactive_budget * (active[name] / active_total)

        # Convert ratios to token counts
        budgets: dict[str, int] = {}
        for name in _BUDGET_RATIOS:
            ratio = active.get(name, 0.0)
            budgets[name] = int(total_budget * ratio)

        return budgets

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _format_entity(entity: EntityProfile) -> str:
        """Format entity profile into readable context."""
        parts: list[str] = []

        display = entity.display_name or entity.entity_name
        parts.append(f"[{display} 프로필]")

        if entity.summary:
            parts.append(entity.summary)

        if entity.interests_json and entity.interests_json != "[]":
            try:
                import json
                interests = json.loads(entity.interests_json)
                if interests:
                    parts.append(f"관심사: {', '.join(interests)}")
            except (ValueError, TypeError):
                pass

        if entity.personality_notes:
            parts.append(f"성격: {entity.personality_notes}")

        parts.append(
            f"상호작용: {entity.interaction_count}회 | "
            f"감정: {entity.sentiment} | "
            f"신뢰도: {entity.trust_level:.1f}"
        )

        return "\n".join(parts)

    @staticmethod
    def _format_memories(
        memories: list[RetrievalResult],
        budget: int,
    ) -> str:
        """Format memories into context text, fitting within token budget.

        Iterates through sorted memories (highest score first), adding
        each one until the budget is exhausted.
        """
        if not memories:
            return ""

        lines: list[str] = ["[관련 기억]"]
        used_tokens = estimate_tokens(lines[0])

        for result in memories:
            node = result.node
            line = f"- {node.content}"

            # Add importance marker for high-value memories
            if node.importance >= 0.8:
                line += " [중요]"

            line_tokens = estimate_tokens(line)
            if used_tokens + line_tokens > budget:
                break

            lines.append(line)
            used_tokens += line_tokens

        if len(lines) <= 1:
            return ""

        return "\n".join(lines)
