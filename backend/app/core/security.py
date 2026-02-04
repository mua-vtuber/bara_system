from __future__ import annotations

import re

from pydantic import BaseModel

from app.core.config import Config
from app.core.constants import MAX_REGEX_PATTERN_LENGTH
from app.core.logging import get_logger

logger = get_logger(__name__)

# Level 1 auto-block patterns -- always compiled, never user-configurable.
_SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    # Generic API key formats
    re.compile(r"moltbook_[A-Za-z0-9]{16,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"sk_live_[A-Za-z0-9]{20,}"),
    re.compile(r"sk_test_[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"glpat-[A-Za-z0-9\-]{20,}"),
    re.compile(r"xox[bprs]-[A-Za-z0-9\-]+"),
    # .env-style secret lines
    re.compile(r"(?i)(?:api[_-]?key|secret|token|password)\s*[=:]\s*\S+"),
    # Bearer tokens in raw form
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
]


class FilterResult(BaseModel):
    """Outcome of a single ``SecurityFilter.filter_content`` call."""

    level: int  # 1 = auto-blocked, 2 = flagged, 3 = passed
    passed: bool
    reason: str = ""
    matched_patterns: list[str] = []


class SecurityFilter:
    """Three-tier content filter.

    * **Level 1** (auto-block): hard-coded patterns for API keys and secrets.
    * **Level 2** (flag): user-configured ``blocked_keywords`` / ``blocked_patterns``.
    * **Level 3** (pass): everything else.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._blocked_keywords: list[str] = list(config.security.blocked_keywords)
        self._blocked_regexes: list[re.Pattern[str]] = self._compile_patterns(
            config.security.blocked_patterns
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def filter_content(self, content: str) -> FilterResult:
        """Run all three filter levels and return the result."""
        # Level 1 -- hard-coded sensitive patterns
        matched: list[str] = []
        for pattern in _SENSITIVE_PATTERNS:
            if pattern.search(content):
                matched.append(pattern.pattern)
        if matched:
            return FilterResult(
                level=1,
                passed=False,
                reason="Content contains sensitive data (API keys / secrets)",
                matched_patterns=matched,
            )

        # Level 2 -- user-configured keywords and patterns
        matched = []
        content_lower = content.lower()
        for kw in self._blocked_keywords:
            if kw.lower() in content_lower:
                matched.append(f"keyword:{kw}")
        for regex in self._blocked_regexes:
            if regex.search(content):
                matched.append(f"pattern:{regex.pattern}")
        if matched:
            return FilterResult(
                level=2,
                passed=False,
                reason="Content matches blocked keywords or patterns",
                matched_patterns=matched,
            )

        # Level 3 -- passed
        return FilterResult(level=3, passed=True)

    def reload_patterns(self, config: Config) -> None:
        """Hot-reload blocked keywords and patterns from a refreshed config."""
        self._config = config
        self._blocked_keywords = list(config.security.blocked_keywords)
        self._blocked_regexes = self._compile_patterns(config.security.blocked_patterns)
        logger.info("Security filter patterns reloaded")

    # ------------------------------------------------------------------
    # Korean ratio helper
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_korean_ratio(text: str) -> float:
        """Return the fraction of characters that are Korean (Hangul).

        Whitespace and punctuation are excluded from both numerator and
        denominator so that formatting does not skew the result.
        """
        if not text:
            return 0.0
        chars = [ch for ch in text if not ch.isspace() and ch.isalnum()]
        if not chars:
            return 0.0
        korean_count = sum(
            1 for ch in chars if "\uac00" <= ch <= "\ud7a3" or "\u3131" <= ch <= "\u3163"
        )
        return korean_count / len(chars)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _compile_patterns(raw_patterns: list[str]) -> list[re.Pattern[str]]:
        compiled: list[re.Pattern[str]] = []
        for pat in raw_patterns:
            if len(pat) > MAX_REGEX_PATTERN_LENGTH:
                logger.warning(
                    "Regex pattern too long (%d chars), skipped", len(pat)
                )
                continue
            # Reject patterns with nested quantifiers that cause ReDoS.
            if re.search(r"\([^)]*[+*][^)]*\)[+*?]", pat):
                logger.warning(
                    "Regex pattern with nested quantifiers rejected: %s", pat
                )
                continue
            try:
                compiled.append(re.compile(pat, re.IGNORECASE))
            except re.error:
                logger.warning("Invalid regex pattern ignored: %s", pat)
        return compiled

    # ------------------------------------------------------------------
    # Input sanitization (for LLM prompts and user-facing content)
    # ------------------------------------------------------------------

    # Patterns that indicate prompt-injection attempts.
    _INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"ignore\s+(all\s+)?above", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?previous", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
        re.compile(r"new\s+instructions?:", re.IGNORECASE),
        re.compile(r"^system\s*:", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^assistant\s*:", re.IGNORECASE | re.MULTILINE),
        re.compile(r"```\s*(system|assistant)", re.IGNORECASE),
    )

    @classmethod
    def sanitize_input(cls, text: str) -> str:
        """Remove control characters and common prompt-injection markers."""
        if not text:
            return text
        # Strip null bytes and ASCII control chars (except newline / tab).
        cleaned = "".join(
            ch for ch in text if ch in ("\n", "\t") or (ord(ch) >= 32)
        )
        # Replace prompt-injection patterns with harmless placeholders.
        for pat in cls._INJECTION_PATTERNS:
            cleaned = pat.sub("[filtered]", cleaned)
        return cleaned

    def filter_input(self, content: str) -> str:
        """Public entry-point: sanitize user/platform content before LLM use."""
        return self.sanitize_input(content)
