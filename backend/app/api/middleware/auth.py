from __future__ import annotations

from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import get_logger

logger = get_logger(__name__)

# Paths that bypass authentication entirely.
_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/api/auth/login",
    "/api/auth/setup-password",
    "/api/auth/status",
    "/api/auth/csrf-token",
    "/ws/",
)

_STATIC_PREFIXES: tuple[str, ...] = (
    "/static",
    "/assets",
    "/favicon.ico",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """Validates session tokens from cookies or Authorization header.

    Exempt paths (health, login, setup, docs, static assets) are passed
    through.  For all other routes the middleware looks for a session token in:

    1. Cookie named ``session_token``
    2. ``Authorization: Bearer <token>`` header

    A valid session is stored on ``request.state.session``.  Invalid or
    missing tokens receive a ``401`` JSON response.

    The ``AuthService`` is resolved lazily from ``request.app.state`` so that
    the middleware can be registered at app-creation time before the lifespan
    context has initialised the service.
    """

    async def dispatch(self, request: Request, call_next: Callable[..., Response]) -> Response:
        path = request.url.path

        # Allow exempt paths
        if self._is_exempt(path):
            return await call_next(request)

        # Lazy import of auth_service from app state
        auth_service = getattr(request.app.state, "auth_service", None)
        if auth_service is None:
            # Service not yet initialised (should not happen in normal flow)
            return JSONResponse(
                status_code=503,
                content={"detail": "Service initializing"},
            )

        # Extract token
        token = self._extract_token(request)
        if token is None:
            return self._unauthorized("Missing session token")

        session = auth_service.validate_session(token)
        if session is None:
            return self._unauthorized("Invalid or expired session")

        request.state.session = session
        return await call_next(request)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_exempt(path: str) -> bool:
        if path.startswith(_STATIC_PREFIXES):
            return True
        for prefix in _EXEMPT_PREFIXES:
            if path == prefix or path.startswith(prefix + "/"):
                return True
        return False

    @staticmethod
    def _extract_token(request: Request) -> str | None:
        # 1. Cookie
        token = request.cookies.get("session_token")
        if token:
            return token

        # 2. Authorization header
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()

        return None

    @staticmethod
    def _unauthorized(detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": detail},
        )
