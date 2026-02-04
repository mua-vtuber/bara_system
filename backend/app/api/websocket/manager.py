from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.constants import MAX_WS_CONNECTIONS_PER_USER
from app.core.logging import get_logger
from app.models.auth import Session
from app.services.auth import AuthService

logger = get_logger(__name__)


@dataclass
class WebSocketConnection:
    """Metadata for a single WebSocket connection."""

    websocket: WebSocket
    connection_id: str
    session: Optional[Session] = None
    connected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class WebSocketManager:
    """Manages active WebSocket connections with broadcast support.

    Thread-safety is ensured via an ``asyncio.Lock`` that protects the
    connections dict.  The lock is released **before** performing I/O
    (sending messages) to avoid holding it during slow network operations.
    """

    def __init__(self, auth_service: AuthService) -> None:
        self._auth_service = auth_service
        self._connections: dict[str, WebSocketConnection] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Connect / Disconnect
    # ------------------------------------------------------------------

    async def connect(
        self,
        websocket: WebSocket,
        session: Session | None = None,
    ) -> str:
        """Accept *websocket*, register, and return a unique connection id."""
        # Enforce per-user connection limit.
        if session:
            async with self._lock:
                user_count = sum(
                    1 for conn in self._connections.values()
                    if conn.session and conn.session.session_id == session.session_id
                )
            if user_count >= MAX_WS_CONNECTIONS_PER_USER:
                await websocket.close(code=4429, reason="Too many connections")
                return ""

        connection_id = uuid.uuid4().hex
        await websocket.accept()

        conn = WebSocketConnection(
            websocket=websocket,
            connection_id=connection_id,
            session=session,
        )

        async with self._lock:
            self._connections[connection_id] = conn

        logger.info(
            "WebSocket connected: id=%s, session=%s",
            connection_id[:8],
            session.session_id[:8] if session else "anonymous",
        )
        return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """Remove and close the connection identified by *connection_id*."""
        async with self._lock:
            conn = self._connections.pop(connection_id, None)

        if conn is None:
            return

        try:
            if conn.websocket.client_state == WebSocketState.CONNECTED:
                await conn.websocket.close()
        except Exception:
            pass  # already closed -- ignore

        logger.info("WebSocket disconnected: id=%s", connection_id[:8])

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Send a JSON message to **all** connected clients.

        Dead connections discovered during the broadcast are removed
        automatically.
        """
        payload = json.dumps(
            {"type": event_type, "data": data},
            ensure_ascii=False,
            default=str,
        )

        # Snapshot connections then release the lock before I/O.
        async with self._lock:
            snapshot = list(self._connections.items())

        dead_connections: list[str] = []

        for cid, conn in snapshot:
            try:
                if conn.websocket.client_state == WebSocketState.CONNECTED:
                    await conn.websocket.send_text(payload)
                else:
                    dead_connections.append(cid)
            except Exception:
                logger.warning("Send failed for connection %s, marking dead", cid[:8])
                dead_connections.append(cid)

        # Purge dead connections.
        if dead_connections:
            async with self._lock:
                for cid in dead_connections:
                    self._connections.pop(cid, None)
            logger.info("Removed %d dead connection(s)", len(dead_connections))

    async def send_to(
        self,
        connection_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Send a JSON message to a **single** connection."""
        async with self._lock:
            conn = self._connections.get(connection_id)

        if conn is None:
            return

        payload = json.dumps(
            {"type": event_type, "data": data},
            ensure_ascii=False,
            default=str,
        )

        try:
            if conn.websocket.client_state == WebSocketState.CONNECTED:
                await conn.websocket.send_text(payload)
        except Exception:
            logger.warning("send_to failed for %s, removing", connection_id[:8])
            async with self._lock:
                self._connections.pop(connection_id, None)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_connection_count(self) -> int:
        """Return the number of currently tracked connections."""
        return len(self._connections)
