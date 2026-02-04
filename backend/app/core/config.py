from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from app.core.constants import (
    DEFAULT_BUSY_TIMEOUT_MS,
    DEFAULT_CORS_ORIGINS,
    DEFAULT_JITTER_RANGE,
    DEFAULT_LOCKOUT_MINUTES,
    DEFAULT_MAX_LOGIN_ATTEMPTS,
    DEFAULT_MAX_MESSAGE_LENGTH,
    DEFAULT_MAX_SESSION_COUNT,
    DEFAULT_MONITORING_INTERVAL_MINUTES,
    DEFAULT_SESSION_TIMEOUT_HOURS,
    MIN_COMMENT_LENGTH,
    DEFAULT_KOREAN_RATIO_THRESHOLD,
)
from app.core.exceptions import ConfigError


class BotConfig(BaseModel):
    name: str = "YourBotName"
    model: str = "your_ollama_model"
    wake_words: list[str] = Field(default_factory=list)
    owner_name: str = "YourName"


class PlatformConfig(BaseModel):
    enabled: bool = False
    base_url: str = ""


class PlatformsConfig(BaseModel):
    moltbook: PlatformConfig = Field(default_factory=PlatformConfig)
    botmadang: PlatformConfig = Field(default_factory=PlatformConfig)


class CommentStrategyConfig(BaseModel):
    min_quality_length: int = MIN_COMMENT_LENGTH
    korean_ratio_threshold: float = DEFAULT_KOREAN_RATIO_THRESHOLD
    jitter_range_seconds: tuple[int, int] = DEFAULT_JITTER_RANGE


class DailyLimitsConfig(BaseModel):
    max_comments: int = 20
    max_posts: int = 3
    max_upvotes: int = 30


class TimeRange(BaseModel):
    start: int = 9
    end: int = 22


class ActiveHoursConfig(BaseModel):
    weekday: TimeRange = Field(default_factory=lambda: TimeRange(start=9, end=22))
    weekend: TimeRange = Field(default_factory=lambda: TimeRange(start=10, end=20))


class BehaviorConfig(BaseModel):
    auto_mode: bool = False
    approval_mode: bool = True
    monitoring_interval_minutes: int = DEFAULT_MONITORING_INTERVAL_MINUTES
    interest_keywords: list[str] = Field(default_factory=list)
    comment_strategy: CommentStrategyConfig = Field(
        default_factory=CommentStrategyConfig
    )
    daily_limits: DailyLimitsConfig = Field(default_factory=DailyLimitsConfig)
    active_hours: ActiveHoursConfig = Field(default_factory=ActiveHoursConfig)


class VoiceConfig(BaseModel):
    enabled: bool = False
    wake_word_engine: str = "openwakeword"
    stt_model: str = "base"
    language: str = "ko"
    audio_source: str = "browser"


class WebSecurityConfig(BaseModel):
    session_timeout_hours: int = DEFAULT_SESSION_TIMEOUT_HOURS
    max_login_attempts: int = DEFAULT_MAX_LOGIN_ATTEMPTS
    lockout_minutes: int = DEFAULT_LOCKOUT_MINUTES
    https_enabled: bool = True
    allowed_ips: list[str] = Field(default_factory=list)
    allow_all_local: bool = True
    trusted_proxies: list[str] = Field(default_factory=list)
    csrf_secret: str = ""
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS)
    )
    max_message_length: int = DEFAULT_MAX_MESSAGE_LENGTH
    max_session_count: int = DEFAULT_MAX_SESSION_COUNT


class SecurityConfig(BaseModel):
    blocked_keywords: list[str] = Field(default_factory=list)
    blocked_patterns: list[str] = Field(default_factory=list)


class UIConfig(BaseModel):
    theme: str = "light"
    language: str = "ko"


class PersonalityConfig(BaseModel):
    system_prompt: str = ""
    interests: list[str] = Field(default_factory=list)
    expertise: list[str] = Field(default_factory=list)
    style: str = "casual"
    traits: list[str] = Field(default_factory=list)
    backstory: str = ""


class EnvSettings(BaseSettings):
    """Loads secrets from .env file or environment variables."""

    moltbook_api_key: str = ""
    botmadang_api_key: str = ""
    web_ui_password_hash: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


class Config:
    """Application configuration loaded from config.json + .env.

    Implements singleton access via ``get_instance`` and supports runtime
    hot-reload of mutable sections with observer notifications.
    """

    _instance: Optional[Config] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(
        self,
        bot: BotConfig,
        platforms: PlatformsConfig,
        behavior: BehaviorConfig,
        voice: VoiceConfig,
        web_security: WebSecurityConfig,
        security: SecurityConfig,
        ui: UIConfig,
        personality: PersonalityConfig,
        env: EnvSettings,
        config_path: Optional[Path] = None,
    ) -> None:
        self.bot = bot
        self.platforms = platforms
        self.behavior = behavior
        self.voice = voice
        self.web_security = web_security
        self.security = security
        self.ui = ui
        self.personality = personality
        self.env = env
        self.config_path = config_path
        self._observers: list[Callable[[str, Any, Any], Any]] = []

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> Config:
        if cls._instance is None:
            raise ConfigError("Config has not been loaded. Call Config.from_file() first.")
        return cls._instance

    @classmethod
    def from_file(
        cls,
        config_path: Path | str = "config.json",
        env_path: Path | str = ".env",
    ) -> Config:
        config_path = Path(config_path)
        env_path = Path(env_path)

        load_dotenv(dotenv_path=env_path, override=True)
        env = EnvSettings()

        if not config_path.exists():
            raise ConfigError(f"Config file not found: {config_path}")

        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in {config_path}: {exc}") from exc

        try:
            instance = cls(
                bot=BotConfig(**raw.get("bot", {})),
                platforms=PlatformsConfig(**raw.get("platforms", {})),
                behavior=BehaviorConfig(**raw.get("behavior", {})),
                voice=VoiceConfig(**raw.get("voice", {})),
                web_security=WebSecurityConfig(**raw.get("web_security", {})),
                security=SecurityConfig(**raw.get("security", {})),
                ui=UIConfig(**raw.get("ui", {})),
                personality=PersonalityConfig(**raw.get("personality", {})),
                env=env,
                config_path=config_path,
            )
        except Exception as exc:
            raise ConfigError(f"Config validation failed: {exc}") from exc

        cls._instance = instance

        # Auto-generate CSRF secret if not configured
        if not instance.web_security.csrf_secret:
            import secrets as _secrets
            instance.web_security.csrf_secret = _secrets.token_hex(32)
            # Persist to config file so it survives restarts
            if instance.config_path and instance.config_path.exists():
                try:
                    raw_cfg = json.loads(
                        instance.config_path.read_text(encoding="utf-8")
                    )
                    raw_cfg.setdefault("web_security", {})[
                        "csrf_secret"
                    ] = instance.web_security.csrf_secret
                    instance.config_path.write_text(
                        json.dumps(raw_cfg, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    pass  # Non-fatal: secret is in memory regardless

        return instance

    # ------------------------------------------------------------------
    # Hot-reload support
    # ------------------------------------------------------------------

    def add_observer(self, callback: Callable[[str, Any, Any], Any]) -> None:
        self._observers.append(callback)

    def remove_observer(self, callback: Callable[[str, Any, Any], Any]) -> None:
        self._observers = [cb for cb in self._observers if cb is not callback]

    async def _notify_observers(self, section: str, old_value: Any, new_value: Any) -> None:
        for callback in self._observers:
            result = callback(section, old_value, new_value)
            if asyncio.iscoroutine(result):
                await result

    async def update_section(self, section: str, data: dict[str, Any]) -> None:
        async with self._lock:
            current = getattr(self, section, None)
            if current is None:
                raise ConfigError(f"Unknown config section: {section}")

            model_cls = type(current)
            old_value = current.model_copy()
            new_value = model_cls(**data)
            setattr(self, section, new_value)
            await self._notify_observers(section, old_value, new_value)

    async def reload_from_file(self) -> None:
        if self.config_path is None or not self.config_path.exists():
            raise ConfigError("Cannot reload: config file path is not set or file missing.")

        raw = json.loads(self.config_path.read_text(encoding="utf-8"))

        mutable_sections = ("behavior", "voice", "web_security", "security", "ui", "personality")
        for section in mutable_sections:
            if section in raw:
                await self.update_section(section, raw[section])

    def to_dict(self) -> dict[str, Any]:
        return {
            "bot": self.bot.model_dump(),
            "platforms": self.platforms.model_dump(),
            "behavior": self.behavior.model_dump(),
            "voice": self.voice.model_dump(),
            "web_security": self.web_security.model_dump(),
            "security": self.security.model_dump(),
            "ui": self.ui.model_dump(),
            "personality": self.personality.model_dump(),
        }

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    @property
    def db_path(self) -> str:
        return "bara_system.db"

    @property
    def busy_timeout_ms(self) -> int:
        return DEFAULT_BUSY_TIMEOUT_MS
