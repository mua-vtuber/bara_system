from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from app.core.config import Config
from app.core.constants import MISSION_MAX_COLLECTING_HOURS
from app.core.logging import get_logger
from app.models.events import (
    MissionCompletedEvent,
    MissionCreatedEvent,
    MissionPostPublishedEvent,
)
from app.models.mission import Mission, MissionCreate, MissionStatus
from app.repositories.mission import MissionRepository

if TYPE_CHECKING:
    from app.core.events import EventBus
    from app.models.platform import PlatformPost
    from app.services.llm import LLMService
    from app.services.memory import MemoryService
    from app.services.prompt_builder import PromptBuilder

logger = get_logger(__name__)


class MissionService:
    """Manages information-gathering missions.

    A mission flows through these states:
    pending -> warmup -> active -> posted -> collecting -> complete

    The bot warms up by commenting on related topics, then posts a
    question disguised as genuine curiosity, collects responses, and
    finally summarizes the results for the user.
    """

    def __init__(
        self,
        mission_repo: MissionRepository,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
        memory_service: MemoryService,
        event_bus: EventBus,
        config: Config,
    ) -> None:
        self._repo = mission_repo
        self._prompt_builder = prompt_builder
        self._llm = llm_service
        self._memory = memory_service
        self._event_bus = event_bus
        self._config = config

    # ------------------------------------------------------------------
    # Mission creation
    # ------------------------------------------------------------------

    async def create_from_chat(self, user_message: str) -> Mission | None:
        """Detect mission intent from a chat message and create if found.

        Returns the created Mission, or None if the message is not a
        mission request.
        """
        detect_prompt = self._prompt_builder.build_mission_detect_prompt(
            user_message
        )
        system = self._prompt_builder.build_system_prompt()

        try:
            raw = await self._llm.generate(detect_prompt, system=system)
            response_text = raw.strip() if isinstance(raw, str) else ""
        except Exception as exc:
            logger.warning("Mission detection LLM call failed: %s", exc)
            return None

        # Parse the JSON response
        parsed = self._parse_detection_response(response_text)
        if parsed is None or not parsed.get("is_mission"):
            return None

        topic = parsed.get("topic", "").strip()
        if not topic:
            return None

        urgency = parsed.get("urgency", "normal")
        if urgency not in ("immediate", "normal", "patient"):
            urgency = "normal"

        return await self.create_mission(
            MissionCreate(
                topic=topic,
                urgency=urgency,
                user_notes=f"원본 메시지: {user_message[:500]}",
            )
        )

    async def create_mission(self, create: MissionCreate) -> Mission:
        """Create a new mission and publish event."""
        mission = await self._repo.add(create)

        await self._event_bus.publish(
            MissionCreatedEvent(
                mission_id=mission.id,
                topic=mission.topic,
                urgency=mission.urgency,
            )
        )

        logger.info(
            "Mission #%d created: topic='%s', urgency=%s",
            mission.id,
            mission.topic,
            mission.urgency,
        )
        return mission

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    async def advance_mission(self, mission: Mission) -> Mission | None:
        """Advance a mission one step in its lifecycle.

        Returns the updated mission, or None if no transition occurred.
        """
        status = mission.status

        if status == MissionStatus.PENDING:
            # immediate urgency skips warmup
            if mission.urgency == "immediate":
                await self._repo.update_status(mission.id, MissionStatus.ACTIVE)
            else:
                await self._repo.update_status(mission.id, MissionStatus.WARMUP)

        elif status == MissionStatus.WARMUP:
            if mission.warmup_count >= mission.warmup_target:
                await self._repo.update_status(mission.id, MissionStatus.ACTIVE)
            else:
                return None  # Still warming up

        elif status == MissionStatus.ACTIVE:
            # Ready to post — actual posting is handled by the caller
            return None

        elif status == MissionStatus.POSTED:
            await self._repo.update_status(
                mission.id, MissionStatus.COLLECTING
            )

        elif status == MissionStatus.COLLECTING:
            if await self.should_complete(mission):
                await self.complete_mission(mission)

        else:
            return None  # Terminal state

        return await self._repo.get(mission.id)

    async def advance_all(self) -> None:
        """Advance all active missions. Called periodically by scheduler."""
        active = await self._repo.get_active()
        for mission in active:
            try:
                await self.advance_mission(mission)
            except Exception as exc:
                logger.error(
                    "Failed to advance mission #%d: %s", mission.id, exc
                )

    # ------------------------------------------------------------------
    # Warmup
    # ------------------------------------------------------------------

    async def execute_warmup(
        self, mission: Mission, post: PlatformPost
    ) -> str | None:
        """Generate a warmup comment for a mission-related post.

        Returns the generated comment text, or None on failure.
        """
        if mission.status != MissionStatus.WARMUP:
            return None

        prompt = self._prompt_builder.build_warmup_comment_prompt(
            post, mission
        )
        system = self._prompt_builder.build_system_prompt()

        try:
            response = await self._llm.generate(prompt, system=system)
            content = response.strip() if isinstance(response, str) else ""
        except Exception as exc:
            logger.error("Warmup comment generation failed: %s", exc)
            return None

        if content:
            new_count = await self._repo.increment_warmup(mission.id)
            logger.info(
                "Mission #%d warmup %d/%d on post '%s'",
                mission.id,
                new_count,
                mission.warmup_target,
                (post.title or "")[:50],
            )

        return content if content else None

    # ------------------------------------------------------------------
    # Post generation
    # ------------------------------------------------------------------

    async def generate_mission_post(
        self, mission: Mission
    ) -> dict | None:
        """Generate the mission's question post.

        Returns {"title": str, "content": str, "community": str} or None.
        """
        if mission.status != MissionStatus.ACTIVE:
            return None

        prompt = self._prompt_builder.build_mission_question_prompt(mission)
        system = self._prompt_builder.build_system_prompt()

        try:
            response = await self._llm.generate(prompt, system=system)
            raw = response.strip() if isinstance(response, str) else ""
        except Exception as exc:
            logger.error("Mission post generation failed: %s", exc)
            return None

        return self._parse_post_response(raw)

    async def record_post(
        self, mission: Mission, platform: str, post_id: str
    ) -> None:
        """Record that the mission question was published."""
        await self._repo.set_post_info(mission.id, platform, post_id)
        await self._repo.update_status(mission.id, MissionStatus.POSTED)

        await self._event_bus.publish(
            MissionPostPublishedEvent(
                mission_id=mission.id,
                platform=platform,
                post_id=post_id,
            )
        )

        logger.info(
            "Mission #%d posted on %s (post_id=%s)",
            mission.id,
            platform,
            post_id,
        )

    # ------------------------------------------------------------------
    # Response collection
    # ------------------------------------------------------------------

    async def add_response(
        self, mission_id: int, response: dict
    ) -> None:
        """Add a collected response to a mission."""
        await self._repo.add_response(mission_id, response)

    async def generate_followup(
        self, mission: Mission, response: dict
    ) -> str | None:
        """Generate a follow-up reaction to a useful response."""
        prompt = self._prompt_builder.build_followup_prompt(
            mission, response
        )
        system = self._prompt_builder.build_system_prompt()

        try:
            raw = await self._llm.generate(prompt, system=system)
            return raw.strip() if isinstance(raw, str) else None
        except Exception as exc:
            logger.warning("Followup generation failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    async def should_complete(self, mission: Mission) -> bool:
        """Determine if a collecting mission should be completed."""
        responses = mission.collected_responses or []

        # Enough responses gathered
        if len(responses) >= 5:
            return True

        # Time-based: check if created_at + MAX hours has passed
        if mission.created_at:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            age_hours = (now - mission.created_at).total_seconds() / 3600
            if age_hours >= MISSION_MAX_COLLECTING_HOURS:
                return True

        return False

    async def complete_mission(self, mission: Mission) -> str:
        """Complete a mission: generate summary and update status."""
        summary = await self.generate_summary(mission)
        await self._repo.set_summary(mission.id, summary)
        await self._repo.update_status(mission.id, MissionStatus.COMPLETE)

        responses = mission.collected_responses or []
        await self._event_bus.publish(
            MissionCompletedEvent(
                mission_id=mission.id,
                topic=mission.topic,
                response_count=len(responses),
            )
        )

        logger.info(
            "Mission #%d completed: '%s' (%d responses)",
            mission.id,
            mission.topic,
            len(responses),
        )
        return summary

    async def generate_summary(self, mission: Mission) -> str:
        """Generate an LLM summary of collected responses."""
        prompt = self._prompt_builder.build_summary_prompt(mission)
        system = self._prompt_builder.build_system_prompt()

        try:
            raw = await self._llm.generate(prompt, system=system)
            return raw.strip() if isinstance(raw, str) else ""
        except Exception as exc:
            logger.error("Summary generation failed: %s", exc)
            return f"요약 생성 실패: {exc}"

    async def cancel_mission(self, mission_id: int) -> None:
        """Cancel a mission."""
        await self._repo.update_status(mission_id, MissionStatus.CANCELLED)
        logger.info("Mission #%d cancelled", mission_id)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    async def get_mission(self, mission_id: int) -> Mission | None:
        return await self._repo.get(mission_id)

    async def get_active_missions(self) -> list[Mission]:
        return await self._repo.get_active()

    async def get_pending_missions(self) -> list[Mission]:
        return await self._repo.get_by_status(MissionStatus.PENDING)

    async def get_all_missions(
        self, limit: int = 50, offset: int = 0
    ) -> list[Mission]:
        return await self._repo.get_all(limit, offset)

    async def count_missions(self) -> int:
        return await self._repo.count()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_detection_response(text: str) -> dict | None:
        """Parse the mission detection LLM response as JSON."""
        # Try to extract JSON from possible markdown fences
        cleaned = text.strip()
        if "```" in cleaned:
            parts = cleaned.split("```")
            for part in parts:
                stripped = part.strip()
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                if stripped.startswith("{"):
                    cleaned = stripped
                    break

        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            logger.debug("Failed to parse mission detection response: %s", text[:200])
            return None

    @staticmethod
    def _parse_post_response(raw: str) -> dict | None:
        """Parse LLM output with 제목/내용/커뮤니티 markers."""
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

        if not title and not content:
            return None

        return {"title": title, "content": content, "community": community}
