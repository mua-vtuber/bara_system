from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel as PydanticBaseModel

from app.api.dependencies import get_conversation_repo, get_llm_service
from app.core.logging import get_logger
from app.models.conversation import Conversation, ConversationCreate
from app.repositories.conversation import ConversationRepository
from app.services.llm import LLMService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ------------------------------------------------------------------
# Request / response schemas
# ------------------------------------------------------------------


class ChatRequest(PydanticBaseModel):
    message: str
    platform: str = "chat"


class ChatResponse(PydanticBaseModel):
    response: str
    conversation_id: int


class HistoryResponse(PydanticBaseModel):
    conversations: list[Conversation]
    total: int


# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

_MAX_HISTORY_CONTEXT: int = 20


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@router.post("", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    request: Request,
    llm_service: LLMService = Depends(get_llm_service),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
) -> ChatResponse:
    """Send a chat message and receive the LLM response (non-streaming)."""
    max_len = request.app.state.config.web_security.max_message_length
    if len(body.message) > max_len:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Message too long (max {max_len} characters)"},
        )

    # 1. Save user message
    user_entry = await conversation_repo.add(
        ConversationCreate(
            role="user",
            content=body.message,
            platform=body.platform,
        )
    )

    # 2. Check for mission intent
    mission_service = getattr(request.app.state, "mission_service", None)
    prompt_builder = getattr(request.app.state, "prompt_builder", None)
    mission = None

    if mission_service:
        try:
            mission = await mission_service.create_from_chat(body.message)
        except Exception as exc:
            logger.warning("Mission detection failed: %s", exc)

    if mission:
        # Mission created — build confirmation response
        if mission.urgency == "immediate":
            response_text = (
                f"알겠어요! '{mission.topic}'에 대해 바로 알아볼게요. "
                "관련 글을 작성해서 다른 봇들의 의견을 수집할게요."
            )
        else:
            response_text = (
                f"알겠어요! '{mission.topic}'에 대해 알아볼게요. "
                "관련 주제에 관심을 보이면서 자연스럽게 알아볼게요."
            )
        logger.info(
            "Mission #%d created from chat: topic='%s'",
            mission.id, mission.topic,
        )
    else:
        # 3. Regular chat — load history and call LLM
        recent = await conversation_repo.get_history(
            limit=_MAX_HISTORY_CONTEXT,
            platform_filter=body.platform,
        )

        messages: list[dict[str, str]] = []
        for conv in reversed(recent):
            messages.append({"role": conv.role, "content": conv.content})

        # Inject system prompt if prompt_builder is available
        if prompt_builder:
            system_prompt = prompt_builder.build_system_prompt()
            messages.insert(0, {"role": "system", "content": system_prompt})

        response_text = await llm_service.chat(messages, stream=False)
        if not isinstance(response_text, str):
            logger.error("LLM returned non-string response: %s", type(response_text).__name__)
            return JSONResponse(
                status_code=502,
                content={"detail": "Unexpected response from language model"},
            )

    # 4. Save assistant response
    assistant_entry = await conversation_repo.add(
        ConversationCreate(
            role="assistant",
            content=response_text,
            platform=body.platform,
        )
    )

    logger.info(
        "Chat completed: user_msg_id=%d, assistant_msg_id=%d, platform=%s",
        user_entry.id,
        assistant_entry.id,
        body.platform,
    )

    return ChatResponse(
        response=response_text,
        conversation_id=assistant_entry.id,
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    platform: Optional[str] = Query(default=None),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
) -> HistoryResponse:
    """Retrieve conversation history with optional platform filter."""
    conversations = await conversation_repo.get_history(
        limit=limit,
        offset=offset,
        platform_filter=platform,
    )
    return HistoryResponse(
        conversations=conversations,
        total=len(conversations),
    )
