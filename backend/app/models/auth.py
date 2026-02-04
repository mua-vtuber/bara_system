from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.base import BaseModel


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    success: bool
    session_token: Optional[str] = None
    error: Optional[str] = None


class Session(BaseModel):
    session_id: str
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
