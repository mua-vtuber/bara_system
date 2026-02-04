from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from pydantic import Field as PydanticField

from app.core.config import Config
from app.core.constants import MIN_COMMENT_LENGTH
from app.core.events import EventBus
from app.core.logging import get_logger
from app.core.security import SecurityFilter
from app.models.activity import Activity, DailyCounts, DailyLimits
from app.models.base import BaseModel
from app.models.events import BotResponseGeneratedEvent
from app.models.platform import PlatformComment, PlatformNotification, PlatformPost
from app.repositories.activity import ActivityRepository
from app.services.llm import LLMService
from app.services.prompt_builder import PromptBuilder

logger = get_logger(__name__)


# ------------------------------------------------------------------
# Decision / quality-check models
# ------------------------------------------------------------------


class CommentDecision(BaseModel):
    """Result of evaluating whether to comment on a post."""

    should_comment: bool
    reason: str
    priority: int = 5  # 1 = highest, 10 = lowest
    delay_seconds: int = 0


class QualityCheckedComment(BaseModel):
    """A generated comment with quality-check metadata."""

    content: str
    passed: bool
    issues: list[str] = PydanticField(default_factory=list)
    korean_ratio: float | None = None
    length: int = 0


class QualityCheckedPost(BaseModel):
    """A generated post with quality-check metadata."""

    title: str
    content: str
    community: str
    passed: bool
    issues: list[str] = PydanticField(default_factory=list)


# ------------------------------------------------------------------
# Strategy context
# ------------------------------------------------------------------


@dataclass
class StrategyContext:
    """Snapshot of state needed by a :class:`BehaviorStrategy`."""

    daily_counts: DailyCounts
    daily_limits: DailyLimits
    interest_keywords: list[str]
    recent_activities: list[Activity]
    current_time: datetime
    active_hours: dict[str, dict[str, int]] = field(default_factory=dict)
    # Example: {"weekday": {"start": 9, "end": 22}, "weekend": {"start": 10, "end": 20}}


# ------------------------------------------------------------------
# Abstract strategy
# ------------------------------------------------------------------


class BehaviorStrategy(ABC):
    """Defines *when* and *how* the bot should act -- without LLM calls."""

    @abstractmethod
    def should_comment(
        self, post: PlatformPost, context: StrategyContext
    ) -> CommentDecision: ...

    @abstractmethod
    def should_post(self, context: StrategyContext) -> bool: ...

    @abstractmethod
    def should_upvote(
        self, post: PlatformPost, context: StrategyContext
    ) -> bool: ...

    @abstractmethod
    def select_community(
        self, content: str, communities: list[str]
    ) -> str: ...

    @abstractmethod
    def prioritize_posts(
        self, posts: list[PlatformPost], context: StrategyContext
    ) -> list[PlatformPost]: ...


# ------------------------------------------------------------------
# Default strategy implementation
# ------------------------------------------------------------------


class DefaultBehaviorStrategy(BehaviorStrategy):
    """Rule-based strategy aligned with spec section 5.2."""

    def __init__(self, config: Config) -> None:
        self._config = config

    # -- helpers -------------------------------------------------------

    def _is_active_hour(self, ctx: StrategyContext) -> bool:
        """Return ``True`` when *current_time* falls inside configured hours."""
        now = ctx.current_time
        is_weekend = now.weekday() >= 5
        key = "weekend" if is_weekend else "weekday"
        hours = ctx.active_hours.get(key, {})
        start = hours.get("start", 9)
        end = hours.get("end", 22)
        return start <= now.hour < end

    def _keyword_match_count(
        self, text: str, keywords: list[str]
    ) -> int:
        """Count how many *keywords* appear in *text* (case-insensitive)."""
        if not text:
            return 0
        lower = text.lower()
        return sum(1 for kw in keywords if kw.lower() in lower)

    def _already_responded(
        self, post: PlatformPost, recent: list[Activity]
    ) -> bool:
        return any(
            a.platform_post_id == post.post_id for a in recent
        )

    def _jitter(self) -> int:
        lo, hi = self._config.behavior.comment_strategy.jitter_range_seconds
        return random.randint(lo, hi)

    # -- interface implementation --------------------------------------

    def should_comment(
        self, post: PlatformPost, context: StrategyContext
    ) -> CommentDecision:
        # 1) Active hours
        if not self._is_active_hour(context):
            return CommentDecision(
                should_comment=False, reason="Outside active hours"
            )

        # 2) Daily limit
        if context.daily_counts.comments >= context.daily_limits.max_comments:
            return CommentDecision(
                should_comment=False, reason="Daily comment limit reached"
            )

        # 3) Already responded
        if self._already_responded(post, context.recent_activities):
            return CommentDecision(
                should_comment=False, reason="Already responded to this post"
            )

        # 4) Keyword matching
        combined_text = f"{post.title or ''} {post.content or ''}"
        match_count = self._keyword_match_count(
            combined_text, context.interest_keywords
        )
        if match_count == 0:
            return CommentDecision(
                should_comment=False, reason="No interest-keyword match"
            )

        # 5) Priority inversely proportional to match count (more matches -> lower number = higher priority)
        priority = max(1, 10 - match_count)
        delay = self._jitter()

        return CommentDecision(
            should_comment=True,
            reason=f"Matched {match_count} keyword(s)",
            priority=priority,
            delay_seconds=delay,
        )

    def should_post(self, context: StrategyContext) -> bool:
        if not self._is_active_hour(context):
            return False
        return context.daily_counts.posts < context.daily_limits.max_posts

    def should_upvote(
        self, post: PlatformPost, context: StrategyContext
    ) -> bool:
        if not self._is_active_hour(context):
            return False
        if context.daily_counts.upvotes >= context.daily_limits.max_upvotes:
            return False
        combined_text = f"{post.title or ''} {post.content or ''}"
        return self._keyword_match_count(combined_text, context.interest_keywords) > 0

    def select_community(
        self, content: str, communities: list[str]
    ) -> str:
        """Pick the community whose name best matches *content* keywords."""
        if not communities:
            return ""
        lower = content.lower()
        best, best_score = communities[0], 0
        for community in communities:
            # Simple heuristic: count how many community-name tokens appear
            tokens = community.lower().replace("_", " ").replace("-", " ").split()
            score = sum(1 for tok in tokens if tok in lower)
            if score > best_score:
                best_score = score
                best = community
        return best

    def prioritize_posts(
        self, posts: list[PlatformPost], context: StrategyContext
    ) -> list[PlatformPost]:
        """Sort *posts* by keyword-match score descending."""

        def _score(p: PlatformPost) -> int:
            combined = f"{p.title or ''} {p.content or ''}"
            return self._keyword_match_count(combined, context.interest_keywords)

        return sorted(posts, key=_score, reverse=True)


# ------------------------------------------------------------------
# Strategy Engine (orchestrates strategy + LLM + quality checks)
# ------------------------------------------------------------------


class StrategyEngine:
    """High-level facade that pairs a :class:`BehaviorStrategy` with LLM
    generation and quality/security filtering.
    """

    def __init__(
        self,
        strategy: BehaviorStrategy,
        llm_service: LLMService,
        config: Config,
        security_filter: SecurityFilter,
        event_bus: EventBus | None = None,
    ) -> None:
        self._strategy = strategy
        self._llm = llm_service
        self._config = config
        self._security = security_filter
        self._prompt_builder: PromptBuilder | None = None
        self._event_bus = event_bus

    def set_prompt_builder(self, prompt_builder: PromptBuilder) -> None:
        """Inject prompt builder for personality-aware prompt generation."""
        self._prompt_builder = prompt_builder

    # ------------------------------------------------------------------
    # Evaluate
    # ------------------------------------------------------------------

    async def evaluate_post(
        self,
        post: PlatformPost,
        platform: str,
        activity_repo: ActivityRepository,
    ) -> CommentDecision:
        """Decide whether to comment on *post* using the active strategy."""
        today = date.today()
        daily_counts = await activity_repo.get_daily_counts(platform, today)

        recent = await activity_repo.get_timeline(
            platform_filter=platform, limit=100
        )

        behavior = self._config.behavior
        daily_limits = DailyLimits(
            max_comments=behavior.daily_limits.max_comments,
            max_posts=behavior.daily_limits.max_posts,
            max_upvotes=behavior.daily_limits.max_upvotes,
        )

        active_hours = {
            "weekday": {
                "start": behavior.active_hours.weekday.start,
                "end": behavior.active_hours.weekday.end,
            },
            "weekend": {
                "start": behavior.active_hours.weekend.start,
                "end": behavior.active_hours.weekend.end,
            },
        }

        ctx = StrategyContext(
            daily_counts=daily_counts,
            daily_limits=daily_limits,
            interest_keywords=behavior.interest_keywords,
            recent_activities=recent,
            current_time=datetime.now(),
            active_hours=active_hours,
        )

        return self._strategy.should_comment(post, ctx)

    # ------------------------------------------------------------------
    # Generate comment
    # ------------------------------------------------------------------

    async def generate_comment(
        self, post: PlatformPost, platform: str
    ) -> QualityCheckedComment:
        """Generate a comment for *post* via LLM, then quality-check it."""
        fewshot_context = ""
        if self._prompt_builder:
            # Build few-shot context from good examples
            topic_text = f"{post.title or ''} {post.content or ''}"[:200]
            try:
                fewshot_context = await self._prompt_builder.build_fewshot_context(
                    topic_text, action_type="comment", limit=2
                )
            except Exception as exc:
                logger.debug("Few-shot context build failed: %s", exc)

            prompt = self._prompt_builder.build_comment_prompt(
                post, fewshot_context=fewshot_context
            )
            system = self._prompt_builder.build_system_prompt()
        else:
            bot_name = self._config.bot.name
            owner_name = self._config.bot.owner_name
            prompt = (
                f"당신은 AI 에이전트 SNS에서 활동하는 봇 '{bot_name}'입니다.\n"
                f"주인인 '{owner_name}'의 관점에서 자연스럽게 댓글을 작성합니다.\n\n"
                "다음 글에 대한 자연스러운 한국어 댓글을 작성해주세요.\n"
                f"- 최소 {MIN_COMMENT_LENGTH}자 이상\n"
                "- 글의 내용에 대한 의견이나 공감을 담아주세요\n"
                "- 너무 형식적이지 않게, 친근한 어투로\n\n"
                f"글 제목: {self._security.sanitize_input(post.title or '(없음)')}\n"
                f"글 내용: {self._security.sanitize_input(post.content or '(없음)')}\n\n"
                "댓글:"
            )
            system = None

        try:
            response = await self._llm.generate(prompt, system=system)
            content = response.strip() if isinstance(response, str) else ""
        except Exception as exc:
            logger.error("LLM comment generation failed: %s", exc)
            return QualityCheckedComment(
                content="",
                passed=False,
                issues=[f"LLM generation error: {exc}"],
            )

        # Publish event for auto-capture
        if self._event_bus and content:
            try:
                await self._event_bus.publish(BotResponseGeneratedEvent(
                    platform=platform,
                    action_type="comment",
                    original_content=f"{post.title or ''}\n{post.content or ''}"[:500],
                    bot_response=content,
                    post_id=post.post_id,
                    author=post.author or "",
                ))
            except Exception as exc:
                logger.debug("Failed to publish BotResponseGeneratedEvent: %s", exc)

        return self._check_quality(content, platform)

    # ------------------------------------------------------------------
    # Generate reply
    # ------------------------------------------------------------------

    async def generate_reply(
        self,
        notification: PlatformNotification,
        original_post: PlatformPost,
        conversation_context: list[PlatformComment],
    ) -> QualityCheckedComment:
        """Generate a reply based on notification context."""
        if self._prompt_builder:
            prompt = self._prompt_builder.build_reply_prompt(
                notification, original_post, conversation_context
            )
            system = self._prompt_builder.build_system_prompt()
        else:
            bot_name = self._config.bot.name
            owner_name = self._config.bot.owner_name

            thread_text = "\n".join(
                f"- {self._security.sanitize_input(c.author or '???')}: {self._security.sanitize_input(c.content or '')}"
                for c in conversation_context
            )

            prompt = (
                f"당신은 AI 에이전트 SNS에서 활동하는 봇 '{bot_name}'입니다.\n"
                f"주인인 '{owner_name}'의 관점에서 자연스럽게 답글을 작성합니다.\n\n"
                f"원글 제목: {self._security.sanitize_input(original_post.title or '(없음)')}\n"
                f"원글 내용: {self._security.sanitize_input(original_post.content or '(없음)')}\n\n"
                f"댓글 스레드:\n{thread_text}\n\n"
                f"알림 내용: {self._security.sanitize_input(notification.content_preview or '(없음)')}\n"
                f"작성자: {self._security.sanitize_input(notification.actor_name or '???')}\n\n"
                "위 문맥에 맞게 자연스러운 한국어 답글을 작성해주세요.\n"
                f"- 최소 {MIN_COMMENT_LENGTH}자 이상\n"
                "- 이전 대화 흐름을 고려해주세요\n\n"
                "답글:"
            )
            system = None

        try:
            response = await self._llm.generate(prompt, system=system)
            content = response.strip() if isinstance(response, str) else ""
        except Exception as exc:
            logger.error("LLM reply generation failed: %s", exc)
            return QualityCheckedComment(
                content="",
                passed=False,
                issues=[f"LLM generation error: {exc}"],
            )

        # Publish event for auto-capture
        if self._event_bus and content:
            try:
                await self._event_bus.publish(BotResponseGeneratedEvent(
                    platform=notification.platform,
                    action_type="reply",
                    original_content=(notification.content_preview or "")[:500],
                    bot_response=content,
                    post_id=original_post.post_id,
                    author=notification.actor_name or "",
                ))
            except Exception as exc:
                logger.debug("Failed to publish BotResponseGeneratedEvent: %s", exc)

        return self._check_quality(content, notification.platform)

    # ------------------------------------------------------------------
    # Generate post
    # ------------------------------------------------------------------

    async def generate_post(
        self, topic: str, platform: str
    ) -> QualityCheckedPost:
        """Generate a new post about *topic* via LLM."""
        if self._prompt_builder:
            prompt = self._prompt_builder.build_post_prompt(topic)
            system = self._prompt_builder.build_system_prompt()
        else:
            bot_name = self._config.bot.name
            owner_name = self._config.bot.owner_name

            prompt = (
                f"당신은 AI 에이전트 SNS에서 활동하는 봇 '{bot_name}'입니다.\n"
                f"주인인 '{owner_name}'의 관점에서 새 글을 작성합니다.\n\n"
                f"주제: {self._security.sanitize_input(topic)}\n\n"
                "다음 형식으로 작성해주세요:\n"
                "제목: (한 줄 제목)\n"
                "내용: (본문)\n"
                "커뮤니티: (적절한 커뮤니티 이름)\n\n"
                "자연스러운 한국어로 작성하고, 제목과 내용을 구분해서 출력해주세요."
            )
            system = None

        try:
            response = await self._llm.generate(prompt, system=system)
            raw = response.strip() if isinstance(response, str) else ""
        except Exception as exc:
            logger.error("LLM post generation failed: %s", exc)
            return QualityCheckedPost(
                title="",
                content="",
                community="",
                passed=False,
                issues=[f"LLM generation error: {exc}"],
            )

        title, content, community = self._parse_post_response(raw)

        # Publish event for auto-capture
        if self._event_bus and content:
            try:
                await self._event_bus.publish(BotResponseGeneratedEvent(
                    platform=platform,
                    action_type="post",
                    original_content=topic[:500],
                    bot_response=f"{title}\n{content}"[:500],
                    post_id="",
                    author="",
                ))
            except Exception as exc:
                logger.debug("Failed to publish BotResponseGeneratedEvent: %s", exc)

        issues: list[str] = []
        if not title:
            issues.append("Empty title")
        if not content:
            issues.append("Empty content")
        if len(content) < MIN_COMMENT_LENGTH:
            issues.append(
                f"Content too short ({len(content)} < {MIN_COMMENT_LENGTH})"
            )

        security_result = self._security.filter_content(f"{title} {content}")
        if not security_result.passed:
            issues.append(f"Security filter: {security_result.reason}")

        return QualityCheckedPost(
            title=title,
            content=content,
            community=community,
            passed=len(issues) == 0,
            issues=issues,
        )

    # ------------------------------------------------------------------
    # Upvote decision
    # ------------------------------------------------------------------

    async def should_upvote(
        self,
        post: PlatformPost,
        platform: str,
        activity_repo: ActivityRepository,
    ) -> bool:
        """Decide whether to upvote *post*."""
        today = date.today()
        daily_counts = await activity_repo.get_daily_counts(platform, today)
        behavior = self._config.behavior

        daily_limits = DailyLimits(
            max_comments=behavior.daily_limits.max_comments,
            max_posts=behavior.daily_limits.max_posts,
            max_upvotes=behavior.daily_limits.max_upvotes,
        )

        active_hours = {
            "weekday": {
                "start": behavior.active_hours.weekday.start,
                "end": behavior.active_hours.weekday.end,
            },
            "weekend": {
                "start": behavior.active_hours.weekend.start,
                "end": behavior.active_hours.weekend.end,
            },
        }

        ctx = StrategyContext(
            daily_counts=daily_counts,
            daily_limits=daily_limits,
            interest_keywords=behavior.interest_keywords,
            recent_activities=[],
            current_time=datetime.now(),
            active_hours=active_hours,
        )

        return self._strategy.should_upvote(post, ctx)

    # ------------------------------------------------------------------
    # Quality check (internal)
    # ------------------------------------------------------------------

    def _check_quality(
        self, content: str, platform: str
    ) -> QualityCheckedComment:
        """Run quality and security checks on generated *content*."""
        issues: list[str] = []

        # Empty check
        if not content:
            issues.append("Empty response from LLM")
            return QualityCheckedComment(
                content="", passed=False, issues=issues, length=0
            )

        length = len(content)
        min_len = self._config.behavior.comment_strategy.min_quality_length

        # Minimum length
        if length < min_len:
            issues.append(f"Too short ({length} < {min_len})")

        # Korean ratio
        threshold = self._config.behavior.comment_strategy.korean_ratio_threshold
        ratio = SecurityFilter.calculate_korean_ratio(content)
        if ratio < threshold:
            issues.append(
                f"Korean ratio too low ({ratio:.2f} < {threshold:.2f})"
            )

        # Security filter
        security_result = self._security.filter_content(content)
        if not security_result.passed:
            issues.append(f"Security filter: {security_result.reason}")

        return QualityCheckedComment(
            content=content,
            passed=len(issues) == 0,
            issues=issues,
            korean_ratio=ratio,
            length=length,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_post_response(raw: str) -> tuple[str, str, str]:
        """Parse LLM output that contains '제목:', '내용:', '커뮤니티:' markers."""
        title = ""
        content = ""
        community = ""

        lines = raw.split("\n")
        current_section: str | None = None
        content_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("제목:"):
                current_section = "title"
                title = stripped[len("제목:"):].strip()
            elif stripped.startswith("내용:"):
                current_section = "content"
                first = stripped[len("내용:"):].strip()
                if first:
                    content_lines.append(first)
            elif stripped.startswith("커뮤니티:"):
                current_section = "community"
                community = stripped[len("커뮤니티:"):].strip()
            elif current_section == "content":
                content_lines.append(line)

        if content_lines:
            content = "\n".join(content_lines).strip()

        return title, content, community
