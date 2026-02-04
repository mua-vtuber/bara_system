from __future__ import annotations

import ipaddress
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import get_logger
from app.core.network import get_client_ip

logger = get_logger(__name__)

# RFC-1918 private networks + loopback.
_LOCAL_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv6Network("::1/128"),
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
)


class IPFilterMiddleware(BaseHTTPMiddleware):
    """Restrict access based on client IP address.

    Reads ``config.web_security`` lazily from ``request.app.state.config``
    so the middleware can be registered before lifespan runs.

    Behaviour:

    * If ``allowed_ips`` is empty **and** ``allow_all_local`` is ``False``,
      all IPs are permitted (default open-access for development).
    * If ``allow_all_local`` is ``True``, loopback and private-network
      addresses are always allowed regardless of the allowlist.
    * Otherwise only explicitly listed IPs pass through.
    """

    async def dispatch(self, request: Request, call_next: Callable[..., Response]) -> Response:
        config = getattr(request.app.state, "config", None)
        if config is None:
            return await call_next(request)

        allowed_ips = config.web_security.allowed_ips
        allow_local = config.web_security.allow_all_local

        # No restrictions configured -> allow everything.
        if not allowed_ips and not allow_local:
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        # allow_all_local: accept any private / loopback address.
        if allow_local and self._is_local(client_ip):
            return await call_next(request)

        # Explicit allowlist check.
        if allowed_ips and client_ip in allowed_ips:
            return await call_next(request)

        # If allowed_ips is empty but allow_local is True, non-local IPs are denied.
        if not allowed_ips and allow_local:
            logger.warning("IP denied (non-local): %s", client_ip)
            return self._forbidden(client_ip)

        logger.warning("IP denied (not in allowlist): %s", client_ip)
        return self._forbidden(client_ip)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Return the client IP using the shared network utility."""
        config = getattr(request.app.state, "config", None)
        trusted = config.web_security.trusted_proxies if config else ()
        return get_client_ip(request, trusted_proxies=trusted)

    @staticmethod
    def _is_local(ip_str: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        return any(addr in net for net in _LOCAL_NETWORKS)

    @staticmethod
    def _forbidden(ip: str) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"detail": f"Access denied for IP: {ip}"},
        )
