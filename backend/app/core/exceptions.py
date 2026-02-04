from __future__ import annotations

from typing import Optional


class BaraSystemError(Exception):
    """Base exception for the bara_system project."""

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(self.message)


class ConfigError(BaraSystemError):
    """Raised when configuration loading or validation fails."""


class DatabaseError(BaraSystemError):
    """Raised when a database operation fails."""


class PlatformError(BaraSystemError):
    """Raised when a platform API call fails."""

    def __init__(
        self,
        platform: str,
        status_code: Optional[int] = None,
        message: str = "",
    ) -> None:
        self.platform = platform
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(PlatformError):
    """Raised when platform authentication fails (401/403)."""


class RateLimitError(PlatformError):
    """Raised when the platform returns a rate-limit response (429)."""

    def __init__(
        self,
        platform: str,
        retry_after: Optional[float] = None,
        status_code: Optional[int] = 429,
        message: str = "",
    ) -> None:
        self.retry_after = retry_after
        super().__init__(platform=platform, status_code=status_code, message=message)


class PlatformServerError(PlatformError):
    """Raised when the platform returns a 5xx server error."""


class NetworkError(PlatformError):
    """Raised when a network-level failure occurs (timeout, DNS, connection refused)."""


class LLMError(BaraSystemError):
    """Base exception for LLM-related failures."""


class LLMConnectionError(LLMError):
    """Raised when the Ollama server is unreachable."""


class LLMGenerationError(LLMError):
    """Raised when the LLM produces an invalid or empty response."""


class SecurityFilterError(BaraSystemError):
    """Raised when content fails a security filter check."""


class KillSwitchActivated(BaraSystemError):
    """Raised when the emergency kill-switch file or API signal is detected."""


class MaxRetriesExceeded(BaraSystemError):
    """Raised when a retriable operation exhausts all retry attempts."""


class SetupIncompleteError(BaraSystemError):
    """Raised when mandatory first-time setup has not been completed."""
