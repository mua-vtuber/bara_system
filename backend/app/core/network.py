"""Shared network utilities for client IP resolution and SSRF protection."""

from __future__ import annotations

import ipaddress
from typing import Sequence

from starlette.requests import Request

from app.core.constants import TRUSTED_INTERNAL_NETWORKS
from app.core.logging import get_logger

logger = get_logger(__name__)

# Pre-parsed internal networks for SSRF blocking.
_INTERNAL_NETS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = tuple(
    ipaddress.ip_network(net, strict=False) for net in TRUSTED_INTERNAL_NETWORKS
)


def get_client_ip(
    request: Request,
    trusted_proxies: Sequence[str] = (),
) -> str:
    """Return the real client IP address.

    Only trusts ``X-Forwarded-For`` when the *immediate* connection
    (``request.client.host``) comes from a known trusted proxy.
    When untrusted, the header is ignored entirely.
    """
    direct_ip = request.client.host if request.client else "unknown"

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return direct_ip

    # Only honour the header when the direct peer is a trusted proxy.
    if direct_ip not in trusted_proxies:
        return direct_ip

    # Use the *rightmost* entry that is NOT a known proxy.
    # This is the safest strategy when proxies append to the header.
    parts = [p.strip() for p in forwarded.split(",")]
    for ip_str in reversed(parts):
        if ip_str not in trusted_proxies:
            return ip_str

    # Every entry is a trusted proxy – fall back to the direct peer.
    return direct_ip


def is_private_ip(ip_str: str) -> bool:
    """Return ``True`` if *ip_str* belongs to a private / loopback range."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in net for net in _INTERNAL_NETS)
