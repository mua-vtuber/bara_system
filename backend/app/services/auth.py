from __future__ import annotations

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import Config
from app.core.constants import (
    DEFAULT_MAX_SESSION_COUNT,
    PASSWORD_MIN_LENGTH,
    PASSWORD_MAX_LENGTH,
    WS_TICKET_EXPIRY_SECONDS,
)
from app.core.database import Database
from app.core.logging import get_logger
from app.models.auth import Session

logger = get_logger(__name__)

_HASH_ALGORITHM = "sha256"
_HASH_ITERATIONS = 600_000
_SALT_LENGTH = 32
_TOKEN_BYTES = 32


def _sanitize_env_value(value: str) -> str:
    """Strip characters that could inject new env vars or shell commands."""
    # Remove newlines (prevents injecting new KEY=VALUE lines)
    value = value.replace("\n", "").replace("\r", "")
    # Remove shell metacharacters
    for ch in ("$", "`", "|", ";", ">", "<"):
        value = value.replace(ch, "")
    return value


class AuthService:
    """Handles password verification, session management, and login-attempt tracking.

    Sessions and login attempts are stored in-memory. A server restart clears
    both, which is the intended behaviour for this single-instance deployment.
    """

    def __init__(self, config: Config, db: Database) -> None:
        self._config = config
        self._db = db

        # session_token -> Session
        self._sessions: dict[str, Session] = {}
        # ip -> list of unix-epoch timestamps of failed attempts
        self._login_attempts: dict[str, list[float]] = {}
        # WebSocket one-time tickets: ticket_str -> (session, expiry_timestamp)
        self._ws_tickets: dict[str, tuple[Session, float]] = {}

    # ------------------------------------------------------------------
    # Password hashing
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_password(password: str, salt: bytes | None = None) -> str:
        """Return ``salt_hex:hash_hex`` using PBKDF2-HMAC-SHA256."""
        if salt is None:
            salt = os.urandom(_SALT_LENGTH)
        dk = hashlib.pbkdf2_hmac(
            _HASH_ALGORITHM,
            password.encode("utf-8"),
            salt,
            _HASH_ITERATIONS,
        )
        return f"{salt.hex()}:{dk.hex()}"

    @staticmethod
    def _verify_hash(password: str, stored_hash: str) -> bool:
        """Verify *password* against a ``salt_hex:hash_hex`` string."""
        try:
            salt_hex, expected_hex = stored_hash.split(":", 1)
            salt = bytes.fromhex(salt_hex)
        except (ValueError, IndexError):
            return False
        dk = hashlib.pbkdf2_hmac(
            _HASH_ALGORITHM,
            password.encode("utf-8"),
            salt,
            _HASH_ITERATIONS,
        )
        return secrets.compare_digest(dk.hex(), expected_hex)

    # ------------------------------------------------------------------
    # Password management
    # ------------------------------------------------------------------

    def verify_password(self, password: str) -> bool:
        """Compare *password* against the hash stored in ``EnvSettings``."""
        stored = self._config.env.web_ui_password_hash
        if not stored:
            return False
        return self._verify_hash(password, stored)

    def set_password(self, password: str) -> str:
        """Hash *password*, persist to ``.env``, and update running config.

        Returns the new hash string.
        """
        new_hash = self._hash_password(password)
        self._persist_env_value("WEB_UI_PASSWORD_HASH", new_hash)
        self._config.env.web_ui_password_hash = new_hash
        logger.info("Password hash updated")
        return new_hash

    def is_setup_complete(self) -> bool:
        """Return True when the initial password has been configured."""
        return bool(self._config.env.web_ui_password_hash)

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(self, ip_address: str) -> Session:
        """Create a new session token and return a ``Session`` model."""
        # Enforce maximum session count.
        max_sessions = self._config.web_security.max_session_count
        while len(self._sessions) >= max_sessions:
            # Evict the oldest session.
            oldest_key = min(
                self._sessions, key=lambda k: self._sessions[k].created_at
            )
            self._sessions.pop(oldest_key, None)
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        now = datetime.now(timezone.utc)
        timeout_hours = self._config.web_security.session_timeout_hours
        session = Session(
            session_id=token,
            created_at=now,
            expires_at=now + timedelta(hours=timeout_hours),
            ip_address=ip_address,
        )
        self._sessions[token] = session
        logger.info("Session created for ip=%s", ip_address)
        return session

    def validate_session(self, session_token: str) -> Session | None:
        """Return the ``Session`` if the token is valid and not expired."""
        session = self._sessions.get(session_token)
        if session is None:
            return None
        if datetime.now(timezone.utc) > session.expires_at:
            self._sessions.pop(session_token, None)
            logger.info("Session expired: %s...", session_token[:8])
            return None
        return session

    def invalidate_session(self, session_token: str) -> None:
        """Remove a session, effectively logging the user out."""
        removed = self._sessions.pop(session_token, None)
        if removed:
            logger.info("Session invalidated: %s...", session_token[:8])

    # ------------------------------------------------------------------
    # Login-attempt tracking
    # ------------------------------------------------------------------

    def record_login_attempt(self, ip: str, success: bool) -> None:
        """Record a login attempt.  Successful attempts clear the history."""
        if success:
            self._login_attempts.pop(ip, None)
            return
        attempts = self._login_attempts.setdefault(ip, [])
        attempts.append(time.time())

    def is_locked_out(self, ip: str) -> bool:
        """Return True when *ip* has exceeded the allowed login attempts."""
        max_attempts = self._config.web_security.max_login_attempts
        lockout_seconds = self._config.web_security.lockout_minutes * 60
        attempts = self._login_attempts.get(ip)
        if not attempts:
            return False
        cutoff = time.time() - lockout_seconds
        recent = [t for t in attempts if t > cutoff]
        # keep only recent entries
        self._login_attempts[ip] = recent
        return len(recent) >= max_attempts

    # ------------------------------------------------------------------
    # .env persistence helper
    # ------------------------------------------------------------------

    @staticmethod
    def _persist_env_value(key: str, value: str) -> None:
        """Write or update *key=value* in the ``.env`` file."""
        value = _sanitize_env_value(value)
        env_path = Path(".env")
        lines: list[str] = []
        found = False

        if env_path.exists():
            raw = env_path.read_text(encoding="utf-8")
            for line in raw.splitlines():
                if line.startswith(f"{key}="):
                    lines.append(f"{key}={value}")
                    found = True
                else:
                    lines.append(line)

        if not found:
            lines.append(f"{key}={value}")

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # Session cleanup
    # ------------------------------------------------------------------

    def cleanup_expired_sessions(self) -> int:
        """Remove all expired sessions and tickets. Returns count removed."""
        now_utc = datetime.now(timezone.utc)
        now_ts = now_utc.timestamp()

        expired_sessions = [
            k for k, s in self._sessions.items() if now_utc > s.expires_at
        ]
        for key in expired_sessions:
            self._sessions.pop(key, None)

        expired_tickets = [
            k for k, (_, exp) in self._ws_tickets.items() if now_ts > exp
        ]
        for key in expired_tickets:
            self._ws_tickets.pop(key, None)

        total = len(expired_sessions) + len(expired_tickets)
        if total:
            logger.debug("Cleaned up %d expired sessions/tickets", total)
        return total

    # ------------------------------------------------------------------
    # Password complexity
    # ------------------------------------------------------------------

    @staticmethod
    def validate_password_complexity(password: str) -> tuple[bool, str]:
        """Validate password meets security requirements.

        Returns (True, "") on success, or (False, reason) on failure.
        """
        if len(password) < PASSWORD_MIN_LENGTH:
            return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
        if len(password) > PASSWORD_MAX_LENGTH:
            return False, f"Password must be at most {PASSWORD_MAX_LENGTH} characters."
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter."
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter."
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit."
        if not any(not c.isalnum() for c in password):
            return False, "Password must contain at least one special character."
        return True, ""

    def change_password(
        self, current_password: str, new_password: str
    ) -> tuple[bool, str]:
        """Change the password after verifying the current one."""
        if not self.verify_password(current_password):
            return False, "Current password is incorrect."
        ok, reason = self.validate_password_complexity(new_password)
        if not ok:
            return False, reason
        self.set_password(new_password)
        return True, "Password changed successfully."

    # ------------------------------------------------------------------
    # WebSocket one-time tickets
    # ------------------------------------------------------------------

    def create_ws_ticket(self, session_token: str) -> str | None:
        """Create a short-lived, single-use ticket for WebSocket auth.

        Returns the ticket string, or None if the session is invalid.
        """
        session = self.validate_session(session_token)
        if session is None:
            return None
        ticket = secrets.token_urlsafe(32)
        expiry = datetime.now(timezone.utc).timestamp() + WS_TICKET_EXPIRY_SECONDS
        self._ws_tickets[ticket] = (session, expiry)
        return ticket

    def validate_ws_ticket(self, ticket: str) -> Session | None:
        """Validate and consume a one-time WebSocket ticket.

        The ticket is invalidated immediately after use.
        """
        entry = self._ws_tickets.pop(ticket, None)
        if entry is None:
            return None
        session, expiry = entry
        if datetime.now(timezone.utc).timestamp() > expiry:
            return None
        # Also verify the underlying session is still valid.
        if self.validate_session(session.session_id) is None:
            return None
        return session
