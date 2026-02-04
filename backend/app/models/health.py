from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.base import BaseModel


class ComponentHealth(BaseModel):
    name: str
    status: str
    message: Optional[str] = None
    latency_ms: Optional[float] = None


class HealthCheckResult(BaseModel):
    status: str
    checks: list[ComponentHealth]
    uptime_seconds: float
    timestamp: datetime
    vram_usage_mb: Optional[float] = None
    vram_total_mb: Optional[float] = None
    disk_free_gb: Optional[float] = None
