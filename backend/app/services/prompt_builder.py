from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import Config
from app.core.constants import MIN_COMMENT_LENGTH
from app.core.logging import get_logger
from app.core.security import SecurityFilter

if TYPE_CHECKING:
    from app.models.collected_info import CollectedInfo
    from app.models.memory import BotMemory
    from app.models.mission import Mission
    from app.models.platform import PlatformComment, PlatformNotification, PlatformPost

logger = get_logger(__name__)


class PromptBuilder:
    """Centralized prompt construction for all LLM calls.

    Injects personality, memory context, and mission awareness into prompts,
    replacing the inline prompt strings previously scattered across strategy.py.
    """

    def __init__(
        self,
        config: Config,
        security_filter: SecurityFilter,
    ) -> None:
        self._config = config
        self._security = security_filter

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def build_system_prompt(self) -> str:
        """Build a system prompt from PersonalityConfig.

        If ``config.personality.system_prompt`` is non-empty, use it directly.
        Otherwise, auto-generate from traits, interests, expertise, and backstory.
        """
        p = self._config.personality
        bot_name = self._config.bot.name

        if p.system_prompt.strip():
            return p.system_prompt.strip()

        parts: list[str] = []
        parts.append(f"당신은 '{bot_name}'이라는 이름의 AI 봇입니다.")

        if p.backstory:
            parts.append(f"배경: {p.backstory}")

        if p.traits:
            parts.append(f"성격: {', '.join(p.traits)}")

        if p.interests:
            parts.append(f"관심사: {', '.join(p.interests)}")

        if p.expertise:
            parts.append(f"전문 분야: {', '.join(p.expertise)}")

        style_map = {
            "casual": "친근하고 편안한 어투를 사용합니다.",
            "formal": "정중하고 격식있는 어투를 사용합니다.",
            "technical": "기술적이고 정확한 어투를 사용합니다.",
        }
        parts.append(style_map.get(p.style, style_map["casual"]))

        parts.append("자연스러운 한국어로 대화하며, 자신만의 의견과 관점을 가지고 있습니다.")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Comment prompt
    # ------------------------------------------------------------------

    def build_comment_prompt(
        self,
        post: PlatformPost,
        *,
        memories: list[BotMemory] | None = None,
        related_info: list[CollectedInfo] | None = None,
    ) -> str:
        """Build a prompt for generating a comment on a post."""
        sanitize = self._security.sanitize_input
        sections: list[str] = []

        # Post info
        sections.append("다음 글에 대한 자연스러운 댓글을 작성해주세요.")
        sections.append(f"- 최소 {MIN_COMMENT_LENGTH}자 이상")
        sections.append("- 글의 내용에 대한 의견이나 공감을 담아주세요")
        sections.append("- 자신의 경험이나 관점을 자연스럽게 녹여주세요")
        sections.append("")
        sections.append(f"글 제목: {sanitize(post.title or '(없음)')}")
        sections.append(f"글 내용: {sanitize(post.content or '(없음)')}")
        if post.author:
            sections.append(f"작성자: {sanitize(post.author)}")

        # Memory context: what we know about the author
        if memories:
            author_memory = next(
                (m for m in memories if m.entity_name == post.author), None
            )
            if author_memory and author_memory.interaction_count > 0:
                sections.append("")
                sections.append(f"[참고] 이 봇({sanitize(post.author or '')})과는 "
                              f"이전에 {author_memory.interaction_count}번 상호작용했습니다.")
                if author_memory.topics:
                    sections.append(f"주로 다루는 주제: {', '.join(author_memory.topics[:5])}")
                if author_memory.relationship_notes:
                    sections.append(f"관계 메모: {author_memory.relationship_notes[:200]}")

        # Related collected info
        if related_info:
            sections.append("")
            sections.append("[참고] 관련 기억:")
            for info in related_info[:3]:
                preview = (info.content or "")[:100]
                sections.append(f"- {sanitize(info.title or '무제')}: {sanitize(preview)}")

        sections.append("")
        sections.append("댓글:")

        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Reply prompt
    # ------------------------------------------------------------------

    def build_reply_prompt(
        self,
        notification: PlatformNotification,
        original_post: PlatformPost,
        conversation: list[PlatformComment],
        *,
        bot_memory: BotMemory | None = None,
    ) -> str:
        """Build a prompt for generating a reply to a notification."""
        sanitize = self._security.sanitize_input
        sections: list[str] = []

        sections.append(f"원글 제목: {sanitize(original_post.title or '(없음)')}")
        sections.append(f"원글 내용: {sanitize(original_post.content or '(없음)')}")
        sections.append("")

        # Conversation thread
        if conversation:
            sections.append("댓글 스레드:")
            for c in conversation:
                sections.append(
                    f"- {sanitize(c.author or '???')}: {sanitize(c.content or '')}"
                )
            sections.append("")

        sections.append(f"알림 내용: {sanitize(notification.content_preview or '(없음)')}")
        sections.append(f"작성자: {sanitize(notification.actor_name or '???')}")

        # Memory about the responder
        if bot_memory and bot_memory.interaction_count > 0:
            sections.append("")
            sections.append(f"[참고] {sanitize(notification.actor_name or '')}과의 "
                          f"이전 상호작용: {bot_memory.interaction_count}번")
            if bot_memory.relationship_notes:
                sections.append(f"관계 메모: {bot_memory.relationship_notes[:200]}")

        sections.append("")
        sections.append("위 문맥에 맞게 자연스러운 답글을 작성해주세요.")
        sections.append(f"- 최소 {MIN_COMMENT_LENGTH}자 이상")
        sections.append("- 이전 대화 흐름을 고려해주세요")
        sections.append("")
        sections.append("답글:")

        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Post prompt
    # ------------------------------------------------------------------

    def build_post_prompt(
        self,
        topic: str,
        *,
        related_memories: list[CollectedInfo] | None = None,
        is_mission: bool = False,
        mission_hint: str = "",
    ) -> str:
        """Build a prompt for generating a new post."""
        sanitize = self._security.sanitize_input
        sections: list[str] = []

        if is_mission and mission_hint:
            sections.append(
                f"'{sanitize(topic)}'에 대해 궁금한 점이 있어서 글을 올리려 합니다."
            )
            sections.append(f"힌트: {sanitize(mission_hint)}")
            sections.append("자신이 진심으로 궁금해하는 것처럼 자연스럽게 질문을 작성해주세요.")
            sections.append("다른 봇들이 자신의 경험이나 지식을 나눠줄 수 있도록 열린 질문으로.")
        else:
            sections.append(f"주제: {sanitize(topic)}")
            sections.append("이 주제에 대해 자신의 생각이나 경험을 담은 글을 작성해주세요.")

        # Related info as reference
        if related_memories:
            sections.append("")
            sections.append("[참고 자료]")
            for info in related_memories[:3]:
                preview = (info.content or "")[:150]
                sections.append(f"- {sanitize(info.title or '무제')}: {sanitize(preview)}")

        sections.append("")
        sections.append("다음 형식으로 작성해주세요:")
        sections.append("제목: (한 줄 제목)")
        sections.append("내용: (본문)")
        sections.append("커뮤니티: (적절한 커뮤니티 이름)")

        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Mission-specific prompts
    # ------------------------------------------------------------------

    def build_mission_question_prompt(
        self,
        mission: Mission,
        related_posts: list[PlatformPost] | None = None,
        warmup_context: list[str] | None = None,
    ) -> str:
        """Build a prompt for the mission's main question post.

        Uses warmup activity context to make the question feel like
        a natural continuation of the bot's recent interests.
        """
        sanitize = self._security.sanitize_input
        sections: list[str] = []

        sections.append(f"'{sanitize(mission.topic)}'에 대해 다른 봇들에게 물어보려 합니다.")

        if mission.question_hint:
            sections.append(f"구체적으로: {sanitize(mission.question_hint)}")

        # Warmup context: what we've been saying recently
        if warmup_context:
            sections.append("")
            sections.append("최근 관련 활동 (자연스러운 흐름을 위해 참고):")
            for ctx in warmup_context[:5]:
                sections.append(f"- {ctx[:100]}")

        # Related posts we've seen
        if related_posts:
            sections.append("")
            sections.append("최근 본 관련 글들:")
            for p in related_posts[:3]:
                sections.append(f"- {sanitize(p.title or '무제')}")

        sections.append("")
        sections.append("위 맥락을 고려해서, 자연스럽게 궁금한 점을 질문하는 글을 작성해주세요.")
        sections.append("- 자신이 진심으로 고민하고 있는 것처럼")
        sections.append("- 다른 봇들이 자신의 경험을 나눌 수 있도록 열린 질문으로")
        sections.append("- 워밍업 활동과 맥락이 이어지도록")
        sections.append("")
        sections.append("다음 형식으로 작성해주세요:")
        sections.append("제목: (한 줄 제목)")
        sections.append("내용: (본문)")
        sections.append("커뮤니티: (적절한 커뮤니티 이름)")

        return "\n".join(sections)

    def build_warmup_comment_prompt(
        self,
        post: PlatformPost,
        mission: Mission,
    ) -> str:
        """Build a prompt for a warmup comment (mission-related, interest-showing)."""
        sanitize = self._security.sanitize_input
        sections: list[str] = []

        sections.append(f"글 제목: {sanitize(post.title or '(없음)')}")
        sections.append(f"글 내용: {sanitize(post.content or '(없음)')}")
        sections.append("")
        sections.append(
            f"이 글은 '{sanitize(mission.topic)}'와 관련이 있습니다. "
            "이 주제에 관심을 보이는 자연스러운 댓글을 작성해주세요."
        )
        sections.append("- 자신도 이 주제에 관심이 있다는 것을 자연스럽게 드러내기")
        sections.append("- 질문하거나 공감하는 형태로")
        sections.append(f"- 최소 {MIN_COMMENT_LENGTH}자 이상")
        sections.append("")
        sections.append("댓글:")

        return "\n".join(sections)

    def build_summary_prompt(
        self,
        mission: Mission,
    ) -> str:
        """Build a prompt for summarizing collected mission responses."""
        sections: list[str] = []

        sections.append(f"주제: {mission.topic}")
        if mission.question_hint:
            sections.append(f"질문 의도: {mission.question_hint}")
        sections.append("")

        responses = mission.collected_responses or []
        sections.append(f"수집된 응답 ({len(responses)}개):")
        for i, resp in enumerate(responses, 1):
            author = resp.get("author", "알 수 없음")
            content = resp.get("content", "")[:300]
            sections.append(f"\n응답 {i} ({author}):")
            sections.append(content)

        sections.append("")
        sections.append("위 응답들을 분석하여 다음을 포함한 요약을 작성해주세요:")
        sections.append("1. 핵심 정보와 공통된 의견")
        sections.append("2. 서로 다른 관점이나 접근법")
        sections.append("3. 가장 유용한 정보")
        sections.append("4. 추가로 알아볼 필요가 있는 부분")

        return "\n".join(sections)

    def build_mission_detect_prompt(self, user_message: str) -> str:
        """Build a prompt for detecting if a chat message is a mission request."""
        sanitize = self._security.sanitize_input
        return (
            "다음 메시지가 '정보 수집 요청'인지 판단하세요.\n"
            "정보 수집 요청 = 뭔가를 알아봐 달라, 조사해 달라, "
            "다른 봇들에게 물어봐 달라는 요청.\n"
            "일반 대화 = 단순 질문, 잡담, 명령, 설정 변경.\n\n"
            f"메시지: \"{sanitize(user_message)}\"\n\n"
            "반드시 다음 JSON 형식으로만 응답하세요:\n"
            '{"is_mission": true/false, "topic": "주제", "urgency": "normal"}\n'
            "urgency는 immediate(바로), normal(보통), patient(여유있게) 중 하나."
        )

    def build_followup_prompt(
        self,
        mission: Mission,
        response: dict,
    ) -> str:
        """Build a prompt for a follow-up reaction to a mission response."""
        sanitize = self._security.sanitize_input
        author = response.get("author", "???")
        content = response.get("content", "")[:300]

        sections: list[str] = []
        sections.append(f"내 질문 주제: {sanitize(mission.topic)}")
        sections.append(f"\n{sanitize(author)}의 답변:")
        sections.append(sanitize(content))
        sections.append("")
        sections.append("이 답변에 대한 자연스러운 후속 반응을 작성해주세요.")
        sections.append("- 감사 표현, 추가 질문, 또는 의견 공유 중 하나로")
        sections.append("- 대화를 이어갈 수 있도록")
        sections.append(f"- 최소 {MIN_COMMENT_LENGTH}자 이상")
        sections.append("")
        sections.append("답글:")

        return "\n".join(sections)
