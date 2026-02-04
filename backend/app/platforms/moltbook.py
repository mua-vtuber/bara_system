from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

from app.core.config import Config
from app.core.constants import PlatformCapability
from app.core.http_client import HttpClient
from app.core.logging import get_logger
from app.core.rate_limiter import PlatformRateLimiter
from app.core.security import SecurityFilter
from app.models.platform import (
    PlatformComment,
    PlatformCommentResult,
    PlatformCommunity,
    PlatformNotification,
    PlatformPost,
    PlatformPostResult,
    RateLimitConfig,
    RegistrationResult,
)
from app.platforms.base import PlatformAdapter

logger = get_logger(__name__)

_ALLOWED_DOMAIN = "https://www.moltbook.com"


def _parse_datetime(raw: Any) -> Optional[datetime]:
    """Safely parse an ISO-8601 datetime string, returning *None* on failure."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class MoltbookAdapter(PlatformAdapter):
    """Platform adapter for Moltbook (https://www.moltbook.com/api/v1).

    Capabilities: SEMANTIC_SEARCH, FOLLOW, NESTED_COMMENTS.
    Does NOT support: NOTIFICATIONS, AGENT_REGISTRATION, DOWNVOTE.

    IMPORTANT:
    - API key must start with ``moltbook_`` prefix.
    - Requests must only go to ``www.moltbook.com`` (never without ``www``).
    """

    _CAPABILITIES: set[PlatformCapability] = {
        PlatformCapability.SEMANTIC_SEARCH,
        PlatformCapability.FOLLOW,
        PlatformCapability.NESTED_COMMENTS,
    }

    _RATE_LIMIT = RateLimitConfig(
        post_cooldown_seconds=1800,
        comment_cooldown_seconds=20,
        api_calls_per_minute=100,
        comments_per_day=50,
    )

    def __init__(
        self,
        config: Config,
        http_client: HttpClient,
        rate_limiter: PlatformRateLimiter,
        security_filter: SecurityFilter,
    ) -> None:
        super().__init__(config, http_client, rate_limiter, security_filter)
        self._base_url: str = config.platforms.moltbook.base_url.rstrip("/")
        self._api_key: str = os.environ.get("MOLTBOOK_API_KEY", config.env.moltbook_api_key)

        # Validate base_url starts with the allowed domain
        if not self._base_url.startswith(_ALLOWED_DOMAIN):
            logger.error(
                "Moltbook base_url '%s' does not start with %s -- API key will NOT be sent",
                self._base_url,
                _ALLOWED_DOMAIN,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_safe_url(self, url: str) -> bool:
        """Verify the URL points to the expected Moltbook domain."""
        try:
            parsed = urlparse(url)
            return (
                parsed.scheme == "https"
                and parsed.hostname == "www.moltbook.com"
            )
        except Exception:
            return False

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        url = self._url(path)
        if not self._is_safe_url(url):
            raise ValueError(f"Refusing to send API key to non-Moltbook domain: {url}")
        return await self._http_client.get(
            url,
            headers=self._auth_headers(),
            params=params,
            platform="moltbook",
        )

    async def _post(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        url = self._url(path)
        if not self._is_safe_url(url):
            raise ValueError(f"Refusing to send API key to non-Moltbook domain: {url}")
        return await self._http_client.post(
            url,
            headers=self._auth_headers(),
            json=json,
            platform="moltbook",
        )

    async def _delete(self, path: str) -> Any:
        url = self._url(path)
        if not self._is_safe_url(url):
            raise ValueError(f"Refusing to send API key to non-Moltbook domain: {url}")
        return await self._http_client.delete(
            url,
            headers=self._auth_headers(),
            platform="moltbook",
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def platform_name(self) -> str:
        return "moltbook"

    @property
    def is_authenticated(self) -> bool:
        return bool(self._api_key) and self._api_key.startswith("moltbook_")

    def get_capabilities(self) -> set[PlatformCapability]:
        return self._CAPABILITIES

    # ------------------------------------------------------------------
    # AUTH
    # ------------------------------------------------------------------

    async def validate_credentials(self) -> bool:
        if not self.is_authenticated:
            return False
        try:
            resp = await self._get("/agents/me")
            return isinstance(resp, dict) and resp.get("success", True)
        except Exception:
            logger.warning("Moltbook credential validation failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    async def get_posts(
        self,
        sort: str = "new",
        limit: int = 25,
        community: Optional[str] = None,
    ) -> list[PlatformPost]:
        params: dict[str, Any] = {"sort": sort, "limit": limit}
        if community:
            params["submolt"] = community
        resp = await self._get("/posts", params=params)
        items: list[dict[str, Any]]
        if isinstance(resp, list):
            items = resp
        elif isinstance(resp, dict):
            items = resp.get("posts", resp.get("data", []))
        else:
            items = []
        return [self._map_post(p) for p in items]

    async def get_post_detail(self, post_id: str) -> PlatformPost:
        resp = await self._get(f"/posts/{post_id}")
        data: dict[str, Any]
        if isinstance(resp, dict):
            data = resp.get("post", resp.get("data", resp))
        else:
            data = {}
        return self._map_post(data)

    async def get_comments(self, post_id: str) -> list[PlatformComment]:
        resp = await self._get(f"/posts/{post_id}/comments")
        items: list[dict[str, Any]]
        if isinstance(resp, list):
            items = resp
        elif isinstance(resp, dict):
            items = resp.get("comments", resp.get("data", []))
        else:
            items = []
        return [self._map_comment(c, post_id) for c in items]

    async def get_communities(self) -> list[PlatformCommunity]:
        resp = await self._get("/submolts")
        items: list[dict[str, Any]]
        if isinstance(resp, list):
            items = resp
        elif isinstance(resp, dict):
            items = resp.get("submolts", resp.get("data", []))
        else:
            items = []
        return [self._map_community(c) for c in items]

    async def get_notifications(
        self,
        since: Optional[datetime] = None,
        unread_only: bool = True,
    ) -> list[PlatformNotification]:
        # Moltbook does not expose a dedicated notifications endpoint
        return []

    async def search(
        self,
        query: str,
        semantic: bool = False,
        limit: int = 25,
    ) -> list[PlatformPost]:
        """Moltbook supports semantic search natively via ``GET /search``."""
        if not semantic:
            return await super().search(query, semantic=False, limit=limit)

        params: dict[str, Any] = {"q": query, "limit": limit, "type": "posts"}
        resp = await self._get("/search", params=params)
        items: list[dict[str, Any]]
        if isinstance(resp, dict):
            items = resp.get("results", resp.get("data", []))
        elif isinstance(resp, list):
            items = resp
        else:
            items = []
        return [self._map_search_result(r) for r in items]

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    async def create_post(
        self,
        title: str,
        content: str,
        community: str,
    ) -> PlatformPostResult:
        # Apply security filter to outgoing content
        filter_result = self._security_filter.filter_content(content)
        if not filter_result.passed:
            return PlatformPostResult(
                success=False,
                error=f"Security filter blocked: {filter_result.reason}",
            )
        filter_title = self._security_filter.filter_content(title)
        if not filter_title.passed:
            return PlatformPostResult(
                success=False,
                error=f"Security filter blocked title: {filter_title.reason}",
            )

        resp = await self._post(
            "/posts",
            json={"submolt": community, "title": title, "content": content},
        )
        if isinstance(resp, dict):
            data = resp.get("post", resp.get("data", resp))
            return PlatformPostResult(
                success=resp.get("success", True),
                post_id=str(data.get("id", data.get("post_id", ""))),
                url=data.get("url"),
            )
        return PlatformPostResult(success=False, error="Unexpected response format")

    async def create_comment(
        self,
        post_id: str,
        content: str,
        parent_comment_id: Optional[str] = None,
    ) -> PlatformCommentResult:
        filter_result = self._security_filter.filter_content(content)
        if not filter_result.passed:
            return PlatformCommentResult(
                success=False,
                error=f"Security filter blocked: {filter_result.reason}",
            )

        payload: dict[str, Any] = {"content": content}
        if parent_comment_id:
            payload["parent_id"] = parent_comment_id

        resp = await self._post(f"/posts/{post_id}/comments", json=payload)
        if isinstance(resp, dict):
            data = resp.get("comment", resp.get("data", resp))
            return PlatformCommentResult(
                success=resp.get("success", True),
                comment_id=str(data.get("id", data.get("comment_id", ""))),
            )
        return PlatformCommentResult(success=False, error="Unexpected response format")

    async def upvote(self, post_id: str) -> bool:
        try:
            resp = await self._post(f"/posts/{post_id}/upvote")
            if isinstance(resp, dict):
                return resp.get("success", True)
            return True
        except Exception:
            logger.warning("Moltbook upvote failed for post %s", post_id, exc_info=True)
            return False

    async def downvote(self, post_id: str) -> bool:
        try:
            resp = await self._post(f"/posts/{post_id}/downvote")
            if isinstance(resp, dict):
                return resp.get("success", True)
            return True
        except Exception:
            logger.warning("Moltbook downvote failed for post %s", post_id, exc_info=True)
            return False

    async def mark_notifications_read(
        self,
        notification_ids: list[str] | str,
    ) -> bool:
        # Moltbook does not expose a notifications-read endpoint
        return True

    # ------------------------------------------------------------------
    # PLATFORM-SPECIFIC
    # ------------------------------------------------------------------

    async def follow(self, agent_id: str) -> bool:
        """Follow a molty by name."""
        try:
            resp = await self._post(f"/agents/{agent_id}/follow")
            if isinstance(resp, dict):
                return resp.get("success", True)
            return True
        except Exception:
            logger.warning("Moltbook follow failed for %s", agent_id, exc_info=True)
            return False

    async def unfollow(self, agent_id: str) -> bool:
        """Unfollow a molty by name."""
        try:
            resp = await self._delete(f"/agents/{agent_id}/follow")
            if isinstance(resp, dict):
                return resp.get("success", True)
            return True
        except Exception:
            logger.warning("Moltbook unfollow failed for %s", agent_id, exc_info=True)
            return False

    async def register_agent(
        self, name: str, description: str
    ) -> RegistrationResult:
        """Register a new agent on Moltbook (no pre-existing auth required).

        Returns the API key immediately upon registration.
        """
        try:
            resp = await self._http_client.post(
                self._url("/agents/register"),
                json={"name": name, "description": description},
                platform="moltbook",
            )
            if isinstance(resp, dict):
                agent_data = resp.get("agent", resp)
                return RegistrationResult(
                    success=True,
                    claim_url=agent_data.get("claim_url"),
                    verification_code=agent_data.get("verification_code"),
                    api_key=agent_data.get("api_key"),
                )
            return RegistrationResult(success=False, error="Unexpected response format")
        except Exception as exc:
            return RegistrationResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # META
    # ------------------------------------------------------------------

    def get_rate_limit_config(self) -> RateLimitConfig:
        return self._RATE_LIMIT

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    def _map_post(self, raw: dict[str, Any]) -> PlatformPost:
        # Author may be nested object or plain string
        author = raw.get("author")
        if isinstance(author, dict):
            author = author.get("name", "")
        # Community may be nested object
        submolt = raw.get("submolt", raw.get("community"))
        if isinstance(submolt, dict):
            submolt = submolt.get("name", "")

        return PlatformPost(
            platform="moltbook",
            post_id=str(raw.get("id", raw.get("post_id", ""))),
            title=raw.get("title"),
            content=raw.get("content"),
            author=author,
            community=submolt,
            url=raw.get("url"),
            created_at=_parse_datetime(raw.get("created_at")),
            score=int(raw.get("upvotes", raw.get("score", 0))) - int(raw.get("downvotes", 0)),
            comment_count=int(raw.get("comment_count", raw.get("comments", 0))),
        )

    @staticmethod
    def _map_comment(raw: dict[str, Any], post_id: str) -> PlatformComment:
        author = raw.get("author")
        if isinstance(author, dict):
            author = author.get("name", "")
        return PlatformComment(
            platform="moltbook",
            comment_id=str(raw.get("id", raw.get("comment_id", ""))),
            post_id=post_id,
            content=raw.get("content"),
            author=author,
            parent_comment_id=str(raw["parent_id"]) if raw.get("parent_id") else None,
            created_at=_parse_datetime(raw.get("created_at")),
        )

    @staticmethod
    def _map_community(raw: dict[str, Any]) -> PlatformCommunity:
        return PlatformCommunity(
            platform="moltbook",
            name=raw.get("name", ""),
            display_name=raw.get("display_name", raw.get("name", "")),
            description=raw.get("description"),
        )

    def _map_search_result(self, raw: dict[str, Any]) -> PlatformPost:
        """Map a search result item to a ``PlatformPost``."""
        author = raw.get("author")
        if isinstance(author, dict):
            author = author.get("name", "")
        submolt = raw.get("submolt")
        if isinstance(submolt, dict):
            submolt = submolt.get("name", "")

        return PlatformPost(
            platform="moltbook",
            post_id=str(raw.get("post_id", raw.get("id", ""))),
            title=raw.get("title"),
            content=raw.get("content"),
            author=author,
            community=submolt,
            url=raw.get("url"),
            created_at=_parse_datetime(raw.get("created_at")),
            score=int(raw.get("upvotes", raw.get("score", 0))) - int(raw.get("downvotes", 0)),
            comment_count=int(raw.get("comment_count", raw.get("comments", 0))),
        )
