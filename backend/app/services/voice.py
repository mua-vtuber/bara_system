"""Voice service for orchestrating wake word detection and speech-to-text."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.models.events import VoiceCommandEvent

if TYPE_CHECKING:
    from app.core.config import Config
    from app.core.events import EventBus

logger = get_logger(__name__)

# Optional imports
_VOICE_AVAILABLE = False
try:
    from app.voice.wake_word import WakeWordEngine
    from app.voice.whisper import WhisperEngine

    _VOICE_AVAILABLE = True
except ImportError:
    logger.debug("Voice subsystem not available (optional dependencies missing)")
    WakeWordEngine = None  # type: ignore[assignment, misc]
    WhisperEngine = None  # type: ignore[assignment, misc]


class VoiceService:
    """Voice service coordinating wake word detection and STT.

    State machine:
    1. IDLE: Waiting for wake word
    2. LISTENING: Wake word detected, collecting audio for STT
    3. TRANSCRIBING: Processing collected audio

    VRAM optimization: Whisper model is loaded only when needed
    and unloaded immediately after transcription.
    """

    def __init__(self, config: Config, event_bus: EventBus) -> None:
        self._config = config
        self._event_bus = event_bus
        self._enabled = config.voice.enabled

        self._wake_word_engine: WakeWordEngine | None = None
        self._whisper_engine: WhisperEngine | None = None

        self._listening = False  # True when actively collecting audio for STT
        self._audio_buffer = bytearray()
        self._silence_timeout = 2.0  # seconds of silence before transcribing
        self._last_audio_time = 0.0

        # Check if voice subsystem is available
        if self._enabled and not _VOICE_AVAILABLE:
            logger.warning(
                "Voice is enabled in config but dependencies are not installed. "
                "Install with: pip install openai-whisper torch numpy"
            )
            self._enabled = False

        # Initialize engines if available
        if self._enabled and _VOICE_AVAILABLE:
            self._wake_word_engine = WakeWordEngine(config)
            self._whisper_engine = WhisperEngine(config)

    async def start(self) -> None:
        """Start the voice pipeline."""
        if not self._enabled:
            logger.info("Voice service is disabled")
            return

        if self._wake_word_engine is None:
            logger.warning("Cannot start voice service: wake word engine not available")
            return

        try:
            await self._wake_word_engine.start()
            logger.info("Voice service started (wake word detection active)")
        except Exception as exc:
            logger.exception("Failed to start voice service: %s", exc)

    async def stop(self) -> None:
        """Stop the voice pipeline and free resources."""
        if not self._enabled:
            return

        # Unload Whisper model to free VRAM
        if self._whisper_engine is not None:
            try:
                await self._whisper_engine.unload_model()
            except Exception as exc:
                logger.exception("Error unloading Whisper: %s", exc)

        # Stop wake word engine
        if self._wake_word_engine is not None:
            try:
                await self._wake_word_engine.stop()
            except Exception as exc:
                logger.exception("Error stopping wake word engine: %s", exc)

        logger.info("Voice service stopped")

    async def process_audio(self, chunk: bytes) -> str | None:
        """Process incoming audio chunk.

        State transitions:
        - IDLE + wake word detected → LISTENING (start collecting)
        - LISTENING + silence timeout → TRANSCRIBING → IDLE
        - LISTENING + audio → add to buffer

        Args:
            chunk: Raw PCM audio bytes (16kHz, 16-bit, mono)

        Returns:
            Transcribed text if transcription occurred, None otherwise
        """
        if not self._enabled:
            return None

        current_time = time.time()

        # State: IDLE - checking for wake word
        if not self._listening:
            if self._wake_word_engine is None:
                return None

            try:
                wake_word_detected = await self._wake_word_engine.process_audio_chunk(
                    chunk
                )
                if wake_word_detected:
                    logger.info("Wake word detected, starting audio collection")
                    self._listening = True
                    self._audio_buffer = bytearray()
                    self._last_audio_time = current_time

                    # Load Whisper model in background (will be ready when needed)
                    if self._whisper_engine is not None:
                        asyncio.create_task(self._whisper_engine.load_model())

            except Exception as exc:
                logger.exception("Error processing wake word: %s", exc)

            return None

        # State: LISTENING - collecting audio for transcription
        self._audio_buffer.extend(chunk)
        self._last_audio_time = current_time

        # Check for silence timeout (simple heuristic: no audio for N seconds)
        # In production, use VAD (Voice Activity Detection) for better results
        if len(self._audio_buffer) > 0:
            # Check if we have enough audio and silence timeout expired
            time_since_last_audio = current_time - self._last_audio_time

            # For now, trigger transcription after collecting some audio
            # Real implementation should use VAD or explicit end-of-speech signal
            if len(self._audio_buffer) > 160000:  # ~5 seconds at 16kHz 16-bit mono
                return await self._finalize_transcription()

        return None

    async def finalize_listening(self) -> str | None:
        """Explicitly finalize listening and transcribe collected audio.

        This should be called when the WebSocket client signals end of speech.
        """
        if not self._listening:
            return None

        return await self._finalize_transcription()

    async def _finalize_transcription(self) -> str | None:
        """Transcribe collected audio and return to IDLE state."""
        if not self._listening or len(self._audio_buffer) == 0:
            self._listening = False
            return None

        logger.info(
            "Finalizing transcription (collected %d bytes)",
            len(self._audio_buffer),
        )

        try:
            if self._whisper_engine is None:
                logger.warning("Cannot transcribe: Whisper engine not available")
                self._listening = False
                return None

            # Transcribe
            audio_bytes = bytes(self._audio_buffer)
            text = await self._whisper_engine.transcribe(audio_bytes)

            # Emit event
            event = VoiceCommandEvent(transcript=text, confidence=1.0)
            await self._event_bus.publish(event)

            logger.info("Voice command transcribed: %s", text)

            # Cleanup: unload Whisper to free VRAM
            await self._whisper_engine.unload_model()

            # Reset state
            self._listening = False
            self._audio_buffer = bytearray()

            return text

        except Exception as exc:
            logger.exception("Transcription failed: %s", exc)
            self._listening = False
            self._audio_buffer = bytearray()
            return None

    @property
    def is_enabled(self) -> bool:
        """Return True if voice service is enabled."""
        return self._enabled

    @property
    def is_listening(self) -> bool:
        """Return True if actively collecting audio for transcription."""
        return self._listening
