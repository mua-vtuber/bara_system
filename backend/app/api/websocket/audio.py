"""WebSocket endpoint for real-time audio streaming and voice commands."""

from __future__ import annotations

import json

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.constants import MAX_WS_AUDIO_CHUNK_BYTES
from app.core.logging import get_logger

logger = get_logger(__name__)


async def websocket_audio(ws: WebSocket) -> None:
    """WebSocket endpoint for audio streaming and voice commands.

    Protocol
    --------
    **Client -> Server**:
    - Binary frames: Raw PCM audio data (16kHz, 16-bit, mono)
    - JSON text frames: Control messages
        - ``{"type": "start"}`` - Start listening session
        - ``{"type": "stop"}`` - Stop and transcribe collected audio
        - ``{"type": "ping"}`` - Keep-alive

    **Server -> Client** (JSON text frames):
    - ``{"type": "wake_word_detected"}`` - Wake word detected, now collecting audio
    - ``{"type": "transcript", "text": "..."}`` - Transcription result
    - ``{"type": "status", "listening": bool}`` - Current listening state
    - ``{"type": "error", "message": "..."}`` - Error occurred

    Authentication
    --------------
    The client must pass ``?token=<session_token>`` as a query parameter.
    Invalid tokens cause an immediate close with code 4401.

    Voice must be enabled in config, otherwise connection is closed.
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

    # -- Check if voice service is available and enabled ---------------------
    voice_service = getattr(ws.app.state, "voice_service", None)
    if voice_service is None or not voice_service.is_enabled:
        await ws.close(code=4503, reason="Voice service is not available or disabled")
        return

    # -- Accept connection ---------------------------------------------------
    await ws.accept()
    logger.info("WebSocket audio connected: session=%s...", session.session_id[:8])

    try:
        # Send initial status
        await _send_json(
            ws,
            {
                "type": "status",
                "listening": voice_service.is_listening,
            },
        )

        while True:
            # Receive message (binary or text)
            message = await ws.receive()

            # Handle binary audio data
            if "bytes" in message:
                audio_chunk = message["bytes"]
                if len(audio_chunk) > MAX_WS_AUDIO_CHUNK_BYTES:
                    await ws.send_json({"type": "error", "message": f"Audio chunk too large (max {MAX_WS_AUDIO_CHUNK_BYTES} bytes)"})
                    continue
                result = await voice_service.process_audio(audio_chunk)

                # If we got a transcription result, send it
                if result is not None:
                    await _send_json(
                        ws,
                        {
                            "type": "transcript",
                            "text": result,
                        },
                    )
                    # Send updated status
                    await _send_json(
                        ws,
                        {
                            "type": "status",
                            "listening": voice_service.is_listening,
                        },
                    )

                # If wake word was detected, notify client
                if voice_service.is_listening and result is None:
                    await _send_json(
                        ws,
                        {
                            "type": "wake_word_detected",
                        },
                    )

            # Handle text control messages
            elif "text" in message:
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type")

                    if msg_type == "stop":
                        # Explicitly finalize transcription
                        result = await voice_service.finalize_listening()
                        if result is not None:
                            await _send_json(
                                ws,
                                {
                                    "type": "transcript",
                                    "text": result,
                                },
                            )
                        await _send_json(
                            ws,
                            {
                                "type": "status",
                                "listening": voice_service.is_listening,
                            },
                        )

                    elif msg_type == "status":
                        # Send current status
                        await _send_json(
                            ws,
                            {
                                "type": "status",
                                "listening": voice_service.is_listening,
                            },
                        )

                    elif msg_type == "ping":
                        # Keep-alive response
                        await _send_json(ws, {"type": "pong"})

                    else:
                        await _send_error(ws, f"Unknown message type: {msg_type}")

                except json.JSONDecodeError:
                    await _send_error(ws, "Invalid JSON control message")

    except WebSocketDisconnect:
        logger.info("WebSocket audio disconnected: session=%s...", session.session_id[:8])
    except Exception as exc:
        logger.exception("WebSocket audio unexpected error: %s", exc)
        if ws.client_state == WebSocketState.CONNECTED:
            await _send_error(ws, "Internal server error")
            await ws.close(code=1011, reason="Internal error")


async def _send_json(ws: WebSocket, data: dict) -> None:
    """Send JSON message if connection is still open."""
    if ws.client_state == WebSocketState.CONNECTED:
        await ws.send_text(json.dumps(data, ensure_ascii=False))


async def _send_error(ws: WebSocket, message: str) -> None:
    """Send an error frame if the connection is still open."""
    if ws.client_state == WebSocketState.CONNECTED:
        await ws.send_text(
            json.dumps({"type": "error", "message": message}, ensure_ascii=False)
        )
