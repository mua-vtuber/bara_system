from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/emergency", tags=["emergency"])


@router.post("-stop")
async def emergency_stop(request: Request) -> JSONResponse:
    """Activate the emergency kill switch.

    Stops the scheduler and task queue immediately.
    """
    kill_switch = request.app.state.kill_switch

    if kill_switch.is_active:
        return JSONResponse(
            status_code=409,
            content={"detail": "Emergency stop already active"},
        )

    await kill_switch.activate(source="api")
    logger.warning("Emergency stop activated via API")

    return JSONResponse(
        content={"detail": "Emergency stop activated", "active": True}
    )


@router.post("-resume")
async def emergency_resume(request: Request) -> JSONResponse:
    """Deactivate the emergency kill switch.

    Clears the stop state and removes the STOP_BOT file if present.
    The scheduler must be restarted separately.
    """
    kill_switch = request.app.state.kill_switch

    if not kill_switch.is_active:
        return JSONResponse(
            status_code=409,
            content={"detail": "Emergency stop is not active"},
        )

    await kill_switch.deactivate()

    # Restart scheduler and task queue
    scheduler = request.app.state.scheduler
    task_queue = request.app.state.task_queue

    try:
        await task_queue.start()
        await scheduler.start()
        logger.info("Scheduler and task queue restarted after emergency resume")
    except Exception as exc:
        logger.error("Failed to restart services after resume: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Emergency stop cleared but failed to restart services",
                "error": str(exc),
            },
        )

    return JSONResponse(
        content={"detail": "Emergency stop deactivated, services restarted", "active": False}
    )


@router.get("-status")
async def emergency_status(request: Request) -> JSONResponse:
    """Return the current emergency stop state."""
    kill_switch = request.app.state.kill_switch
    scheduler = request.app.state.scheduler

    return JSONResponse(
        content={
            "active": kill_switch.is_active,
            "scheduler_running": scheduler.is_running,
            "scheduler_state": scheduler.get_state(),
        }
    )
