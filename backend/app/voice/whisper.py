"""Whisper-based speech-to-text engine with VRAM management."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.core.config import Config

logger = get_logger(__name__)

# Optional dependency detection
_WHISPER_AVAILABLE = False
_TORCH_AVAILABLE = False
_NUMPY_AVAILABLE = False

try:
    import whisper  # type: ignore[import-untyped]

    _WHISPER_AVAILABLE = True
except ImportError:
    logger.debug("whisper not available (optional dependency)")

try:
    import torch

    _TORCH_AVAILABLE = True
except ImportError:
    logger.debug("torch not available (optional dependency)")

try:
    import numpy as np

    _NUMPY_AVAILABLE = True
except ImportError:
    logger.debug("numpy not available (optional dependency)")


class WhisperEngine:
    """Whisper speech-to-text engine with automatic VRAM management.

    The model is loaded on-demand when transcribe() is called and
    can be explicitly unloaded to free VRAM.

    Supported models: tiny, base, small, medium, large
    """

    def __init__(self, config: Config) -> None:
        self._model_name = config.voice.stt_model
        self._language = config.voice.language
        self._model: Any = None
        self._loaded = False

        # Validate dependencies
        if not _WHISPER_AVAILABLE:
            logger.warning(
                "Whisper not installed. Install with: pip install openai-whisper"
            )
        if not _TORCH_AVAILABLE:
            logger.warning(
                "PyTorch not installed. Install with: pip install torch"
            )
        if not _NUMPY_AVAILABLE:
            logger.warning(
                "NumPy not installed. Install with: pip install numpy"
            )

    async def load_model(self) -> None:
        """Load Whisper model into VRAM.

        This is called automatically by transcribe() if needed.
        Raises ImportError if dependencies are not installed.
        """
        if self._loaded:
            logger.debug("Whisper model already loaded")
            return

        if not _WHISPER_AVAILABLE:
            raise ImportError(
                "Whisper is not installed. Install with: pip install openai-whisper"
            )
        if not _TORCH_AVAILABLE:
            raise ImportError(
                "PyTorch is not installed. Install with: pip install torch"
            )

        try:
            logger.info("Loading Whisper model: %s", self._model_name)
            self._model = whisper.load_model(self._model_name)
            self._loaded = True
            logger.info("Whisper model loaded successfully (VRAM allocated)")
        except Exception as exc:
            logger.exception("Failed to load Whisper model: %s", exc)
            raise

    async def unload_model(self) -> None:
        """Unload Whisper model and free VRAM.

        Should be called after transcription is complete to minimize
        memory usage.
        """
        if not self._loaded:
            return

        if self._model is not None:
            try:
                del self._model
                self._model = None

                # Free CUDA memory if available
                if _TORCH_AVAILABLE and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logger.debug("CUDA cache cleared")

            except Exception as exc:
                logger.exception("Error unloading Whisper model: %s", exc)

        self._loaded = False
        logger.info("Whisper model unloaded (VRAM freed)")

    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio bytes to text.

        Args:
            audio_data: Raw PCM audio bytes or WAV/MP3 file bytes

        Returns:
            Transcribed text

        Raises:
            ImportError: If required dependencies are not installed
            Exception: If transcription fails
        """
        if not self._loaded:
            await self.load_model()

        if not _NUMPY_AVAILABLE:
            raise ImportError(
                "NumPy is not installed. Install with: pip install numpy"
            )

        try:
            # Convert bytes to numpy array
            # If audio_data is WAV/MP3, we need to decode it
            # For simplicity, assume raw PCM 16kHz 16-bit mono
            import numpy as np

            # Try to load as audio file first (WAV, MP3, etc.)
            try:
                # Use librosa or soundfile if available
                try:
                    import soundfile as sf

                    audio_array, sample_rate = sf.read(io.BytesIO(audio_data))
                except ImportError:
                    # Fallback: assume raw PCM
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                    sample_rate = 16000
                    # Normalize to float32 in range [-1, 1]
                    audio_array = audio_array.astype(np.float32) / 32768.0

            except Exception:
                # Last resort: treat as raw PCM
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                audio_array = audio_array.astype(np.float32) / 32768.0

            # Transcribe using Whisper
            logger.debug("Starting transcription (model=%s, language=%s)",
                        self._model_name, self._language)

            result = self._model.transcribe(
                audio_array,
                language=self._language if self._language != "auto" else None,
                fp16=_TORCH_AVAILABLE and torch.cuda.is_available(),
            )

            text = result.get("text", "").strip()
            logger.info("Transcription complete: %s", text[:100])
            return text

        except Exception as exc:
            logger.exception("Transcription failed: %s", exc)
            raise

    @property
    def is_loaded(self) -> bool:
        """Return True if the model is loaded."""
        return self._loaded
