from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware import register_middleware
from app.api.routes.activities import router as activities_router
from app.api.routes.auth import router as auth_router
from app.api.routes.backup import router as backup_router
from app.api.routes.chat import router as chat_router
from app.api.routes.commands import router as commands_router
from app.api.routes.emergency import router as emergency_router
from app.api.routes.info import router as info_router
from app.api.routes.missions import router as missions_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.platforms import router as platforms_router
from app.api.routes.settings import router as settings_router
from app.api.routes.setup_wizard import router as setup_wizard_router
from app.api.websocket.audio import websocket_audio
from app.api.websocket.chat import websocket_chat
from app.api.websocket.manager import WebSocketManager
from app.api.websocket.status import websocket_status
from app.core.config import Config
from app.core.database import Database
from app.core.events import EventBus
from app.core.http_client import HttpClient
from app.core.logging import get_logger, setup_logging
from app.core.rate_limiter import RateLimiterFactory
from app.core.security import SecurityFilter
from app.core.task_queue import TaskQueue
from app.platforms.registry import PlatformRegistry
from app.repositories.activity import ActivityRepository
from app.repositories.notification import NotificationRepository
from app.services.auth import AuthService
from app.services.backup import BackupService
from app.services.feed_monitor import FeedMonitor
from app.services.health import HealthMonitor
from app.services.kill_switch import KillSwitch
from app.services.llm import LLMService
from app.services.notifications import NotificationService
from app.services.scheduler import Scheduler
from app.services.strategy import DefaultBehaviorStrategy, StrategyEngine
from app.services.translation import TranslationService
from app.services.voice import VoiceService
from app.models.events import CommentPostedEvent, NewPostDiscoveredEvent
from app.repositories.collected_info import CollectedInfoRepository
from app.repositories.memory import BotMemoryRepository
from app.repositories.mission import MissionRepository
from app.services.activity_mixer import ActivityMixer
from app.services.memory import MemoryService
from app.services.mission import MissionService
from app.services.prompt_builder import PromptBuilder
from app.services.response_collector import ResponseCollector

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle for the FastAPI application."""

    # -- Startup -------------------------------------------------------------
    setup_logging()
    logger.info("Starting bara_system backend")

    config = Config.from_file()
    db = await Database.initialize(config.db_path)
    await db.run_migrations()

    auth_service = AuthService(config, db)
    security_filter = SecurityFilter(config)

    # -- HTTP client and platform infrastructure ------------------------------
    http_client = HttpClient(config)
    await http_client.start()

    # -- LLM service -----------------------------------------------------------
    llm_service = LLMService(config, http_client)

    rate_limiters = RateLimiterFactory.create_all(config)

    platform_registry = PlatformRegistry(
        config=config,
        http_client=http_client,
        rate_limiters=rate_limiters,
        security_filter=security_filter,
    )
    platform_registry.initialize()

    # -- Strategy engine and translation service --------------------------------
    behavior_strategy = DefaultBehaviorStrategy(config)
    strategy_engine = StrategyEngine(
        strategy=behavior_strategy,
        llm_service=llm_service,
        config=config,
        security_filter=security_filter,
    )
    translation_service = TranslationService(llm_service)

    # -- Event system and WebSocket manager ------------------------------------
    event_bus = EventBus()
    ws_manager = WebSocketManager(auth_service)

    # -- Task queue ------------------------------------------------------------
    task_queue = TaskQueue(rate_limiters)

    # -- Repositories for automation services ----------------------------------
    activity_repo = ActivityRepository(db)
    notification_repo = NotificationRepository(db)

    # -- Automation services ---------------------------------------------------
    feed_monitor = FeedMonitor(
        platform_registry=platform_registry,
        config=config,
        strategy_engine=strategy_engine,
        activity_repo=activity_repo,
        event_bus=event_bus,
        task_queue=task_queue,
    )

    notification_service = NotificationService(
        platform_registry=platform_registry,
        notification_repo=notification_repo,
        activity_repo=activity_repo,
        strategy_engine=strategy_engine,
        event_bus=event_bus,
        task_queue=task_queue,
    )

    backup_service = BackupService(db=db, config=config)

    scheduler = Scheduler(
        config=config,
        feed_monitor=feed_monitor,
        notification_service=notification_service,
        event_bus=event_bus,
        backup_service=backup_service,
    )

    kill_switch = KillSwitch(
        scheduler=scheduler,
        task_queue=task_queue,
        event_bus=event_bus,
        config=config,
    )

    health_monitor = HealthMonitor(
        config=config,
        llm_service=llm_service,
        db=db,
        platform_registry=platform_registry,
    )

    # -- Autonomous bot services -----------------------------------------------
    collected_info_repo = CollectedInfoRepository(db)
    memory_repo = BotMemoryRepository(db)
    mission_repo = MissionRepository(db)

    memory_service = MemoryService(
        memory_repo=memory_repo,
        collected_info_repo=collected_info_repo,
        config=config,
    )

    prompt_builder = PromptBuilder(
        config=config,
        security_filter=security_filter,
    )

    mission_service = MissionService(
        mission_repo=mission_repo,
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        memory_service=memory_service,
        event_bus=event_bus,
        config=config,
    )

    activity_mixer = ActivityMixer(config=config)

    response_collector = ResponseCollector(
        mission_service=mission_service,
        memory_service=memory_service,
        platform_registry=platform_registry,
        event_bus=event_bus,
        config=config,
    )

    # Inject prompt builder into strategy engine
    strategy_engine.set_prompt_builder(prompt_builder)

    # Inject services into feed monitor
    feed_monitor.set_memory_service(memory_service)
    feed_monitor.set_activity_mixer(activity_mixer)
    feed_monitor.set_mission_service(mission_service)

    # Subscribe memory service to events
    await event_bus.subscribe(NewPostDiscoveredEvent, memory_service.on_new_post)
    await event_bus.subscribe(CommentPostedEvent, memory_service.on_comment_posted)

    # -- Voice service (optional, only if enabled) -----------------------------
    voice_service = VoiceService(config=config, event_bus=event_bus)
    if voice_service.is_enabled:
        await voice_service.start()
        logger.info("Voice service started")
    else:
        logger.info("Voice service disabled or unavailable")

    # -- Bind all to app.state -------------------------------------------------
    app.state.config = config
    app.state.db = db
    app.state.auth_service = auth_service
    app.state.security_filter = security_filter
    app.state.http_client = http_client
    app.state.llm_service = llm_service
    app.state.rate_limiters = rate_limiters
    app.state.platform_registry = platform_registry
    app.state.strategy_engine = strategy_engine
    app.state.translation_service = translation_service
    app.state.event_bus = event_bus
    app.state.ws_manager = ws_manager
    app.state.task_queue = task_queue
    app.state.feed_monitor = feed_monitor
    app.state.notification_service = notification_service
    app.state.scheduler = scheduler
    app.state.kill_switch = kill_switch
    app.state.health_monitor = health_monitor
    app.state.backup_service = backup_service
    app.state.voice_service = voice_service
    app.state.memory_service = memory_service
    app.state.mission_service = mission_service
    app.state.prompt_builder = prompt_builder
    app.state.activity_mixer = activity_mixer
    app.state.response_collector = response_collector

    # -- Start automation (task queue + scheduler) -----------------------------
    await task_queue.start()
    if config.behavior.auto_mode:
        await scheduler.start()
        # Register autonomous bot tasks
        from app.core.constants import MISSION_RESPONSE_CHECK_INTERVAL_SECONDS
        await scheduler.add_task(
            "response_collector",
            response_collector.check_all_active_posts,
            MISSION_RESPONSE_CHECK_INTERVAL_SECONDS,
        )
        await scheduler.add_task(
            "mission_advance",
            mission_service.advance_all,
            600,
        )
        logger.info("Auto-mode enabled: scheduler started")
    else:
        logger.info("Auto-mode disabled: scheduler idle (start via API)")

    logger.info("Startup complete")
    yield

    # -- Shutdown ------------------------------------------------------------
    logger.info("Shutting down bara_system backend")
    await scheduler.stop()
    await task_queue.stop()
    await voice_service.stop()
    await event_bus.clear()
    await http_client.close()
    await db.close()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="bara_system",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS (outermost middleware -- added first so it wraps everything)
    # Load CORS origins early (before lifespan) from config file.
    _cors_origins = ["http://localhost:5173"]
    try:
        import json as _json
        _cfg_path = Path("config.json")
        if _cfg_path.exists():
            _raw = _json.loads(_cfg_path.read_text(encoding="utf-8"))
            _cors_origins = (
                _raw.get("web_security", {}).get("cors_allowed_origins")
                or _cors_origins
            )
    except Exception:
        pass

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    )

    # Custom middleware (all resolve dependencies lazily from app.state)
    register_middleware(app)

    # -- Health endpoint (no auth required) ----------------------------------

    @app.get("/api/health")
    async def health_check() -> JSONResponse:
        return JSONResponse(
            content={
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    # -- Routers -------------------------------------------------------------
    app.include_router(auth_router)
    app.include_router(setup_wizard_router)
    app.include_router(chat_router)
    app.include_router(platforms_router)
    app.include_router(activities_router)
    app.include_router(notifications_router)
    app.include_router(settings_router)
    app.include_router(emergency_router)
    app.include_router(commands_router)
    app.include_router(info_router)
    app.include_router(backup_router)
    app.include_router(missions_router)

    # -- WebSocket endpoints --------------------------------------------------
    app.websocket("/ws/chat")(websocket_chat)
    app.websocket("/ws/status")(websocket_status)
    app.websocket("/ws/audio")(websocket_audio)

    return app


app = create_app()
