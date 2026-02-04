from __future__ import annotations

from fastapi import FastAPI

from app.api.middleware.auth import AuthMiddleware
from app.api.middleware.csrf import CSRFMiddleware
from app.api.middleware.ip_filter import IPFilterMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.middleware.request_log import RequestLoggingMiddleware
from app.api.middleware.security_headers import SecurityHeadersMiddleware


def register_middleware(app: FastAPI) -> None:
    """Register all middleware on *app* in the correct order.

    All middleware classes resolve their dependencies lazily from
    ``request.app.state`` at request time, so this function can be called
    during ``create_app`` before the lifespan context has run.

    Starlette processes middleware in **reverse** registration order (last
    added wraps outermost), so we register from innermost to outermost:

        CSRF -> Auth -> RateLimit -> IPFilter -> RequestLogging -> SecurityHeaders -> CORS

    CORS is already added in ``create_app``, so we skip it here.  The
    resulting onion is:

        CORS (outermost)
          -> SecurityHeaders
            -> RequestLogging
              -> IPFilter
                -> RateLimit
                  -> Auth
                    -> CSRF (innermost, validates after auth sets session)
    """
    # Innermost first
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(IPFilterMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
