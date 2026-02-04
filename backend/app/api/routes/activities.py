from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.dependencies import get_activity_repo
from app.core.logging import get_logger
from app.repositories.activity import ActivityRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/api/activities", tags=["activities"])


@router.get("")
async def list_activities(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    type: Optional[str] = Query(None, alias="type", description="Filter by activity type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start: Optional[str] = Query(None, description="Start date (ISO format)"),
    end: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    activity_repo: ActivityRepository = Depends(get_activity_repo),
) -> JSONResponse:
    """Return a paginated timeline of bot activities."""
    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None

    if start:
        try:
            start_dt = datetime.fromisoformat(start)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid start date format. Use ISO format."},
            )
    if end:
        try:
            end_dt = datetime.fromisoformat(end)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid end date format. Use ISO format."},
            )

    # Use status filter path if provided
    if status:
        activities = await activity_repo.get_by_status(status, limit=limit)
        return JSONResponse(
            content={
                "items": [a.model_dump(mode="json") for a in activities],
                "total": len(activities),
            }
        )

    # General timeline query
    activities = await activity_repo.get_timeline(
        start=start_dt,
        end=end_dt,
        platform_filter=platform,
        type_filter=type,
        limit=limit,
        offset=offset,
    )

    return JSONResponse(
        content={
            "items": [a.model_dump(mode="json") for a in activities],
            "total": len(activities),
            "limit": limit,
            "offset": offset,
        }
    )


@router.get("/{activity_id}")
async def get_activity(
    activity_id: int,
    activity_repo: ActivityRepository = Depends(get_activity_repo),
) -> JSONResponse:
    """Return details for a single activity."""
    activity = await activity_repo.get_by_id(activity_id)
    if activity is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Activity {activity_id} not found"},
        )
    return JSONResponse(content=activity.model_dump(mode="json"))
