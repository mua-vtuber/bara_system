from __future__ import annotations

from app.core.logging import get_logger
from app.core.security import SecurityFilter
from app.services.llm import LLMService

logger = get_logger(__name__)

_LANG_NAMES: dict[str, str] = {
    "ko": "한국어",
    "en": "영어",
}

_KOREAN_THRESHOLD: float = 0.5


class TranslationService:
    """Lightweight translation layer backed by :class:`LLMService`."""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def translate(self, text: str, direction: str) -> str:
        """Translate *text* according to *direction* (``ko_to_en`` or ``en_to_ko``).

        Returns the translated string, or the original text on failure.
        """
        if not text or not text.strip():
            return text

        parts = direction.split("_to_")
        if len(parts) != 2:
            logger.warning("Invalid translation direction: %s", direction)
            return text

        _src_lang, tgt_lang = parts
        target_name = _LANG_NAMES.get(tgt_lang, tgt_lang)

        prompt = (
            f"다음 텍스트를 {target_name}로 번역해주세요. "
            "번역만 출력하세요:\n"
            f"{text}"
        )

        try:
            response = await self._llm.generate(prompt)
            translated = response.strip() if isinstance(response, str) else ""
            if not translated:
                logger.warning("LLM returned empty translation")
                return text
            return translated
        except Exception as exc:
            logger.error("Translation failed (%s): %s", direction, exc)
            return text

    def detect_language(self, text: str) -> str:
        """Detect language heuristically based on Korean character ratio.

        Returns ``"ko"`` if the Korean ratio >= threshold, else ``"en"``.
        """
        if not text:
            return "en"
        ratio = SecurityFilter.calculate_korean_ratio(text)
        return "ko" if ratio >= _KOREAN_THRESHOLD else "en"

    async def translate_if_needed(
        self, text: str, target: str
    ) -> tuple[str, str | None]:
        """Translate *text* to *target* language only when necessary.

        Returns
        -------
        tuple[str, str | None]
            ``(translated_text, direction)`` where *direction* is ``None``
            when no translation was performed.
        """
        detected = self.detect_language(text)
        if detected == target:
            return text, None

        direction = f"{detected}_to_{target}"
        translated = await self.translate(text, direction)
        return translated, direction
