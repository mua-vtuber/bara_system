"""Wake word detection engine with support for OpenWakeWord and Porcupine."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.config import Config

logger = get_logger(__name__)

# Optional dependency detection
_OPENWAKEWORD_AVAILABLE = False
_PORCUPINE_AVAILABLE = False

try:
    import openwakeword  # type: ignore[import-untyped]

    _OPENWAKEWORD_AVAILABLE = True
except ImportError:
    logger.debug("openwakeword not available (optional dependency)")

try:
    import pvporcupine  # type: ignore[import-untyped]

    _PORCUPINE_AVAILABLE = True
except ImportError:
    logger.debug("pvporcupine not available (optional dependency)")


class WakeWordEngine:
    """Wake word detection engine.

    Supports multiple backends:
    - openwakeword: Open-source, CPU-efficient
    - porcupine: Picovoice commercial engine

    If the selected engine is not installed, falls back gracefully
    (always returns False for detection).
    """

    def __init__(self, config: Config) -> None:
        self._engine_name = config.voice.wake_word_engine
        self._wake_words = config.bot.wake_words
        self._running = False
        self._engine: Any = None

        # Validate engine availability
        if self._engine_name == "openwakeword" and not _OPENWAKEWORD_AVAILABLE:
            logger.warning(
                "Wake word engine 'openwakeword' selected but not installed. "
                "Install with: pip install openwakeword"
            )
        elif self._engine_name == "porcupine" and not _PORCUPINE_AVAILABLE:
            logger.warning(
                "Wake word engine 'porcupine' selected but not installed. "
                "Install with: pip install pvporcupine"
            )

    async def start(self) -> None:
        """Initialize the wake word engine."""
        if self._running:
            logger.debug("WakeWordEngine already running")
            return

        if not self._wake_words:
            logger.warning("No wake words configured, engine will not start")
            return

        try:
            if self._engine_name == "openwakeword" and _OPENWAKEWORD_AVAILABLE:
                self._engine = openwakeword.Model()
                logger.info(
                    "OpenWakeWord engine initialized with words: %s",
                    self._wake_words,
                )
            elif self._engine_name == "porcupine" and _PORCUPINE_AVAILABLE:
                # Porcupine requires keyword paths or built-in keywords
                # This is a placeholder - real implementation needs keyword files
                self._engine = pvporcupine.create(keywords=self._wake_words)
                logger.info(
                    "Porcupine engine initialized with words: %s",
                    self._wake_words,
                )
            else:
                logger.warning(
                    "Wake word engine '%s' not available, running in stub mode",
                    self._engine_name,
                )
                self._engine = None

            self._running = True
            logger.info("WakeWordEngine started")

        except Exception as exc:
            logger.exception("Failed to initialize wake word engine: %s", exc)
            self._engine = None
            self._running = False

    async def stop(self) -> None:
        """Stop and cleanup the wake word engine."""
        if not self._running:
            return

        if self._engine is not None:
            try:
                if hasattr(self._engine, "delete"):
                    self._engine.delete()
            except Exception as exc:
                logger.exception("Error cleaning up wake word engine: %s", exc)

        self._engine = None
        self._running = False
        logger.info("WakeWordEngine stopped")

    async def process_audio_chunk(self, chunk: bytes) -> bool:
        """Process audio chunk and return True if wake word detected.

        Args:
            chunk: Raw PCM audio bytes (typically 16kHz, 16-bit, mono)

        Returns:
            True if wake word detected, False otherwise
        """
        if not self._running or self._engine is None:
            return False

        try:
            if self._engine_name == "openwakeword" and _OPENWAKEWORD_AVAILABLE:
                # OpenWakeWord expects numpy array
                import numpy as np

                audio_array = np.frombuffer(chunk, dtype=np.int16)
                # Normalize to float32 in range [-1, 1]
                audio_float = audio_array.astype(np.float32) / 32768.0

                predictions = self._engine.predict(audio_float)
                # Check if any wake word exceeded threshold
                for word in self._wake_words:
                    if predictions.get(word, 0.0) > 0.5:
                        logger.info("Wake word detected: %s", word)
                        return True

            elif self._engine_name == "porcupine" and _PORCUPINE_AVAILABLE:
                # Porcupine expects specific frame size
                keyword_index = self._engine.process(chunk)
                if keyword_index >= 0:
                    detected_word = (
                        self._wake_words[keyword_index]
                        if keyword_index < len(self._wake_words)
                        else "unknown"
                    )
                    logger.info("Wake word detected: %s", detected_word)
                    return True

        except Exception as exc:
            logger.exception("Error processing audio chunk: %s", exc)

        return False

    @property
    def is_running(self) -> bool:
        """Return True if the engine is running."""
        return self._running
