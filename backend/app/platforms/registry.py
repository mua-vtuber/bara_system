from __future__ import annotations

from typing import Any

from app.core.config import Config
from app.core.http_client import HttpClient
from app.core.logging import get_logger
from app.core.rate_limiter import PlatformRateLimiter
from app.core.security import SecurityFilter
from app.platforms.base import PlatformAdapter
from app.platforms.botmadang import BotmadangAdapter
from app.platforms.moltbook import MoltbookAdapter

logger = get_logger(__name__)

# Mapping from platform name to adapter class
_ADAPTER_CLASSES: dict[str, type[PlatformAdapter]] = {
    "botmadang": BotmadangAdapter,
    "moltbook": MoltbookAdapter,
}


class PlatformRegistry:
    """Factory and registry for platform adapters.

    Creates adapter instances for each enabled platform during
    :meth:`initialize` and provides lookup by name.
    """

    def __init__(
        self,
        config: Config,
        http_client: HttpClient,
        rate_limiters: dict[str, PlatformRateLimiter],
        security_filter: SecurityFilter,
    ) -> None:
        self._config = config
        self._http_client = http_client
        self._rate_limiters = rate_limiters
        self._security_filter = security_filter
        self._adapters: dict[str, PlatformAdapter] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Instantiate adapters for every enabled platform in config."""
        platform_enabled = {
            "botmadang": self._config.platforms.botmadang.enabled,
            "moltbook": self._config.platforms.moltbook.enabled,
        }

        for name, enabled in platform_enabled.items():
            if not enabled:
                logger.debug("Platform '%s' is disabled, skipping adapter creation", name)
                continue

            adapter_cls = _ADAPTER_CLASSES.get(name)
            if adapter_cls is None:
                logger.warning("No adapter class registered for platform '%s'", name)
                continue

            rate_limiter = self._rate_limiters.get(name)
            if rate_limiter is None:
                logger.warning("No rate limiter found for platform '%s', skipping", name)
                continue

            adapter = adapter_cls(
                config=self._config,
                http_client=self._http_client,
                rate_limiter=rate_limiter,
                security_filter=self._security_filter,
            )
            self._adapters[name] = adapter
            logger.info(
                "Platform adapter created: %s (authenticated=%s, capabilities=%s)",
                name,
                adapter.is_authenticated,
                sorted(c.value for c in adapter.get_capabilities()),
            )

        if not self._adapters:
            logger.warning("No platform adapters were created; check platform config")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_adapter(self, platform_name: str) -> PlatformAdapter:
        """Return the adapter for *platform_name*.

        Raises ``KeyError`` when the platform is not registered.
        """
        try:
            return self._adapters[platform_name]
        except KeyError:
            available = ", ".join(self._adapters.keys()) or "(none)"
            raise KeyError(
                f"Platform '{platform_name}' is not registered. "
                f"Available: {available}"
            )

    def get_enabled_platforms(self) -> list[PlatformAdapter]:
        """Return all registered (enabled) adapters."""
        return list(self._adapters.values())

    def get_status_summary(self) -> dict[str, Any]:
        """Return a status overview suitable for health checks and UI display."""
        summary: dict[str, Any] = {}
        for name, adapter in self._adapters.items():
            summary[name] = {
                "enabled": True,
                "authenticated": adapter.is_authenticated,
                "capabilities": sorted(c.value for c in adapter.get_capabilities()),
            }

        # Include disabled platforms so the UI knows they exist
        all_known = {"botmadang", "moltbook"}
        for name in all_known - set(self._adapters.keys()):
            summary[name] = {
                "enabled": False,
                "authenticated": False,
                "capabilities": [],
            }

        return summary
