from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.dependencies import get_notification_repo
from app.core.logging import get_logger
from app.repositories.notification import NotificationRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    unread: Optional[bool] = Query(None, description="Filter unread only"),
    limit: int = Query(50, ge=1, le=200),
    notification_repo: NotificationRepository = Depends(get_notification_repo),
) -> JSONResponse:
    """Return a list of notification log entries."""
    if platform and unread:
        items = await notification_repo.get_unprocessed(platform)
        items = items[:limit]
    elif platform:
        rows = await notification_repo.fetch_all(
            "SELECT * FROM notification_log WHERE platform = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (platform, limit),
        )
        from app.models.notification import NotificationLog

        items = [NotificationLog(**r) for r in rows]
    elif unread:
        # Unread across all platforms
        rows = await notification_repo.fetch_all(
            "SELECT * FROM notification_log WHERE is_read = 0 "
            "ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        from app.models.notification import NotificationLog

        items = [NotificationLog(**r) for r in rows]
    else:
        rows = await notification_repo.fetch_all(
            "SELECT * FROM notification_log "
            "ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        from app.models.notification import NotificationLog

        items = [NotificationLog(**r) for r in rows]

    return JSONResponse(
        content={
            "items": [i.model_dump(mode="json") for i in items],
            "total": len(items),
        }
    )


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    notification_repo: NotificationRepository = Depends(get_notification_repo),
) -> JSONResponse:
    """Mark a notification as read."""
    existing = await notification_repo.get_by_id(notification_id)
    if existing is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Notification {notification_id} not found"},
        )

    await notification_repo.mark_responded(notification_id, response_activity_id=0)
    return JSONResponse(content={"detail": "Notification marked as read"})
