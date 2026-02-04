from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from typing import Any, Awaitable, Callable, TypeVar

from app.core.logging import get_logger
from app.models.events import Event

logger = get_logger(__name__)

T = TypeVar("T", bound=Event)

Handler = Callable[[Any], Awaitable[None] | None]


class EventBus:
    """In-process publish/subscribe event bus.

    * Supports both async and sync handlers.
    * ``publish`` is non-blocking: handlers execute as background tasks.
    * A failing handler never prevents other handlers from running.
    """

    def __init__(self) -> None:
        self._subscribers: dict[type[Event], list[Handler]] = defaultdict(list)
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Subscribe / Unsubscribe
    # ------------------------------------------------------------------

    async def subscribe(
        self,
        event_type: type[T],
        handler: Callable[[T], Awaitable[None] | None],
    ) -> None:
        """Register *handler* for *event_type*."""
        async with self._lock:
            self._subscribers[event_type].append(handler)  # type: ignore[arg-type]
        logger.debug(
            "Subscribed handler %s to %s (total: %d)",
            getattr(handler, "__name__", repr(handler)),
            event_type.__name__,
            len(self._subscribers[event_type]),
        )

    async def unsubscribe(
        self,
        event_type: type[T],
        handler: Callable[[T], Awaitable[None] | None],
    ) -> None:
        """Remove *handler* from *event_type*.  No-op if not found."""
        async with self._lock:
            handlers = self._subscribers.get(event_type)
            if handlers is None:
                return
            try:
                handlers.remove(handler)  # type: ignore[arg-type]
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(self, event: Event) -> None:
        """Dispatch *event* to all registered handlers in the background.

        The caller is **not** blocked while handlers execute.  Each handler
        runs in its own ``asyncio.Task`` so a slow or failing handler does
        not affect others.
        """
        event_type = type(event)

        async with self._lock:
            handlers = list(self._subscribers.get(event_type, []))

        if not handlers:
            logger.debug("Published %s with 0 subscribers", event_type.__name__)
            return

        logger.debug(
            "Publishing %s to %d subscriber(s)",
            event_type.__name__,
            len(handlers),
        )

        for handler in handlers:
            asyncio.create_task(self._invoke_handler(handler, event))

    # ------------------------------------------------------------------
    # Introspection / Cleanup
    # ------------------------------------------------------------------

    def get_subscriber_count(self, event_type: type[Event]) -> int:
        """Return the number of handlers registered for *event_type*."""
        return len(self._subscribers.get(event_type, []))

    async def clear(self) -> None:
        """Remove **all** subscriptions."""
        async with self._lock:
            self._subscribers.clear()
        logger.info("EventBus cleared all subscriptions")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    async def _invoke_handler(handler: Handler, event: Event) -> None:
        """Call *handler* safely, catching and logging any exception."""
        try:
            result = handler(event)
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception(
                "Handler %s raised while processing %s",
                getattr(handler, "__name__", repr(handler)),
                type(event).__name__,
            )
