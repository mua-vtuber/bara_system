from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.api.dependencies import get_collected_info_repo
from app.core.logging import get_logger
from app.repositories.collected_info import CollectedInfoRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/api/collected-info", tags=["collected-info"])


@router.get("")
async def list_collected_info(
    query: Optional[str] = Query(None, alias="q", description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    bookmarked: bool = Query(False, description="Show bookmarked only"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    repo: CollectedInfoRepository = Depends(get_collected_info_repo),
) -> JSONResponse:
    """Return a list of collected information items."""
    items = await repo.search(
        query=query,
        category=category,
        bookmarked_only=bookmarked,
        limit=limit,
        offset=offset,
    )

    return JSONResponse(
        content={
            "items": [i.model_dump(mode="json") for i in items],
            "total": len(items),
            "limit": limit,
            "offset": offset,
        }
    )


@router.get("/categories")
async def list_categories(
    repo: CollectedInfoRepository = Depends(get_collected_info_repo),
) -> JSONResponse:
    """Return all distinct categories."""
    categories = await repo.get_categories()
    return JSONResponse(content={"categories": categories})


@router.get("/{item_id}")
async def get_collected_info(
    item_id: int,
    repo: CollectedInfoRepository = Depends(get_collected_info_repo),
) -> JSONResponse:
    """Return details for a single collected-info entry."""
    item = await repo.get_by_id(item_id)
    if item is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"CollectedInfo {item_id} not found"},
        )
    return JSONResponse(content=item.model_dump(mode="json"))


@router.post("/{item_id}/bookmark")
async def toggle_bookmark(
    item_id: int,
    repo: CollectedInfoRepository = Depends(get_collected_info_repo),
) -> JSONResponse:
    """Toggle the bookmark flag on a collected-info entry."""
    try:
        new_state = await repo.toggle_bookmark(item_id)
    except ValueError:
        return JSONResponse(
            status_code=404,
            content={"detail": f"CollectedInfo {item_id} not found"},
        )

    return JSONResponse(
        content={
            "id": item_id,
            "bookmarked": new_state,
        }
    )
