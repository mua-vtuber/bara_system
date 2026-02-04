from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel as PydanticBaseModel

from app.api.dependencies import (
    get_auth_service,
    get_config,
    get_llm_service,
    get_platform_registry,
    get_settings_repo,
)
from app.core.config import Config
from app.core.logging import get_logger
from app.platforms.registry import PlatformRegistry
from app.repositories.settings import SettingsRepository
from app.services.auth import AuthService
from app.services.llm import LLMService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/setup", tags=["setup"])

# ------------------------------------------------------------------
# Request / Response Models
# ------------------------------------------------------------------


class SetupStatusResponse(PydanticBaseModel):
    completed: bool
    current_step: int
    steps: list[str]


class SystemCheckResult(PydanticBaseModel):
    name: str
    passed: bool
    message: str


class SystemCheckResponse(PydanticBaseModel):
    checks: list[SystemCheckResult]


class ModelInfo(PydanticBaseModel):
    name: str
    size: int | None = None
    modified_at: str | None = None


class ModelsResponse(PydanticBaseModel):
    models: list[ModelInfo]


class ModelSelectRequest(PydanticBaseModel):
    model: str


class BotConfigRequest(PydanticBaseModel):
    name: str
    owner_name: str
    wake_words: list[str]


class PlatformCredentials(PydanticBaseModel):
    enabled: bool
    api_key: str = ""


class PlatformsConfigRequest(PydanticBaseModel):
    moltbook: PlatformCredentials
    botmadang: PlatformCredentials


class PlatformRegisterRequest(PydanticBaseModel):
    platform: str  # "moltbook" or "botmadang"
    description: str = ""


class BehaviorConfigRequest(PydanticBaseModel):
    auto_mode: bool
    approval_mode: bool
    interest_keywords: list[str]
    monitoring_interval_minutes: int


class VoiceConfigRequest(PydanticBaseModel):
    enabled: bool
    wake_word_engine: str
    stt_model: str


class SetupCompleteResponse(PydanticBaseModel):
    success: bool
    message: str


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status(
    auth_service: AuthService = Depends(get_auth_service),
    config: Config = Depends(get_config),
) -> SetupStatusResponse:
    """Get current setup wizard progress."""
    steps = [
        "비밀번호 설정",
        "시스템 확인",
        "모델 선택",
        "봇 설정",
        "플랫폼 연동",
        "행동 설정",
        "음성 설정",
        "설정 완료",
    ]

    # Determine current step based on what's configured
    current_step = 0
    completed = False

    # Step 1: Password
    if not auth_service.is_setup_complete():
        current_step = 1
    # Step 2-3: Model selection
    elif config.bot.model == "your_ollama_model":
        current_step = 3
    # Step 4: Bot config
    elif config.bot.name == "YourBotName":
        current_step = 4
    # Step 5-7: Optional steps, mark as completed
    else:
        current_step = 8
        completed = True

    return SetupStatusResponse(
        completed=completed,
        current_step=current_step,
        steps=steps,
    )


@router.get("/system-check", response_model=SystemCheckResponse)
async def system_check(
    llm_service: LLMService = Depends(get_llm_service),
) -> SystemCheckResponse:
    """Perform system health checks."""
    checks: list[SystemCheckResult] = []

    # 1. Ollama connection
    ollama_ok = await llm_service.check_health()
    checks.append(
        SystemCheckResult(
            name="Ollama 연결",
            passed=ollama_ok,
            message="Ollama 서버가 정상적으로 실행 중입니다." if ollama_ok else "Ollama 서버에 연결할 수 없습니다.",
        )
    )

    # 2. Python version
    python_version = sys.version_info
    python_ok = python_version >= (3, 10)
    checks.append(
        SystemCheckResult(
            name="Python 버전",
            passed=python_ok,
            message=f"Python {python_version.major}.{python_version.minor}.{python_version.micro}"
            + (" (권장 버전)" if python_ok else " (Python 3.10+ 필요)"),
        )
    )

    # 3. Disk space
    try:
        total, used, free = shutil.disk_usage(".")
        free_gb = free / (1024**3)
        disk_ok = free_gb >= 1.0
        checks.append(
            SystemCheckResult(
                name="디스크 여유 공간",
                passed=disk_ok,
                message=f"{free_gb:.1f}GB 사용 가능" + (" (충분함)" if disk_ok else " (1GB 이상 필요)"),
            )
        )
    except Exception as exc:
        checks.append(
            SystemCheckResult(
                name="디스크 여유 공간",
                passed=False,
                message="확인 실패. 서버 로그를 확인하세요.",
            )
        )

    return SystemCheckResponse(checks=checks)


@router.get("/models", response_model=ModelsResponse)
async def get_models(
    llm_service: LLMService = Depends(get_llm_service),
) -> ModelsResponse:
    """Get available Ollama models."""
    try:
        models_data = await llm_service.get_available_models()
        models = [
            ModelInfo(
                name=m.get("name", ""),
                size=m.get("size"),
                modified_at=m.get("modified_at"),
            )
            for m in models_data
        ]
        return ModelsResponse(models=models)
    except Exception as exc:
        logger.error("Failed to fetch models: %s", exc)
        return ModelsResponse(models=[])


@router.post("/model")
async def select_model(
    body: ModelSelectRequest,
    request: Request,
    config: Config = Depends(get_config),
    auth_service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    """Select the LLM model to use."""
    if auth_service.is_setup_complete():
        return JSONResponse(
            status_code=403,
            content={"success": False, "message": "Setup already completed. Use settings API."},
        )
    try:
        # Update config in memory
        config.bot.model = body.model

        # Persist to config.json
        await _save_config_to_file(config)

        logger.info("Model selected: %s", body.model)
        return JSONResponse(content={"success": True, "message": "모델이 선택되었습니다."})
    except Exception as exc:
        logger.error("Failed to save model selection: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "모델 선택 실패. 서버 로그를 확인하세요."},
        )


@router.post("/bot")
async def configure_bot(
    body: BotConfigRequest,
    request: Request,
    config: Config = Depends(get_config),
    auth_service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    """Configure bot name and settings."""
    if auth_service.is_setup_complete():
        return JSONResponse(
            status_code=403,
            content={"success": False, "message": "Setup already completed. Use settings API."},
        )
    try:
        config.bot.name = body.name
        config.bot.owner_name = body.owner_name
        config.bot.wake_words = body.wake_words

        await _save_config_to_file(config)

        logger.info("Bot configured: name=%s", body.name)
        return JSONResponse(content={"success": True, "message": "봇 설정이 저장되었습니다."})
    except Exception as exc:
        logger.error("Failed to save bot config: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "봇 설정 실패. 서버 로그를 확인하세요."},
        )


@router.post("/platforms/register")
async def register_on_platform(
    body: PlatformRegisterRequest,
    request: Request,
    config: Config = Depends(get_config),
    platform_registry: PlatformRegistry = Depends(get_platform_registry),
) -> JSONResponse:
    """Register a new bot on a platform and return the API key."""
    if body.platform not in ("moltbook", "botmadang"):
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "지원하지 않는 플랫폼입니다."},
        )

    bot_name = config.bot.name
    if not bot_name or bot_name == "YourBotName":
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "먼저 봇 이름을 설정해주세요."},
        )

    try:
        adapter = platform_registry.get_adapter(body.platform)
        result = await adapter.register_agent(bot_name, body.description)

        if not result.success:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": result.error or "가입에 실패했습니다."},
            )

        # Save API key to .env
        if result.api_key:
            env_key = f"{body.platform.upper()}_API_KEY"
            _persist_env_values({env_key: result.api_key})
            # Update in-memory
            if body.platform == "moltbook":
                config.env.moltbook_api_key = result.api_key
                config.platforms.moltbook.enabled = True
            else:
                config.env.botmadang_api_key = result.api_key
                config.platforms.botmadang.enabled = True
            await _save_config_to_file(config)

        logger.info("Registered bot on %s: %s", body.platform, bot_name)
        return JSONResponse(
            content={
                "success": True,
                "message": f"{body.platform}에 가입되었습니다.",
                "api_key": result.api_key or "",
                "claim_url": result.claim_url or "",
                "verification_code": result.verification_code or "",
            }
        )
    except Exception as exc:
        logger.error("Registration failed on %s: %s", body.platform, exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"가입 실패: {exc}"},
        )


@router.post("/platforms")
async def configure_platforms(
    body: PlatformsConfigRequest,
    request: Request,
    config: Config = Depends(get_config),
    platform_registry: PlatformRegistry = Depends(get_platform_registry),
    auth_service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    """Configure platform integrations."""
    if auth_service.is_setup_complete():
        return JSONResponse(
            status_code=403,
            content={"success": False, "message": "Setup already completed. Use settings API."},
        )
    try:
        # Update platform configs
        config.platforms.moltbook.enabled = body.moltbook.enabled
        config.platforms.botmadang.enabled = body.botmadang.enabled

        # Persist API keys to .env
        env_updates: dict[str, str] = {}
        if body.moltbook.api_key:
            env_updates["MOLTBOOK_API_KEY"] = body.moltbook.api_key
        if body.botmadang.api_key:
            env_updates["BOTMADANG_API_KEY"] = body.botmadang.api_key

        if env_updates:
            _persist_env_values(env_updates)
            # Update in-memory env
            if body.moltbook.api_key:
                config.env.moltbook_api_key = body.moltbook.api_key
            if body.botmadang.api_key:
                config.env.botmadang_api_key = body.botmadang.api_key

        # Validate credentials if enabled
        validation_results: dict[str, bool] = {}
        if body.moltbook.enabled and body.moltbook.api_key:
            try:
                adapter = platform_registry.get_adapter("moltbook")
                validation_results["moltbook"] = await adapter.validate_credentials()
            except Exception as exc:
                logger.warning("Moltbook validation failed: %s", exc)
                validation_results["moltbook"] = False

        if body.botmadang.enabled and body.botmadang.api_key:
            try:
                adapter = platform_registry.get_adapter("botmadang")
                validation_results["botmadang"] = await adapter.validate_credentials()
            except Exception as exc:
                logger.warning("Botmadang validation failed: %s", exc)
                validation_results["botmadang"] = False

        await _save_config_to_file(config)

        logger.info("Platform config saved: %s", validation_results)
        return JSONResponse(
            content={
                "success": True,
                "message": "플랫폼 설정이 저장되었습니다.",
                "validation": validation_results,
            }
        )
    except Exception as exc:
        logger.error("Failed to save platform config: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "플랫폼 설정 실패. 서버 로그를 확인하세요."},
        )


@router.post("/behavior")
async def configure_behavior(
    body: BehaviorConfigRequest,
    request: Request,
    config: Config = Depends(get_config),
    auth_service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    """Configure bot behavior settings."""
    if auth_service.is_setup_complete():
        return JSONResponse(
            status_code=403,
            content={"success": False, "message": "Setup already completed. Use settings API."},
        )
    try:
        config.behavior.auto_mode = body.auto_mode
        config.behavior.approval_mode = body.approval_mode
        config.behavior.interest_keywords = body.interest_keywords
        config.behavior.monitoring_interval_minutes = body.monitoring_interval_minutes

        await _save_config_to_file(config)

        logger.info("Behavior config saved")
        return JSONResponse(content={"success": True, "message": "행동 설정이 저장되었습니다."})
    except Exception as exc:
        logger.error("Failed to save behavior config: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "행동 설정 실패. 서버 로그를 확인하세요."},
        )


@router.post("/voice")
async def configure_voice(
    body: VoiceConfigRequest,
    request: Request,
    config: Config = Depends(get_config),
    auth_service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    """Configure voice/audio settings."""
    if auth_service.is_setup_complete():
        return JSONResponse(
            status_code=403,
            content={"success": False, "message": "Setup already completed. Use settings API."},
        )
    try:
        config.voice.enabled = body.enabled
        config.voice.wake_word_engine = body.wake_word_engine
        config.voice.stt_model = body.stt_model

        await _save_config_to_file(config)

        logger.info("Voice config saved")
        return JSONResponse(content={"success": True, "message": "음성 설정이 저장되었습니다."})
    except Exception as exc:
        logger.error("Failed to save voice config: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "음성 설정 실패. 서버 로그를 확인하세요."},
        )


@router.post("/complete", response_model=SetupCompleteResponse)
async def complete_setup(
    request: Request,
    config: Config = Depends(get_config),
    settings_repo: SettingsRepository = Depends(get_settings_repo),
    auth_service: AuthService = Depends(get_auth_service),
) -> SetupCompleteResponse:
    """Finalize setup wizard."""
    if auth_service.is_setup_complete():
        return SetupCompleteResponse(
            success=False,
            message="Setup already completed. Use settings API.",
        )
    try:
        # Save final config to file
        await _save_config_to_file(config)

        # Save snapshot to settings_history
        config_json = json.dumps(config.to_dict(), ensure_ascii=False, indent=2)
        await settings_repo.save_snapshot(config_json)

        logger.info("Setup wizard completed successfully")
        return SetupCompleteResponse(
            success=True,
            message="설정이 완료되었습니다. 이제 bara_system을 사용할 수 있습니다.",
        )
    except Exception as exc:
        logger.error("Failed to complete setup: %s", exc)
        return SetupCompleteResponse(
            success=False,
            message="설정 완료 실패. 서버 로그를 확인하세요.",
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


async def _save_config_to_file(config: Config) -> None:
    """Save config object to config.json."""
    config_path = config.config_path or Path("config.json")
    config_dict = config.to_dict()

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_dict, f, ensure_ascii=False, indent=2)


def _persist_env_values(updates: dict[str, str]) -> None:
    """Write or update key-value pairs in .env file."""
    # Sanitize values to prevent newline/shell injection.
    updates = {
        k: v.replace("\n", "").replace("\r", "").replace("$", "").replace("`", "").replace("|", "").replace(";", "").replace(">", "").replace("<", "")
        for k, v in updates.items()
    }

    env_path = Path(".env")
    lines: list[str] = []
    found_keys: set[str] = set()

    if env_path.exists():
        raw = env_path.read_text(encoding="utf-8")
        for line in raw.splitlines():
            # Check if this line sets one of our update keys
            updated = False
            for key, value in updates.items():
                if line.startswith(f"{key}="):
                    lines.append(f"{key}={value}")
                    found_keys.add(key)
                    updated = True
                    break
            if not updated:
                lines.append(line)

    # Append any keys that weren't found
    for key, value in updates.items():
        if key not in found_keys:
            lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
