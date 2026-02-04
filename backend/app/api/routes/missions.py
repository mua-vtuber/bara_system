from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel as PydanticBaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/missions", tags=["missions"])


# ------------------------------------------------------------------
# Request / response schemas
# ------------------------------------------------------------------


class MissionCreateRequest(PydanticBaseModel):
    topic: str
    question_hint: str = ""
    urgency: str = "normal"
    target_platform: str = ""
    target_community: str = ""
    user_notes: str = ""


class MissionResponse(PydanticBaseModel):
    id: int
    created_at: str
    topic: str
    question_hint: str = ""
    urgency: str = "normal"
    status: str = "pending"
    target_platform: str = ""
    target_community: str = ""
    warmup_count: int = 0
    warmup_target: int = 3
    post_id: str = ""
    post_platform: str = ""
    collected_responses: list[dict] = []
    summary: str = ""
    completed_at: str | None = None
    user_notes: str = ""


class MissionListResponse(PydanticBaseModel):
    missions: list[MissionResponse]
    total: int


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@router.get("", response_model=MissionListResponse)
async def list_missions(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
) -> MissionListResponse:
    """List all missions with optional status filter."""
    mission_service = request.app.state.mission_service

    if status:
        missions = await mission_service._repo.get_by_status(status)
    else:
        missions = await mission_service.get_all_missions(limit, offset)

    total = await mission_service.count_missions()

    return MissionListResponse(
        missions=[
            MissionResponse(
                **{
                    **m.model_dump(),
                    "created_at": m.created_at.isoformat() if m.created_at else "",
                    "completed_at": m.completed_at.isoformat() if m.completed_at else None,
                }
            )
            for m in missions
        ],
        total=total,
    )


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(
    mission_id: int,
    request: Request,
) -> MissionResponse | JSONResponse:
    """Get a single mission by ID."""
    mission_service = request.app.state.mission_service
    mission = await mission_service.get_mission(mission_id)

    if mission is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "Mission not found"},
        )

    return MissionResponse(
        **{
            **mission.model_dump(),
            "created_at": mission.created_at.isoformat() if mission.created_at else "",
            "completed_at": mission.completed_at.isoformat() if mission.completed_at else None,
        }
    )


@router.post("", response_model=MissionResponse)
async def create_mission(
    body: MissionCreateRequest,
    request: Request,
) -> MissionResponse:
    """Create a new mission manually."""
    from app.models.mission import MissionCreate

    mission_service = request.app.state.mission_service
    mission = await mission_service.create_mission(
        MissionCreate(
            topic=body.topic,
            question_hint=body.question_hint,
            urgency=body.urgency,
            target_platform=body.target_platform,
            target_community=body.target_community,
            user_notes=body.user_notes,
        )
    )

    return MissionResponse(
        **{
            **mission.model_dump(),
            "created_at": mission.created_at.isoformat() if mission.created_at else "",
            "completed_at": mission.completed_at.isoformat() if mission.completed_at else None,
        }
    )


@router.put("/{mission_id}/cancel")
async def cancel_mission(
    mission_id: int,
    request: Request,
) -> JSONResponse:
    """Cancel an active mission."""
    mission_service = request.app.state.mission_service
    mission = await mission_service.get_mission(mission_id)

    if mission is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "Mission not found"},
        )

    if mission.status in ("complete", "cancelled"):
        return JSONResponse(
            status_code=400,
            content={"detail": f"Cannot cancel mission in '{mission.status}' state"},
        )

    await mission_service.cancel_mission(mission_id)
    return JSONResponse(content={"detail": "Mission cancelled"})


@router.put("/{mission_id}/complete")
async def complete_mission(
    mission_id: int,
    request: Request,
) -> JSONResponse:
    """Manually complete a mission and generate summary."""
    mission_service = request.app.state.mission_service
    mission = await mission_service.get_mission(mission_id)

    if mission is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "Mission not found"},
        )

    if mission.status in ("complete", "cancelled"):
        return JSONResponse(
            status_code=400,
            content={"detail": f"Cannot complete mission in '{mission.status}' state"},
        )

    summary = await mission_service.complete_mission(mission)
    return JSONResponse(
        content={"detail": "Mission completed", "summary": summary}
    )


@router.get("/{mission_id}/summary")
async def get_mission_summary(
    mission_id: int,
    request: Request,
    regenerate: bool = Query(default=False),
) -> JSONResponse:
    """Get or regenerate the mission summary."""
    mission_service = request.app.state.mission_service
    mission = await mission_service.get_mission(mission_id)

    if mission is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "Mission not found"},
        )

    if regenerate or not mission.summary:
        summary = await mission_service.generate_summary(mission)
        await mission_service._repo.set_summary(mission_id, summary)
    else:
        summary = mission.summary

    return JSONResponse(content={"summary": summary})
