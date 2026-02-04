from __future__ import annotations

from enum import Enum


class Platform(str, Enum):
    BOTMADANG = "botmadang"
    MOLTBOOK = "moltbook"


class ActivityType(str, Enum):
    COMMENT = "comment"
    POST = "post"
    REPLY = "reply"
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"
    FOLLOW = "follow"


class ActivityStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    POSTED = "posted"
    REJECTED = "rejected"
    FAILED = "failed"


class BotStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    OFFLINE = "offline"
    STOPPED = "stopped"


class PlatformCapability(str, Enum):
    SEMANTIC_SEARCH = "semantic_search"
    FOLLOW = "follow"
    NESTED_COMMENTS = "nested_comments"
    NOTIFICATIONS = "notifications"
    AGENT_REGISTRATION = "agent_registration"
    DOWNVOTE = "downvote"


# Monitoring and scheduling
DEFAULT_MONITORING_INTERVAL_MINUTES: int = 30
DEFAULT_SESSION_TIMEOUT_HOURS: int = 24
DEFAULT_MAX_LOGIN_ATTEMPTS: int = 5
DEFAULT_LOCKOUT_MINUTES: int = 5
DEFAULT_BUSY_TIMEOUT_MS: int = 5000
MAX_BACKOFF_SECONDS: int = 1800
DEFAULT_JITTER_RANGE: tuple[int, int] = (30, 300)
HEALTH_CHECK_INTERVAL_SECONDS: int = 30

# Kill switch
KILL_SWITCH_FILE: str = "STOP_BOT"

# Logging
LOG_MAX_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB
LOG_RETENTION_DAYS: int = 30

# Backup
BACKUP_RETENTION_DAYS: int = 7

# Auto-backup
AUTO_BACKUP_INTERVAL_SECONDS: int = 24 * 3600  # 24 hours
AUTO_BACKUP_DIR: str = "backups"

# Log monitoring
LOG_DIR_WARNING_SIZE_BYTES: int = 500 * 1024 * 1024  # 500 MB

# SSL
SSL_CERT_DIR: str = "certs"
SSL_CERT_VALIDITY_DAYS: int = 365

# Content quality
MIN_COMMENT_LENGTH: int = 20
DEFAULT_KOREAN_RATIO_THRESHOLD: float = 0.7

# ── Security: Authentication ──────────────────────────────────────────
PASSWORD_MIN_LENGTH: int = 12
PASSWORD_MAX_LENGTH: int = 128
DEFAULT_MAX_SESSION_COUNT: int = 10
SESSION_CLEANUP_INTERVAL_SECONDS: int = 300  # 5 minutes

# ── Security: CSRF ────────────────────────────────────────────────────
CSRF_TOKEN_BYTES: int = 32

# ── Security: CORS ────────────────────────────────────────────────────
DEFAULT_CORS_ORIGINS: list[str] = ["http://localhost:5173"]

# ── Security: Rate Limiting ───────────────────────────────────────────
DEFAULT_API_RATE_LIMIT: int = 100         # requests per minute
DEFAULT_LOGIN_RATE_LIMIT: int = 10        # requests per minute
RATE_LIMIT_WINDOW_SECONDS: int = 60

# ── Security: WebSocket ──────────────────────────────────────────────
WS_TICKET_EXPIRY_SECONDS: int = 30
MAX_WS_MESSAGE_BYTES: int = 8192          # 8 KB
MAX_WS_AUDIO_CHUNK_BYTES: int = 1_048_576 # 1 MB
MAX_WS_CONNECTIONS_PER_USER: int = 5

# ── Security: Input Validation ───────────────────────────────────────
DEFAULT_MAX_MESSAGE_LENGTH: int = 4096
MAX_REGEX_PATTERN_LENGTH: int = 200
MAX_LLM_INPUT_LENGTH: int = 32_000

# ── Security: Backup ─────────────────────────────────────────────────
BACKUP_ALLOWED_TABLES: frozenset[str] = frozenset(
    {"activities", "notification_log", "collected_info", "settings_history", "good_examples"}
)

# ── Security: Network (SSRF prevention) ──────────────────────────────
TRUSTED_INTERNAL_NETWORKS: tuple[str, ...] = (
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
)

# ── Autonomous features: Mission ────────────────────────────────────
MISSION_WARMUP_DEFAULT: int = 3
MISSION_RESPONSE_CHECK_INTERVAL_SECONDS: int = 300
MISSION_MAX_COLLECTING_HOURS: int = 48

# ── Autonomous features: Activity mixing ────────────────────────────
ACTIVITY_WEIGHT_COMMENT: float = 0.5
ACTIVITY_WEIGHT_UPVOTE: float = 0.3
ACTIVITY_WEIGHT_POST: float = 0.1
ACTIVITY_WEIGHT_SKIP: float = 0.1

# ── Embedding / Vector Memory ─────────────────────────────────────
EMBEDDING_DEFAULT_MODEL: str = "nomic-embed-text"
EMBEDDING_DEFAULT_DIMENSIONS: int = 768
EMBEDDING_SIMILARITY_THRESHOLD: float = 0.3
EMBEDDING_DEDUP_THRESHOLD: float = 0.95
EMBEDDING_CANDIDATE_FETCH_LIMIT: int = 100

# ── Auto Capture ──────────────────────────────────────────────────
AUTO_CAPTURE_MAX_PER_INTERACTION: int = 3
AUTO_CAPTURE_MIN_TEXT_LENGTH: int = 10
AUTO_CAPTURE_MAX_TEXT_LENGTH: int = 500
