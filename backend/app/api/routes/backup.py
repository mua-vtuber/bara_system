from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/backup", tags=["backup"])

_BACKUP_DIR = Path("backups")


@router.post("/export")
async def export_backup(request: Request) -> JSONResponse:
    """Create a full backup of the database and config.

    Returns the backup data as JSON and optionally saves it to disk.
    """
    backup_service = request.app.state.backup_service

    try:
        data = await backup_service.export_backup()
    except Exception as exc:
        logger.error("Backup export failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Backup export failed. Check server logs for details."},
        )

    # Save to disk
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{ts}.json"
    filepath = _BACKUP_DIR / filename

    try:
        filepath.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.error("Failed to write backup file: %s", exc)

    return JSONResponse(
        content={
            "detail": "Backup exported successfully",
            "filename": filename,
            "data": data,
        }
    )


@router.post("/import")
async def import_backup(request: Request) -> JSONResponse:
    """Import a backup from JSON body.

    Expects the backup data object directly in the request body.
    """
    backup_service = request.app.state.backup_service

    try:
        body: dict[str, Any] = await request.json()
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid JSON body"},
        )

    # Validate minimal structure
    if "tables" not in body:
        return JSONResponse(
            status_code=400,
            content={"detail": "Missing 'tables' key in backup data"},
        )

    # Re-authenticate for destructive operation.
    password = body.get("password")
    if not password:
        return JSONResponse(
            status_code=400,
            content={"detail": "Password required for backup import"},
        )
    auth_service = request.app.state.auth_service
    if not auth_service.verify_password(password):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid password"},
        )

    try:
        await backup_service.import_backup(body)
    except Exception as exc:
        logger.error("Backup import failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Backup import failed. Check server logs for details."},
        )

    return JSONResponse(
        content={"detail": "Backup imported successfully"}
    )
