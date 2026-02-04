from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from app.core.constants import PlatformCapability

if TYPE_CHECKING:
    from app.core.config import Config
    from app.core.http_client import HttpClient
    from app.core.rate_limiter import PlatformRateLimiter
    from app.core.security import SecurityFilter
    from app.models.platform import (
        PlatformComment,
        PlatformCommunity,
        PlatformCommentResult,
        PlatformNotification,
        PlatformPost,
        PlatformPostResult,
        RateLimitConfig,
        RegistrationResult,
    )


class PlatformAdapter(ABC):
    """Abstract base class for all platform integrations.

    Every platform adapter implements this interface.  The rest of the
    system interacts with platforms exclusively through this ABC.

    Constructor dependencies are injected via the ``__init__`` signature
    so that each adapter can share the application-wide ``HttpClient``,
    ``PlatformRateLimiter`` and ``SecurityFilter``.
    """

    def __init__(
        self,
        config: Config,
        http_client: HttpClient,
        rate_limiter: PlatformRateLimiter,
        security_filter: SecurityFilter,
    ) -> None:
        self._config = config
        self._http_client = http_client
        self._rate_limiter = rate_limiter
        self._security_filter = security_filter

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Unique identifier: ``'botmadang'``, ``'moltbook'``."""

    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        """Whether the adapter holds valid credentials."""

    @abstractmethod
    def get_capabilities(self) -> set[PlatformCapability]:
        """Return the set of optional features this platform supports.

        Callers check capabilities before invoking platform-specific
        methods (``follow``, ``register_agent``, etc.).
        """

    # --- AUTH ---

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Test whether the current API key is valid."""

    # --- READ OPERATIONS ---

    @abstractmethod
    async def get_posts(
        self,
        sort: str = "new",
        limit: int = 25,
        community: Optional[str] = None,
    ) -> list[PlatformPost]:
        """Fetch a list of posts.  Returns standardised ``PlatformPost`` instances."""

    @abstractmethod
    async def get_post_detail(self, post_id: str) -> PlatformPost:
        """Fetch a single post with full content."""

    @abstractmethod
    async def get_comments(self, post_id: str) -> list[PlatformComment]:
        """Fetch comments on a post."""

    @abstractmethod
    async def get_communities(self) -> list[PlatformCommunity]:
        """Fetch available communities (submadangs / submolts)."""

    @abstractmethod
    async def get_notifications(
        self,
        since: Optional[datetime] = None,
        unread_only: bool = True,
    ) -> list[PlatformNotification]:
        """Fetch notifications.

        Platforms that do not support notifications return an empty list.
        Callers should check ``get_capabilities()`` first.
        """

    async def search(
        self,
        query: str,
        semantic: bool = False,
        limit: int = 25,
    ) -> list[PlatformPost]:
        """Search posts.  ``semantic=True`` uses semantic search when available.

        The default implementation falls back to keyword filtering on the
        result of :meth:`get_posts`.
        """
        if semantic and PlatformCapability.SEMANTIC_SEARCH not in self.get_capabilities():
            semantic = False

        posts = await self.get_posts(limit=limit)
        if not semantic:
            query_lower = query.lower()
            return [
                p
                for p in posts
                if query_lower in ((p.title or "") + (p.content or "")).lower()
            ]
        raise NotImplementedError("Subclass must implement semantic search")

    # --- WRITE OPERATIONS ---

    @abstractmethod
    async def create_post(
        self,
        title: str,
        content: str,
        community: str,
    ) -> PlatformPostResult:
        """Create a new post.  Returns a result containing the platform post ID."""

    @abstractmethod
    async def create_comment(
        self,
        post_id: str,
        content: str,
        parent_comment_id: Optional[str] = None,
    ) -> PlatformCommentResult:
        """Create a comment on a post.  Use ``parent_comment_id`` for nested replies."""

    @abstractmethod
    async def upvote(self, post_id: str) -> bool:
        """Upvote a post.  Returns success flag."""

    async def downvote(self, post_id: str) -> bool:
        """Downvote a post.  Raises by default -- override if supported."""
        raise NotImplementedError(f"{self.platform_name} does not support downvote")

    @abstractmethod
    async def mark_notifications_read(
        self,
        notification_ids: list[str] | str,
    ) -> bool:
        """Mark notifications as read.  Accepts ``'all'`` or a list of IDs."""

    # --- PLATFORM-SPECIFIC (optional) ---

    async def follow(self, agent_id: str) -> bool:
        """Follow an agent.  Moltbook only."""
        raise NotImplementedError(f"{self.platform_name} does not support follow")

    async def unfollow(self, agent_id: str) -> bool:
        """Unfollow an agent.  Moltbook only."""
        raise NotImplementedError(f"{self.platform_name} does not support unfollow")

    async def register_agent(
        self, name: str, description: str
    ) -> RegistrationResult:
        """Register a new agent.  Botmadang only."""
        raise NotImplementedError(f"{self.platform_name} does not support registration")

    # --- META ---

    @abstractmethod
    def get_rate_limit_config(self) -> RateLimitConfig:
        """Return the rate-limit configuration for this platform."""
