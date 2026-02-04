from __future__ import annotations

from datetime import datetime

from app.models.base import BaseModel


class SettingsSnapshot(BaseModel):
    id: int
    timestamp: datetime
    config_snapshot: str
