from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import date
from typing import Any

from app.core.config import Config
from app.core.logging import get_logger
from app.models.platform import AcquireResult, RateLimitConfig

logger = get_logger(__name__)


class PlatformRateLimiter:
    """Per-platform rate limiter using asyncio locks and sliding windows.

    All timing uses :func:`time.monotonic` to avoid wall-clock drift.
    The :meth:`acquire` method is atomic: it checks limits **and** updates
    counters inside a single lock acquisition.
    """

    def __init__(self, platform_name: str, config: RateLimitConfig) -> None:
        self._platform = platform_name
        self._config = config
        self._lock = asyncio.Lock()

        # Cooldown tracking (monotonic timestamps)
        self._last_post_time: float = 0.0
        self._last_comment_time: float = 0.0

        # Sliding window for API calls (monotonic timestamps)
        self._api_calls_window: deque[float] = deque()

        # Daily comment counter
        self._daily_comment_count: int = 0
        self._daily_reset_date: date = date.today()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def acquire(self, action_type: str) -> AcquireResult:
        """Atomically check if *action_type* is allowed and reserve the slot.

        Returns an :class:`AcquireResult` indicating whether the action is
        ``allowed``.  When not allowed, ``wait_seconds`` hints how long the
        caller should wait before retrying.
        """
        async with self._lock:
            self._check_daily_reset()
            now = time.monotonic()

            if action_type == "post":
                return self._acquire_post(now)
            if action_type == "comment":
                return self._acquire_comment(now)
            if action_type == "api_call":
                return self._acquire_api_call(now)
            # For other types (upvote, etc.) only enforce API-call window
            return self._acquire_api_call(now)

    async def wait_and_acquire(self, action_type: str) -> None:
        """Block until *action_type* is permitted, then reserve the slot."""
        while True:
            result = await self.acquire(action_type)
            if result.allowed:
                return
            sleep_time = max(result.wait_seconds, 0.1)
            logger.debug(
                "[%s] %s throttled, waiting %.1fs",
                self._platform,
                action_type,
                sleep_time,
            )
            await asyncio.sleep(sleep_time)

    def get_status(self) -> dict[str, Any]:
        """Return a snapshot of the current limiter state (debug / UI)."""
        now = time.monotonic()
        cutoff = now - 60.0
        active_calls = sum(1 for t in self._api_calls_window if t > cutoff)

        return {
            "platform": self._platform,
            "post_cooldown_remaining": max(
                0.0,
                self._config.post_cooldown_seconds - (now - self._last_post_time),
            ),
            "comment_cooldown_remaining": max(
                0.0,
                self._config.comment_cooldown_seconds - (now - self._last_comment_time),
            ),
            "api_calls_last_minute": active_calls,
            "api_calls_limit": self._config.api_calls_per_minute,
            "daily_comments_used": self._daily_comment_count,
            "daily_comments_limit": self._config.comments_per_day,
        }

    # ------------------------------------------------------------------
    # Internal acquire helpers (called under lock)
    # ------------------------------------------------------------------

    def _acquire_post(self, now: float) -> AcquireResult:
        elapsed = now - self._last_post_time
        remaining = self._config.post_cooldown_seconds - elapsed
        if remaining > 0:
            return AcquireResult(allowed=False, wait_seconds=remaining)

        # Also enforce API call window
        api_result = self._acquire_api_call(now)
        if not api_result.allowed:
            return api_result

        self._last_post_time = now
        return AcquireResult(allowed=True)

    def _acquire_comment(self, now: float) -> AcquireResult:
        # Daily limit check
        if self._daily_comment_count >= self._config.comments_per_day:
            # Estimate seconds until midnight (rough, for wait hint)
            return AcquireResult(allowed=False, wait_seconds=3600.0)

        # Cooldown check
        elapsed = now - self._last_comment_time
        remaining = self._config.comment_cooldown_seconds - elapsed
        if remaining > 0:
            return AcquireResult(allowed=False, wait_seconds=remaining)

        # API call window
        api_result = self._acquire_api_call(now)
        if not api_result.allowed:
            return api_result

        self._last_comment_time = now
        self._daily_comment_count += 1
        return AcquireResult(allowed=True)

    def _acquire_api_call(self, now: float) -> AcquireResult:
        # Purge entries older than 60 seconds
        cutoff = now - 60.0
        while self._api_calls_window and self._api_calls_window[0] <= cutoff:
            self._api_calls_window.popleft()

        if len(self._api_calls_window) >= self._config.api_calls_per_minute:
            oldest = self._api_calls_window[0]
            wait = 60.0 - (now - oldest)
            return AcquireResult(allowed=False, wait_seconds=max(wait, 0.1))

        self._api_calls_window.append(now)
        return AcquireResult(allowed=True)

    # ------------------------------------------------------------------
    # Daily reset
    # ------------------------------------------------------------------

    def _check_daily_reset(self) -> None:
        today = date.today()
        if today != self._daily_reset_date:
            logger.info(
                "[%s] Daily counter reset (was %d comments)",
                self._platform,
                self._daily_comment_count,
            )
            self._daily_comment_count = 0
            self._daily_reset_date = today


# ======================================================================
# Factory
# ======================================================================


class RateLimiterFactory:
    """Creates :class:`PlatformRateLimiter` instances for every known platform."""

    # Default rate-limit profiles per platform
    _PROFILES: dict[str, RateLimitConfig] = {
        "botmadang": RateLimitConfig(
            post_cooldown_seconds=180,
            comment_cooldown_seconds=10,
            api_calls_per_minute=100,
            comments_per_day=100,
        ),
        "moltbook": RateLimitConfig(
            post_cooldown_seconds=1800,
            comment_cooldown_seconds=20,
            api_calls_per_minute=100,
            comments_per_day=50,
        ),
    }

    @classmethod
    def create_all(cls, config: Config) -> dict[str, PlatformRateLimiter]:
        """Return a mapping of ``platform_name -> PlatformRateLimiter``.

        Uses the hard-coded profiles above.  Only creates limiters for
        platforms that are enabled in *config*.
        """
        limiters: dict[str, PlatformRateLimiter] = {}

        platform_enabled = {
            "botmadang": config.platforms.botmadang.enabled,
            "moltbook": config.platforms.moltbook.enabled,
        }

        for name, profile in cls._PROFILES.items():
            if platform_enabled.get(name, False):
                limiters[name] = PlatformRateLimiter(name, profile)
                logger.info(
                    "Rate limiter created for %s (post=%ds, comment=%ds, api=%d/min, daily=%d)",
                    name,
                    profile.post_cooldown_seconds,
                    profile.comment_cooldown_seconds,
                    profile.api_calls_per_minute,
                    profile.comments_per_day,
                )

        # If nothing enabled, create all with defaults so callers always
        # have a limiter available during development / testing.
        if not limiters:
            for name, profile in cls._PROFILES.items():
                limiters[name] = PlatformRateLimiter(name, profile)
            logger.warning(
                "No platforms enabled; created rate limiters for all platforms with defaults"
            )

        return limiters
