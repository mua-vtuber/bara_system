"""IP-based sliding-window rate limiting middleware."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.constants import (
    DEFAULT_API_RATE_LIMIT,
    DEFAULT_LOGIN_RATE_LIMIT,
    RATE_LIMIT_WINDOW_SECONDS,
)
from app.core.logging import get_logger
from app.core.network import get_client_ip

logger = get_logger(__name__)

# path prefix -> max requests per window
_ROUTE_LIMITS: dict[str, int] = {
    "/api/auth/login": DEFAULT_LOGIN_RATE_LIMIT,
    "/api/backup": DEFAULT_LOGIN_RATE_LIMIT,
}

_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/static",
    "/assets",
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-IP request rate limits using a sliding window."""

    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        # ip -> list of request timestamps
        self._windows: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable[..., Response]) -> Response:
        path = request.url.path

        # Skip exempt paths.
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        config = getattr(request.app.state, "config", None)
        trusted = config.web_security.trusted_proxies if config else ()
        client_ip = get_client_ip(request, trusted_proxies=trusted)

        # Determine limit for this path.
        limit = DEFAULT_API_RATE_LIMIT
        for prefix, route_limit in _ROUTE_LIMITS.items():
            if path.startswith(prefix):
                limit = route_limit
                break

        now = time.monotonic()
        window = self._windows[client_ip]

        # Prune entries outside the window.
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        self._windows[client_ip] = window = [t for t in window if t > cutoff]

        if len(window) >= limit:
            retry_after = int(RATE_LIMIT_WINDOW_SECONDS - (now - window[0])) + 1
            logger.warning(
                "Rate limit exceeded: ip=%s path=%s (%d/%d)",
                client_ip, path, len(window), limit,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)

        # Periodic cleanup: cap dictionary size to prevent memory growth.
        if len(self._windows) > 10_000:
            oldest_ips = sorted(
                self._windows, key=lambda ip: self._windows[ip][-1] if self._windows[ip] else 0
            )[:5000]
            for ip in oldest_ips:
                del self._windows[ip]

        return await call_next(request)
