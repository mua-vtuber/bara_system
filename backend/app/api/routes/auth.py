from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel as PydanticBaseModel

from app.core.logging import get_logger
from app.core.network import get_client_ip
from app.models.auth import LoginRequest, LoginResponse, Session
from app.services.auth import AuthService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ------------------------------------------------------------------
# Request / response schemas specific to these routes
# ------------------------------------------------------------------


class SetupPasswordRequest(PydanticBaseModel):
    password: str


class SetupPasswordResponse(PydanticBaseModel):
    success: bool
    message: str


class AuthStatusResponse(PydanticBaseModel):
    authenticated: bool
    setup_complete: bool


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response) -> LoginResponse:
    """Authenticate with a password and receive a session cookie."""
    auth_service: AuthService = request.app.state.auth_service
    client_ip = _client_ip(request)

    # Lockout check
    if auth_service.is_locked_out(client_ip):
        auth_service.record_login_attempt(client_ip, success=False)
        logger.warning("Login attempt while locked out: ip=%s", client_ip)
        return LoginResponse(
            success=False,
            error="Too many failed attempts. Please try again later.",
        )

    # Verify password
    if not auth_service.verify_password(body.password):
        auth_service.record_login_attempt(client_ip, success=False)
        logger.warning("Failed login attempt: ip=%s", client_ip)
        return LoginResponse(success=False, error="Invalid password")

    # Success
    auth_service.record_login_attempt(client_ip, success=True)
    session = auth_service.create_session(client_ip)

    response.set_cookie(
        key="session_token",
        value=session.session_id,
        httponly=True,
        samesite="lax",
        secure=request.app.state.config.web_security.https_enabled,
        max_age=request.app.state.config.web_security.session_timeout_hours * 3600,
    )

    logger.info("Successful login: ip=%s", client_ip)
    return LoginResponse(success=True)


@router.post("/logout")
async def logout(request: Request, response: Response) -> JSONResponse:
    """Invalidate the current session and clear the cookie."""
    auth_service: AuthService = request.app.state.auth_service
    token = _extract_token(request)

    if token:
        auth_service.invalidate_session(token)

    response.delete_cookie(key="session_token")
    return JSONResponse(content={"detail": "Logged out"})


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(request: Request) -> AuthStatusResponse:
    """Return current authentication state."""
    auth_service: AuthService = request.app.state.auth_service
    setup_complete = auth_service.is_setup_complete()

    session: Session | None = getattr(request.state, "session", None)
    if session is None:
        # Try manual validation (this route may be called before auth middleware
        # marks the session because /status is useful even when unauthenticated).
        token = _extract_token(request)
        if token:
            session = auth_service.validate_session(token)

    return AuthStatusResponse(
        authenticated=session is not None,
        setup_complete=setup_complete,
    )


@router.post("/setup-password", response_model=SetupPasswordResponse)
async def setup_password(body: SetupPasswordRequest, request: Request) -> SetupPasswordResponse:
    """Set the initial password. Only available when setup is incomplete."""
    auth_service: AuthService = request.app.state.auth_service

    if auth_service.is_setup_complete():
        return SetupPasswordResponse(
            success=False,
            message="Password has already been configured.",
        )

    ok, reason = auth_service.validate_password_complexity(body.password)
    if not ok:
        return SetupPasswordResponse(success=False, message=reason)

    auth_service.set_password(body.password)
    logger.info("Initial password set via setup endpoint")
    return SetupPasswordResponse(success=True, message="Password configured successfully.")


class ChangePasswordRequest(PydanticBaseModel):
    current_password: str
    new_password: str


class ChangePasswordResponse(PydanticBaseModel):
    success: bool
    message: str


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(body: ChangePasswordRequest, request: Request) -> ChangePasswordResponse:
    """Change the current password. Requires authentication."""
    auth_service: AuthService = request.app.state.auth_service
    session = getattr(request.state, "session", None)
    if session is None:
        return ChangePasswordResponse(success=False, message="Authentication required.")
    ok, message = auth_service.change_password(body.current_password, body.new_password)
    if ok:
        logger.info("Password changed: ip=%s", _client_ip(request))
    return ChangePasswordResponse(success=ok, message=message)


@router.post("/ws-ticket")
async def create_ws_ticket(request: Request) -> JSONResponse:
    """Create a short-lived one-time ticket for WebSocket authentication."""
    auth_service: AuthService = request.app.state.auth_service
    token = _extract_token(request)
    if not token:
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    ticket = auth_service.create_ws_ticket(token)
    if ticket is None:
        return JSONResponse(status_code=401, content={"detail": "Invalid session"})
    return JSONResponse(content={"ticket": ticket})


@router.get("/csrf-token")
async def get_csrf_token(request: Request) -> JSONResponse:
    """Return a CSRF token for the current session."""
    from app.api.middleware.csrf import CSRFMiddleware

    config = request.app.state.config
    session = getattr(request.state, "session", None)

    # Try to get session from cookie if middleware hasn't set it.
    if session is None:
        token = _extract_token(request)
        if token:
            auth_service: AuthService = request.app.state.auth_service
            session = auth_service.validate_session(token)

    if session is None:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
        )

    csrf_token = CSRFMiddleware.generate_token(
        config.web_security.csrf_secret, session.session_id
    )
    return JSONResponse(content={"csrf_token": csrf_token})


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _client_ip(request: Request) -> str:
    config = getattr(request.app.state, "config", None)
    trusted = config.web_security.trusted_proxies if config else ()
    return get_client_ip(request, trusted_proxies=trusted)


def _extract_token(request: Request) -> str | None:
    token = request.cookies.get("session_token")
    if token:
        return token
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None
