from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.dependencies import get_platform_registry
from app.platforms.registry import PlatformRegistry

router = APIRouter(prefix="/api/platforms", tags=["platforms"])


# ------------------------------------------------------------------
# Request / Response schemas
# ------------------------------------------------------------------


class ValidateRequest(BaseModel):
    platform: str


class RegisterBotmadangRequest(BaseModel):
    name: str
    description: str


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("")
async def list_platforms(
    registry: PlatformRegistry = Depends(get_platform_registry),
) -> JSONResponse:
    """Return the status of all known platforms."""
    return JSONResponse(content=registry.get_status_summary())


@router.post("/validate")
async def validate_platform(
    body: ValidateRequest,
    registry: PlatformRegistry = Depends(get_platform_registry),
) -> JSONResponse:
    """Test whether the API key for *platform* is valid."""
    try:
        adapter = registry.get_adapter(body.platform)
    except KeyError as exc:
        return JSONResponse(status_code=404, content={"valid": False, "error": str(exc)})

    valid = await adapter.validate_credentials()
    return JSONResponse(content={"platform": body.platform, "valid": valid})


@router.post("/botmadang/register")
async def register_botmadang_agent(
    body: RegisterBotmadangRequest,
    registry: PlatformRegistry = Depends(get_platform_registry),
) -> JSONResponse:
    """Register a new agent on Botmadang.

    Returns a ``claim_url`` and ``verification_code`` that the user must
    verify via X/Twitter.
    """
    try:
        adapter = registry.get_adapter("botmadang")
    except KeyError as exc:
        return JSONResponse(status_code=404, content={"success": False, "error": str(exc)})

    result = await adapter.register_agent(body.name, body.description)
    status_code = 200 if result.success else 400
    return JSONResponse(status_code=status_code, content=result.model_dump())
