"""Voice subsystem for wake word detection and speech-to-text."""

from __future__ import annotations

__all__ = ["WakeWordEngine", "WhisperEngine"]

try:
    from app.voice.wake_word import WakeWordEngine
except ImportError:
    WakeWordEngine = None  # type: ignore[assignment, misc]

try:
    from app.voice.whisper import WhisperEngine
except ImportError:
    WhisperEngine = None  # type: ignore[assignment, misc]
