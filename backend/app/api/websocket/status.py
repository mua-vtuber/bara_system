from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.events import EventBus
from app.core.logging import get_logger
from app.models.events import (
    BotStatusChangedEvent,
    CommentPostedEvent,
    Event,
    HealthCheckEvent,
    MissionCompletedEvent,
    MissionCreatedEvent,
    MissionPostPublishedEvent,
    MissionResponseReceivedEvent,
    PlatformErrorEvent,
    PostCreatedEvent,
    TaskCompletedEvent,
    TaskQueuedEvent,
)
from app.api.websocket.manager import WebSocketManager

logger = get_logger(__name__)

# Maps event dataclass types to the wire ``type`` string sent to clients.
_EVENT_TYPE_MAP: dict[type[Event], str] = {
    BotStatusChangedEvent: "bot_status",
    PlatformErrorEvent: "platform_error",
    HealthCheckEvent: "health",
    TaskQueuedEvent: "task_queued",
    TaskCompletedEvent: "task_completed",
    CommentPostedEvent: "comment_posted",
    PostCreatedEvent: "post_created",
    MissionCreatedEvent: "mission_created",
    MissionPostPublishedEvent: "mission_posted",
    MissionResponseReceivedEvent: "mission_response",
    MissionCompletedEvent: "mission_complete",
}


def _event_to_payload(event: Event) -> dict[str, Any]:
    """Convert a frozen dataclass event into a JSON-safe dict."""
    d = asdict(event)
    # Convert datetime to ISO string for JSON serialisation.
    for key, value in d.items():
        if hasattr(value, "isoformat"):
            d[key] = value.isoformat()
    return d


async def websocket_status(ws: WebSocket) -> None:
    """``WS /ws/status`` -- real-time system status updates.

    Authentication
    --------------
    The client passes ``?token=<session_token>`` as a query parameter.

    Behaviour
    ---------
    1. On connect, the server pushes a full ``state_sync`` snapshot.
    2. The server then forwards selected ``EventBus`` events for the
       lifetime of the connection.
    3. When the client disconnects, all event subscriptions are cleaned up.
    """

    # -- Authentication -------------------------------------------------------
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

    # -- Resolve services from app.state --------------------------------------
    event_bus: EventBus = ws.app.state.event_bus
    ws_manager: WebSocketManager = ws.app.state.ws_manager

    # -- Register connection via manager --------------------------------------
    connection_id = await ws_manager.connect(ws, session=session)

    logger.info(
        "Status WS connected: connection=%s, session=%s",
        connection_id[:8],
        session.session_id[:8],
    )

    # -- Send initial state snapshot ------------------------------------------
    await _send_state_sync(ws)

    # -- Subscribe to relevant EventBus events --------------------------------
    # Build per-connection forwarding handlers so they can be cleanly removed.

    async def _make_forwarder(wire_type: str):
        """Return a handler that forwards an event to this specific WS."""

        async def _forward(event: Event) -> None:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(
                        json.dumps(
                            {"type": wire_type, "data": _event_to_payload(event)},
                            ensure_ascii=False,
                            default=str,
                        )
                    )
            except Exception:
                pass  # connection dropped; disconnect loop will clean up

        return _forward

    handlers: list[tuple[type[Event], Any]] = []
    for event_cls, wire_type in _EVENT_TYPE_MAP.items():
        handler = await _make_forwarder(wire_type)
        await event_bus.subscribe(event_cls, handler)
        handlers.append((event_cls, handler))

    # -- Keep-alive loop (also receives client pings/messages) ----------------
    try:
        while True:
            # We don't expect meaningful inbound messages, but we must
            # keep reading so the framework can detect disconnects.
            await ws.receive_text()
    except WebSocketDisconnect:
        logger.info("Status WS disconnected: connection=%s", connection_id[:8])
    except Exception as exc:
        logger.exception("Status WS unexpected error: %s", exc)
    finally:
        # -- Cleanup subscriptions and connection -----------------------------
        for event_cls, handler in handlers:
            await event_bus.unsubscribe(event_cls, handler)
        await ws_manager.disconnect(connection_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _send_state_sync(ws: WebSocket) -> None:
    """Push the initial ``state_sync`` payload to the client."""
    # At this stage a full bot-state service does not exist yet, so we send
    # a reasonable skeleton that the frontend can depend on.  The real values
    # will be filled in once the bot orchestrator is wired up.
    snapshot: dict[str, Any] = {
        "bot_status": "idle",
        "platforms": {},
        "uptime_seconds": 0,
    }

    await ws.send_text(
        json.dumps(
            {"type": "state_sync", "data": snapshot},
            ensure_ascii=False,
        )
    )
