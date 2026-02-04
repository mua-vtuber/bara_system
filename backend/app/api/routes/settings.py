from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel as PydanticBaseModel

from app.api.dependencies import get_config, get_settings_repo
from app.core.config import Config
from app.core.logging import get_logger
from app.repositories.settings import SettingsRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Sections that can be hot-reloaded at runtime
_MUTABLE_SECTIONS = {"behavior", "voice", "web_security", "security", "ui"}


class SettingsUpdateRequest(PydanticBaseModel):
    section: str
    data: dict[str, Any]


@router.get("")
async def get_settings(
    config: Config = Depends(get_config),
) -> JSONResponse:
    """Return the full current configuration (excluding secrets)."""
    data = config.to_dict()
    # Hide security filter rules from clients.
    if "security" in data:
        data["security"].pop("blocked_keywords", None)
        data["security"].pop("blocked_patterns", None)
    # Hide CSRF secret.
    if "web_security" in data:
        data["web_security"].pop("csrf_secret", None)
    return JSONResponse(content=data)


@router.put("")
async def update_settings(
    body: SettingsUpdateRequest,
    request: Request,
    config: Config = Depends(get_config),
    settings_repo: SettingsRepository = Depends(get_settings_repo),
) -> JSONResponse:
    """Update a configuration section.

    Only mutable sections (behavior, voice, web_security, security, ui)
    can be changed at runtime.
    """
    if body.section not in _MUTABLE_SECTIONS:
        return JSONResponse(
            status_code=400,
            content={
                "detail": (
                    f"Section '{body.section}' cannot be updated at runtime. "
                    f"Mutable sections: {sorted(_MUTABLE_SECTIONS)}"
                )
            },
        )

    # Require re-authentication for web_security changes
    if body.section == "web_security":
        password = body.data.get("_password")
        auth_service = request.app.state.auth_service
        if not password or not auth_service.verify_password(password):
            return JSONResponse(
                status_code=401,
                content={"detail": "Password required to modify security settings"},
            )

    try:
        await config.update_section(body.section, body.data)
    except Exception as exc:
        logger.error("Failed to update section '%s': %s", body.section, exc)
        return JSONResponse(
            status_code=400,
            content={"detail": "Validation error. Check the provided data."},
        )

    # Persist the change to config.json if path is available
    if config.config_path and config.config_path.exists():
        try:
            config.config_path.write_text(
                json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to persist config to file: %s", exc)

    # Save a snapshot for history
    try:
        await settings_repo.save_snapshot(
            json.dumps(config.to_dict(), ensure_ascii=False)
        )
    except Exception as exc:
        logger.warning("Failed to save settings snapshot: %s", exc)

    return JSONResponse(
        content={
            "detail": f"Section '{body.section}' updated successfully",
            "current": config.to_dict(),
        }
    )


@router.get("/history")
async def get_settings_history(
    limit: int = 20,
    settings_repo: SettingsRepository = Depends(get_settings_repo),
) -> JSONResponse:
    """Return the settings change history."""
    snapshots = await settings_repo.get_history(limit=limit)
    return JSONResponse(
        content={
            "items": [s.model_dump(mode="json") for s in snapshots],
            "total": len(snapshots),
        }
    )
