"""CSRF protection middleware using HMAC-based double-submit tokens."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import get_logger

logger = get_logger(__name__)

_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})

_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/auth/login",
    "/api/auth/setup-password",
    "/api/auth/csrf-token",
    "/api/health",
    "/ws/",
)

# Token validity window (seconds).
_TOKEN_MAX_AGE: int = 3600  # 1 hour


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validate CSRF tokens on state-changing requests.

    Tokens are HMAC(csrf_secret, session_token || timestamp) so they can
    be validated without server-side storage.
    """

    async def dispatch(self, request: Request, call_next: Callable[..., Response]) -> Response:
        # Safe methods don't need CSRF.
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        path = request.url.path

        # Exempt paths.
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        config = getattr(request.app.state, "config", None)
        if config is None or not config.web_security.csrf_secret:
            return await call_next(request)

        # Require session for CSRF check.
        session = getattr(request.state, "session", None)
        if session is None:
            # No session = auth middleware will reject separately.
            return await call_next(request)

        csrf_token = request.headers.get("x-csrf-token", "")
        if not csrf_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing"},
            )

        if not self._validate_token(
            csrf_token,
            config.web_security.csrf_secret,
            session.session_id,
        ):
            logger.warning("CSRF token validation failed: path=%s", path)
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token invalid or expired"},
            )

        return await call_next(request)

    # ------------------------------------------------------------------
    # Token generation / validation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_token(csrf_secret: str, session_id: str) -> str:
        """Create a new CSRF token bound to the session."""
        timestamp = str(int(time.time()))
        payload = f"{session_id}:{timestamp}"
        sig = hmac.new(
            csrf_secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        return f"{timestamp}:{sig}"

    @staticmethod
    def _validate_token(token: str, csrf_secret: str, session_id: str) -> bool:
        parts = token.split(":", 1)
        if len(parts) != 2:
            return False
        timestamp_str, sig = parts
        try:
            timestamp = int(timestamp_str)
        except ValueError:
            return False

        # Check token age.
        if abs(time.time() - timestamp) > _TOKEN_MAX_AGE:
            return False

        # Recompute and compare.
        payload = f"{session_id}:{timestamp_str}"
        expected = hmac.new(
            csrf_secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(sig, expected)
