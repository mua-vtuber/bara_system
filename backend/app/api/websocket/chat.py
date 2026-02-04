from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.constants import MAX_WS_MESSAGE_BYTES
from app.core.exceptions import LLMConnectionError, LLMGenerationError
from app.core.logging import get_logger
from app.models.conversation import ConversationCreate
from app.repositories.conversation import ConversationRepository
from app.services.llm import LLMService

logger = get_logger(__name__)

_MAX_HISTORY_CONTEXT: int = 20


async def websocket_chat(ws: WebSocket) -> None:
    """WebSocket endpoint for real-time streaming chat.

    Protocol
    --------
    **Client -> Server** (JSON text frames)::

        {"type": "message", "content": "Hello!", "platform": "chat"}

    **Server -> Client** (JSON text frames)::

        {"type": "token", "content": "He"}       # repeated per token
        {"type": "done", "full_response": "..."}  # once at the end
        {"type": "error", "message": "..."}       # on failure

    Authentication
    --------------
    The client must pass ``?token=<session_token>`` as a query parameter.
    The token is validated against ``AuthService`` before the connection is
    accepted.  Invalid tokens cause an immediate close with code 4401.
    """

    # -- Session validation via query param ---------------------------------
    ticket = ws.query_params.get("ticket")
    token = ws.query_params.get("token")

    if not ticket and not token:
        await ws.close(code=4401, reason="Missing authentication token or ticket")
        return

    auth_service = getattr(ws.app.state, "auth_service", None)
    if auth_service is None:
        await ws.close(code=4500, reason="Auth service unavailable")
        return

    session = None
    if ticket:
        session = auth_service.validate_ws_ticket(ticket)
    elif token:
        session = auth_service.validate_session(token)

    if session is None:
        await ws.close(code=4401, reason="Invalid or expired session")
        return

    # -- Accept connection ---------------------------------------------------
    await ws.accept()
    logger.info("WebSocket chat connected: session=%s...", session.session_id[:8])

    # Resolve services from app state
    llm_service: LLMService = ws.app.state.llm_service
    db = ws.app.state.db
    conversation_repo = ConversationRepository(db)

    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > MAX_WS_MESSAGE_BYTES:
                await _send_error(ws, f"Message too large (max {MAX_WS_MESSAGE_BYTES} bytes)")
                continue
            try:
                data: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await _send_error(ws, "Invalid JSON")
                continue

            msg_type = data.get("type")
            if msg_type != "message":
                await _send_error(ws, f"Unknown message type: {msg_type}")
                continue

            content = data.get("content", "").strip()
            if not content:
                await _send_error(ws, "Empty message content")
                continue

            platform = data.get("platform", "chat")

            # Process the message
            await _handle_message(
                ws=ws,
                content=content,
                platform=platform,
                llm_service=llm_service,
                conversation_repo=conversation_repo,
            )

    except WebSocketDisconnect:
        logger.info("WebSocket chat disconnected: session=%s...", session.session_id[:8])
    except Exception as exc:
        logger.exception("WebSocket chat unexpected error: %s", exc)
        if ws.client_state == WebSocketState.CONNECTED:
            await _send_error(ws, "Internal server error")
            await ws.close(code=1011, reason="Internal error")


async def _handle_message(
    *,
    ws: WebSocket,
    content: str,
    platform: str,
    llm_service: LLMService,
    conversation_repo: ConversationRepository,
) -> None:
    """Save the user message, stream the LLM response, save the result."""

    # 1. Save user message
    await conversation_repo.add(
        ConversationCreate(role="user", content=content, platform=platform)
    )

    # 2. Load recent history
    recent = await conversation_repo.get_history(
        limit=_MAX_HISTORY_CONTEXT,
        platform_filter=platform,
    )
    messages: list[dict[str, str]] = []
    for conv in reversed(recent):
        messages.append({"role": conv.role, "content": conv.content})

    # 3. Stream LLM response
    full_response = ""
    try:
        stream: AsyncIterator[str] = await llm_service.chat(messages, stream=True)  # type: ignore[assignment]

        async for token in stream:
            full_response += token
            await ws.send_text(
                json.dumps({"type": "token", "content": token}, ensure_ascii=False)
            )

    except (LLMConnectionError, LLMGenerationError) as exc:
        logger.error("LLM error during streaming: %s", exc.message)
        await _send_error(ws, f"LLM error: {exc.message}")
        return
    except Exception as exc:
        logger.exception("Unexpected LLM streaming error: %s", exc)
        await _send_error(ws, "Failed to generate response")
        return

    # 4. Save assistant response
    if full_response:
        await conversation_repo.add(
            ConversationCreate(
                role="assistant",
                content=full_response,
                platform=platform,
            )
        )

    # 5. Send completion signal
    await ws.send_text(
        json.dumps(
            {"type": "done", "full_response": full_response},
            ensure_ascii=False,
        )
    )

    logger.info(
        "WebSocket chat response completed: platform=%s, length=%d",
        platform,
        len(full_response),
    )


async def _send_error(ws: WebSocket, message: str) -> None:
    """Send an error frame if the connection is still open."""
    if ws.client_state == WebSocketState.CONNECTED:
        await ws.send_text(
            json.dumps({"type": "error", "message": message}, ensure_ascii=False)
        )
