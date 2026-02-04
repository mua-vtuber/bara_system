from __future__ import annotations

import asyncio
import random
import socket
import time
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp

from app.core.config import Config
from app.core.constants import MAX_BACKOFF_SECONDS
from app.core.exceptions import (
    AuthenticationError,
    NetworkError,
    PlatformServerError,
    RateLimitError,
)
from app.core.logging import get_logger
from app.core.network import is_private_ip

logger = get_logger(__name__)

_DEFAULT_TIMEOUT_SECONDS: int = 30
_DEFAULT_MAX_RETRIES: int = 3
_USER_AGENT: str = "BaraSystem/1.0"


class HttpClient:
    """Async HTTP client wrapping :class:`aiohttp.ClientSession`.

    Features:
    - Automatic JSON response parsing
    - Exponential back-off retry with jitter
    - Proper error mapping (429, 401, 5xx, connection errors)
    - Configurable timeout and retry count
    """

    def __init__(
        self,
        config: Config,
        *,
        timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        self._config = config
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Create the underlying :class:`aiohttp.ClientSession`."""
        if self._session is not None and not self._session.closed:
            return

        timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
        }
        self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        logger.info("HttpClient session started (timeout=%ds)", self._timeout_seconds)

    async def close(self) -> None:
        """Close the underlying session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            # Allow the SSL transport to settle (aiohttp recommendation)
            await asyncio.sleep(0.25)
            logger.info("HttpClient session closed")
        self._session = None

    # ------------------------------------------------------------------
    # Public request helpers
    # ------------------------------------------------------------------

    async def get(self, url: str, **kwargs: Any) -> dict | str:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> dict | str:
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> dict | str:
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> dict | str:
        return await self.request("DELETE", url, **kwargs)

    # ------------------------------------------------------------------
    # Core request with retry
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        url: str,
        *,
        platform: str = "unknown",
        **kwargs: Any,
    ) -> dict | str:
        """Execute an HTTP request with exponential back-off retry.

        Parameters
        ----------
        method:
            HTTP method (GET, POST, PUT, DELETE).
        url:
            Full URL to call.
        platform:
            Platform name used in error context (default ``"unknown"``).
        **kwargs:
            Forwarded to :meth:`aiohttp.ClientSession.request` (e.g.
            ``json=``, ``params=``, ``headers=``).

        Raises
        ------
        RateLimitError
            On HTTP 429. Contains ``retry_after`` when the header exists.
        AuthenticationError
            On HTTP 401.
        PlatformServerError
            On HTTP 5xx after all retries exhausted.
        NetworkError
            On connection/timeout failures after all retries exhausted.
        """
        if self._session is None or self._session.closed:
            raise NetworkError(
                platform=platform,
                message="HttpClient session is not started. Call start() first.",
            )

        last_exception: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                return await self._do_request(method, url, platform, attempt, **kwargs)
            except RateLimitError:
                # Never retry 429 automatically; bubble up so rate limiter handles it
                raise
            except AuthenticationError:
                # Authentication won't fix itself with retries
                raise
            except (PlatformServerError, NetworkError) as exc:
                last_exception = exc
                if attempt < self._max_retries:
                    backoff = self._backoff_seconds(attempt)
                    logger.warning(
                        "%s %s attempt %d/%d failed (%s), retrying in %.1fs",
                        method,
                        url,
                        attempt,
                        self._max_retries,
                        exc.message,
                        backoff,
                    )
                    await asyncio.sleep(backoff)

        # All retries exhausted
        logger.error(
            "%s %s failed after %d attempts", method, url, self._max_retries
        )
        raise last_exception  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _do_request(
        self,
        method: str,
        url: str,
        platform: str,
        attempt: int,
        **kwargs: Any,
    ) -> dict | str:
        """Single request attempt with response classification."""
        if self._session is None:
            raise NetworkError(
                platform=platform,
                message="HttpClient session is not started. Call start() first.",
            )

        # SSRF protection: block requests to internal/private networks.
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        # Allow Ollama on localhost explicitly.
        _ALLOWED_INTERNAL = {"localhost:11434", "127.0.0.1:11434"}
        netloc = f"{hostname}:{parsed.port}" if parsed.port else hostname
        if netloc not in _ALLOWED_INTERNAL:
            try:
                resolved = socket.getaddrinfo(hostname, None)
                for _, _, _, _, addr in resolved:
                    if is_private_ip(addr[0]):
                        raise NetworkError(
                            platform=platform,
                            message=f"Request to internal address blocked: {hostname}",
                        )
            except socket.gaierror:
                pass  # DNS resolution failed — let the HTTP client handle it.

        try:
            async with self._session.request(method, url, **kwargs) as resp:
                status = resp.status
                logger.debug(
                    "%s %s -> %d (attempt %d)", method, url, status, attempt
                )

                # --- 429 Rate Limit ---
                if status == 429:
                    retry_after = self._parse_retry_after(resp)
                    raise RateLimitError(
                        platform=platform,
                        retry_after=retry_after,
                        message=f"Rate limited on {method} {url}",
                    )

                # --- 401 Unauthorized ---
                if status == 401:
                    raise AuthenticationError(
                        platform=platform,
                        status_code=status,
                        message=f"Authentication failed on {method} {url}",
                    )

                # --- 5xx Server Error ---
                if status >= 500:
                    body_preview = await self._safe_text(resp, max_len=200)
                    raise PlatformServerError(
                        platform=platform,
                        status_code=status,
                        message=f"Server error {status} on {method} {url}: {body_preview}",
                    )

                # --- Success (2xx) or other client errors ---
                return await self._parse_response(resp)

        except aiohttp.ClientError as exc:
            raise NetworkError(
                platform=platform,
                message=f"Connection error on {method} {url}: {exc}",
            ) from exc

    @staticmethod
    def _parse_retry_after(resp: aiohttp.ClientResponse) -> float | None:
        """Extract ``Retry-After`` header as seconds, if present."""
        raw = resp.headers.get("Retry-After")
        if raw is None:
            return None
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None

    @staticmethod
    async def _parse_response(resp: aiohttp.ClientResponse) -> dict | str:
        """Return JSON dict if content-type is JSON, else raw text."""
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return await resp.json()  # type: ignore[return-value]
        return await resp.text()

    @staticmethod
    async def _safe_text(
        resp: aiohttp.ClientResponse, *, max_len: int = 200
    ) -> str:
        text = await resp.text()
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text

    def _backoff_seconds(self, attempt: int) -> float:
        """Exponential back-off with jitter, capped at ``MAX_BACKOFF_SECONDS``."""
        base = min(2 ** attempt, MAX_BACKOFF_SECONDS)
        jitter = random.uniform(0, base * 0.5)  # noqa: S311
        return min(base + jitter, MAX_BACKOFF_SECONDS)
