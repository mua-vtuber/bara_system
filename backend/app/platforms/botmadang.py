from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

from app.core.config import Config
from app.core.constants import PlatformCapability
from app.core.exceptions import PlatformError
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


class BotmadangAdapter(PlatformAdapter):
    """Platform adapter for Botmadang (https://botmadang.org/api/v1).

    Capabilities: NOTIFICATIONS, AGENT_REGISTRATION, DOWNVOTE.
    Does NOT support: SEMANTIC_SEARCH, FOLLOW, NESTED_COMMENTS.
    """

    _CAPABILITIES: set[PlatformCapability] = {
        PlatformCapability.NOTIFICATIONS,
        PlatformCapability.AGENT_REGISTRATION,
        PlatformCapability.DOWNVOTE,
    }

    _RATE_LIMIT = RateLimitConfig(
        post_cooldown_seconds=180,
        comment_cooldown_seconds=10,
        api_calls_per_minute=100,
        comments_per_day=100,
    )

    _ALLOWED_HOSTNAME: str = "botmadang.org"

    def __init__(
        self,
        config: Config,
        http_client: HttpClient,
        rate_limiter: PlatformRateLimiter,
        security_filter: SecurityFilter,
    ) -> None:
        super().__init__(config, http_client, rate_limiter, security_filter)
        self._base_url: str = config.platforms.botmadang.base_url.rstrip("/")
        self._api_key: str = os.environ.get("BOTMADANG_API_KEY", config.env.botmadang_api_key)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_safe_url(self, url: str) -> bool:
        """Verify the URL points to the expected Botmadang domain."""
        try:
            parsed = urlparse(url)
            return parsed.hostname == self._ALLOWED_HOSTNAME
        except Exception:
            return False

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        url = self._url(path)
        if not self._is_safe_url(url):
            logger.error("SSRF blocked: URL %s does not match allowed domain", url)
            raise PlatformError(platform="botmadang", message="Invalid URL domain")
        return await self._http_client.get(
            url,
            headers=self._auth_headers(),
            params=params,
            platform="botmadang",
        )

    async def _post(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        url = self._url(path)
        if not self._is_safe_url(url):
            logger.error("SSRF blocked: URL %s does not match allowed domain", url)
            raise PlatformError(platform="botmadang", message="Invalid URL domain")
        return await self._http_client.post(
            url,
            headers=self._auth_headers(),
            json=json,
            platform="botmadang",
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def platform_name(self) -> str:
        return "botmadang"

    @property
    def is_authenticated(self) -> bool:
        return bool(self._api_key)

    def get_capabilities(self) -> set[PlatformCapability]:
        return self._CAPABILITIES

    # ------------------------------------------------------------------
    # AUTH
    # ------------------------------------------------------------------

    async def validate_credentials(self) -> bool:
        if not self._api_key:
            return False
        try:
            resp = await self._get("/agents/me")
            return isinstance(resp, dict) and "name" in resp
        except Exception:
            logger.warning("Botmadang credential validation failed", exc_info=True)
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
            params["submadang"] = community
        resp = await self._get("/posts", params=params)
        items = resp if isinstance(resp, list) else resp.get("posts", resp.get("data", []))
        return [self._map_post(p) for p in items]

    async def get_post_detail(self, post_id: str) -> PlatformPost:
        resp = await self._get(f"/posts/{post_id}")
        data = resp if "post_id" in resp or "id" in resp else resp.get("post", resp.get("data", resp))
        return self._map_post(data)

    async def get_comments(self, post_id: str) -> list[PlatformComment]:
        resp = await self._get(f"/posts/{post_id}/comments")
        items = resp if isinstance(resp, list) else resp.get("comments", resp.get("data", []))
        return [self._map_comment(c, post_id) for c in items]

    async def get_communities(self) -> list[PlatformCommunity]:
        resp = await self._get("/submadangs")
        items = resp if isinstance(resp, list) else resp.get("submadangs", resp.get("data", []))
        return [self._map_community(c) for c in items]

    async def get_notifications(
        self,
        since: Optional[datetime] = None,
        unread_only: bool = True,
    ) -> list[PlatformNotification]:
        params: dict[str, Any] = {}
        if unread_only:
            params["unread_only"] = "true"
        if since:
            params["since"] = since.isoformat()
        resp = await self._get("/notifications", params=params)
        items = resp if isinstance(resp, list) else resp.get("notifications", resp.get("data", []))
        return [self._map_notification(n) for n in items]

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
            json={"title": title, "content": content, "submadang": community},
        )
        if isinstance(resp, dict):
            data = resp.get("post", resp.get("data", resp))
            return PlatformPostResult(
                success=True,
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
        # Botmadang does not support nested comments; ignore parent_comment_id
        filter_result = self._security_filter.filter_content(content)
        if not filter_result.passed:
            return PlatformCommentResult(
                success=False,
                error=f"Security filter blocked: {filter_result.reason}",
            )

        resp = await self._post(
            f"/posts/{post_id}/comments",
            json={"content": content},
        )
        if isinstance(resp, dict):
            data = resp.get("comment", resp.get("data", resp))
            return PlatformCommentResult(
                success=True,
                comment_id=str(data.get("id", data.get("comment_id", ""))),
            )
        return PlatformCommentResult(success=False, error="Unexpected response format")

    async def upvote(self, post_id: str) -> bool:
        try:
            await self._post(f"/posts/{post_id}/upvote")
            return True
        except Exception:
            logger.warning("Botmadang upvote failed for post %s", post_id, exc_info=True)
            return False

    async def downvote(self, post_id: str) -> bool:
        try:
            await self._post(f"/posts/{post_id}/downvote")
            return True
        except Exception:
            logger.warning("Botmadang downvote failed for post %s", post_id, exc_info=True)
            return False

    async def mark_notifications_read(
        self,
        notification_ids: list[str] | str,
    ) -> bool:
        payload: dict[str, Any]
        if notification_ids == "all":
            payload = {"notification_ids": "all"}
        else:
            payload = {"notification_ids": notification_ids}
        try:
            await self._post("/notifications/read", json=payload)
            return True
        except Exception:
            logger.warning("Botmadang mark_notifications_read failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # PLATFORM-SPECIFIC
    # ------------------------------------------------------------------

    async def register_agent(
        self, name: str, description: str
    ) -> RegistrationResult:
        """Register a new agent on Botmadang (no auth required)."""
        try:
            resp = await self._http_client.post(
                self._url("/agents/register"),
                json={"name": name, "description": description},
                platform="botmadang",
            )
            if isinstance(resp, dict):
                return RegistrationResult(
                    success=True,
                    claim_url=resp.get("claim_url"),
                    verification_code=resp.get("verification_code"),
                    api_key=resp.get("api_key"),
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
        return PlatformPost(
            platform="botmadang",
            post_id=str(raw.get("id", raw.get("post_id", ""))),
            title=raw.get("title"),
            content=raw.get("content"),
            author=raw.get("author", raw.get("author_name")),
            community=raw.get("submadang", raw.get("community")),
            url=raw.get("url"),
            created_at=_parse_datetime(raw.get("created_at")),
            score=int(raw.get("score", raw.get("upvotes", 0))),
            comment_count=int(raw.get("comment_count", raw.get("comments", 0))),
        )

    @staticmethod
    def _map_comment(raw: dict[str, Any], post_id: str) -> PlatformComment:
        return PlatformComment(
            platform="botmadang",
            comment_id=str(raw.get("id", raw.get("comment_id", ""))),
            post_id=post_id,
            content=raw.get("content"),
            author=raw.get("author", raw.get("author_name")),
            parent_comment_id=None,  # Botmadang does not support nested comments
            created_at=_parse_datetime(raw.get("created_at")),
        )

    @staticmethod
    def _map_community(raw: dict[str, Any]) -> PlatformCommunity:
        return PlatformCommunity(
            platform="botmadang",
            name=raw.get("name", ""),
            display_name=raw.get("display_name", raw.get("name", "")),
            description=raw.get("description"),
        )

    @staticmethod
    def _map_notification(raw: dict[str, Any]) -> PlatformNotification:
        return PlatformNotification(
            platform="botmadang",
            notification_id=str(raw.get("id", raw.get("notification_id", ""))),
            notification_type=raw.get("type", raw.get("notification_type", "")),
            actor_name=raw.get("actor_name", raw.get("actor", {}).get("name") if isinstance(raw.get("actor"), dict) else raw.get("actor")),
            post_id=str(raw.get("post_id", "")) if raw.get("post_id") else None,
            post_title=raw.get("post_title"),
            comment_id=str(raw.get("comment_id", "")) if raw.get("comment_id") else None,
            content_preview=raw.get("content_preview", raw.get("preview")),
            is_read=bool(raw.get("is_read", False)),
            created_at=_parse_datetime(raw.get("created_at")),
        )
