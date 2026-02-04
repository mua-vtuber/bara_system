from __future__ import annotations

from fastapi import Request
from starlette.exceptions import HTTPException

from app.core.config import Config
from app.core.database import Database
from app.core.security import SecurityFilter
from app.models.auth import Session
from app.platforms.registry import PlatformRegistry
from app.repositories.activity import ActivityRepository
from app.repositories.collected_info import CollectedInfoRepository
from app.repositories.conversation import ConversationRepository
from app.repositories.notification import NotificationRepository
from app.repositories.settings import SettingsRepository
from app.api.websocket.manager import WebSocketManager
from app.core.events import EventBus
from app.services.auth import AuthService
from app.services.backup import BackupService
from app.services.feed_monitor import FeedMonitor
from app.services.health import HealthMonitor
from app.services.kill_switch import KillSwitch
from app.services.llm import LLMService
from app.services.notifications import NotificationService
from app.services.scheduler import Scheduler
from app.services.strategy import StrategyEngine
from app.services.translation import TranslationService


def get_config(request: Request) -> Config:
    """Provide the application ``Config`` instance."""
    return request.app.state.config


def get_db(request: Request) -> Database:
    """Provide the ``Database`` singleton."""
    return request.app.state.db


def get_auth_service(request: Request) -> AuthService:
    """Provide the ``AuthService`` instance."""
    return request.app.state.auth_service


def get_current_session(request: Request) -> Session:
    """Return the authenticated ``Session`` or raise 401.

    Relies on ``AuthMiddleware`` having populated ``request.state.session``.
    """
    session: Session | None = getattr(request.state, "session", None)
    if session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session


def get_security_filter(request: Request) -> SecurityFilter:
    """Provide the ``SecurityFilter`` instance."""
    return request.app.state.security_filter


# ------------------------------------------------------------------
# Repository dependencies
# ------------------------------------------------------------------


def get_conversation_repo(request: Request) -> ConversationRepository:
    """Provide a ``ConversationRepository`` backed by the app DB."""
    return ConversationRepository(request.app.state.db)


def get_activity_repo(request: Request) -> ActivityRepository:
    """Provide an ``ActivityRepository`` backed by the app DB."""
    return ActivityRepository(request.app.state.db)


def get_notification_repo(request: Request) -> NotificationRepository:
    """Provide a ``NotificationRepository`` backed by the app DB."""
    return NotificationRepository(request.app.state.db)


def get_collected_info_repo(request: Request) -> CollectedInfoRepository:
    """Provide a ``CollectedInfoRepository`` backed by the app DB."""
    return CollectedInfoRepository(request.app.state.db)


def get_settings_repo(request: Request) -> SettingsRepository:
    """Provide a ``SettingsRepository`` backed by the app DB."""
    return SettingsRepository(request.app.state.db)


# ------------------------------------------------------------------
# Platform dependencies
# ------------------------------------------------------------------


def get_platform_registry(request: Request) -> PlatformRegistry:
    """Provide the ``PlatformRegistry`` instance."""
    return request.app.state.platform_registry


# ------------------------------------------------------------------
# Service dependencies
# ------------------------------------------------------------------


def get_llm_service(request: Request) -> LLMService:
    """Provide the ``LLMService`` instance."""
    return request.app.state.llm_service


def get_strategy_engine(request: Request) -> StrategyEngine:
    """Provide the ``StrategyEngine`` instance."""
    return request.app.state.strategy_engine


def get_translation_service(request: Request) -> TranslationService:
    """Provide the ``TranslationService`` instance."""
    return request.app.state.translation_service


# ------------------------------------------------------------------
# Event / WebSocket dependencies
# ------------------------------------------------------------------


def get_event_bus(request: Request) -> EventBus:
    """Provide the ``EventBus`` singleton."""
    return request.app.state.event_bus


def get_ws_manager(request: Request) -> WebSocketManager:
    """Provide the ``WebSocketManager`` singleton."""
    return request.app.state.ws_manager


# ------------------------------------------------------------------
# Automation service dependencies
# ------------------------------------------------------------------


def get_feed_monitor(request: Request) -> FeedMonitor:
    """Provide the ``FeedMonitor`` instance."""
    return request.app.state.feed_monitor


def get_notification_service(request: Request) -> NotificationService:
    """Provide the ``NotificationService`` instance."""
    return request.app.state.notification_service


def get_scheduler(request: Request) -> Scheduler:
    """Provide the ``Scheduler`` instance."""
    return request.app.state.scheduler


def get_kill_switch(request: Request) -> KillSwitch:
    """Provide the ``KillSwitch`` instance."""
    return request.app.state.kill_switch


def get_health_monitor(request: Request) -> HealthMonitor:
    """Provide the ``HealthMonitor`` instance."""
    return request.app.state.health_monitor


def get_backup_service(request: Request) -> BackupService:
    """Provide the ``BackupService`` instance."""
    return request.app.state.backup_service


def get_mission_service(request: Request):
    """Provide the ``MissionService`` instance."""
    return request.app.state.mission_service


def get_memory_service(request: Request):
    """Provide the ``MemoryService`` instance."""
    return request.app.state.memory_service
