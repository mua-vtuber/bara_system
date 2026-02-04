from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel as PydanticBaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/commands", tags=["commands"])


class CommandRequest(PydanticBaseModel):
    command: str
    args: dict[str, Any] = {}


class CommandResponse(PydanticBaseModel):
    success: bool
    command: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


@router.post("")
async def execute_command(
    body: CommandRequest,
    request: Request,
) -> JSONResponse:
    """Execute a slash command.

    Supported commands:
    - /post: Create a new post (args: topic, platform)
    - /search: Search posts (args: query, platform, semantic)
    - /status: Get system status
    - /stop: Activate emergency stop
    """
    cmd = body.command.lstrip("/").lower()
    args = body.args

    try:
        if cmd == "post":
            result = await _cmd_post(request, args)
        elif cmd == "search":
            result = await _cmd_search(request, args)
        elif cmd == "status":
            result = await _cmd_status(request)
        elif cmd == "stop":
            result = await _cmd_stop(request)
        else:
            return JSONResponse(
                status_code=400,
                content=CommandResponse(
                    success=False,
                    command=cmd,
                    error=f"Unknown command: /{cmd}. "
                    "Supported: /post, /search, /status, /stop",
                ).model_dump(),
            )

        return JSONResponse(
            content=CommandResponse(
                success=True,
                command=cmd,
                result=result,
            ).model_dump(),
        )

    except Exception as exc:
        logger.error("Command /%s failed: %s", cmd, exc)
        return JSONResponse(
            status_code=500,
            content=CommandResponse(
                success=False,
                command=cmd,
                error="Command execution failed",
            ).model_dump(),
        )


# ------------------------------------------------------------------
# Command handlers
# ------------------------------------------------------------------


async def _cmd_post(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    """Create a new post via the strategy engine."""
    topic: str = args.get("topic", "")
    platform_name: str = args.get("platform", "")

    if not topic:
        raise ValueError("Missing required argument: topic")
    if not platform_name:
        raise ValueError("Missing required argument: platform")

    strategy_engine = request.app.state.strategy_engine
    platform_registry = request.app.state.platform_registry

    # Generate post content
    checked_post = await strategy_engine.generate_post(topic, platform_name)
    if not checked_post.passed:
        return {
            "posted": False,
            "issues": checked_post.issues,
        }

    # Get adapter and create the post
    adapter = platform_registry.get_adapter(platform_name)
    result = await adapter.create_post(
        title=checked_post.title,
        content=checked_post.content,
        community=checked_post.community,
    )

    return {
        "posted": result.success,
        "post_id": result.post_id,
        "url": result.url,
        "error": result.error,
    }


async def _cmd_search(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    """Search posts on a platform."""
    query: str = args.get("query", "")
    platform_name: str = args.get("platform", "")
    semantic: bool = args.get("semantic", False)

    if not query:
        raise ValueError("Missing required argument: query")
    if not platform_name:
        raise ValueError("Missing required argument: platform")

    platform_registry = request.app.state.platform_registry
    adapter = platform_registry.get_adapter(platform_name)

    posts = await adapter.search(query, semantic=semantic, limit=25)

    return {
        "query": query,
        "platform": platform_name,
        "count": len(posts),
        "posts": [
            {
                "post_id": p.post_id,
                "title": p.title,
                "author": p.author,
                "url": p.url,
                "score": p.score,
            }
            for p in posts
        ],
    }


async def _cmd_status(request: Request) -> dict[str, Any]:
    """Return system status summary."""
    scheduler = request.app.state.scheduler
    kill_switch = request.app.state.kill_switch
    task_queue = request.app.state.task_queue
    platform_registry = request.app.state.platform_registry

    return {
        "scheduler": scheduler.get_state(),
        "kill_switch_active": kill_switch.is_active,
        "queue_sizes": task_queue.get_queue_sizes(),
        "platforms": platform_registry.get_status_summary(),
    }


async def _cmd_stop(request: Request) -> dict[str, Any]:
    """Activate the emergency kill switch."""
    kill_switch = request.app.state.kill_switch

    if kill_switch.is_active:
        return {"already_active": True}

    await kill_switch.activate(source="command")
    return {"activated": True}
