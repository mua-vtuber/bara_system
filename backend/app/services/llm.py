from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, Optional

from app.core.config import Config
from app.core.constants import MAX_LLM_INPUT_LENGTH
from app.core.exceptions import LLMConnectionError, LLMGenerationError
from app.core.http_client import HttpClient
from app.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_OLLAMA_BASE_URL: str = "http://localhost:11434"
_STREAM_TIMEOUT_SECONDS: int = 300


class LLMService:
    """High-level wrapper around the Ollama REST API.

    All requests are serialised through an :class:`asyncio.Lock` because
    Ollama processes one generation at a time -- concurrent requests would
    queue server-side anyway and waste resources on the client.
    """

    def __init__(
        self,
        config: Config,
        http_client: HttpClient,
        *,
        ollama_base_url: str = _DEFAULT_OLLAMA_BASE_URL,
    ) -> None:
        self._config = config
        self._http_client = http_client
        self._lock = asyncio.Lock()
        self._model_name: str = config.bot.model
        self._ollama_base_url: str = ollama_base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def base_url(self) -> str:
        return self._ollama_base_url

    # ------------------------------------------------------------------
    # Generate (raw prompt)
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        *,
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        """Send a raw prompt to ``/api/generate``.

        Parameters
        ----------
        prompt:
            The user prompt.
        system:
            Optional system prompt.
        stream:
            When ``True`` return an :class:`AsyncIterator` that yields
            tokens one by one.  When ``False`` return the full response
            as a single string.
        """
        if len(prompt) > MAX_LLM_INPUT_LENGTH:
            raise LLMGenerationError("Input prompt too long")

        url = f"{self._ollama_base_url}/api/generate"
        body: dict[str, Any] = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": stream,
        }
        if system is not None:
            body["system"] = system

        if stream:
            return self._stream_request(url, body)
        return await self._blocking_request(url, body, response_key="response")

    # ------------------------------------------------------------------
    # Chat (multi-turn messages)
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        """Send a chat-style conversation to ``/api/chat``.

        Parameters
        ----------
        messages:
            List of ``{"role": "user"|"assistant"|"system", "content": "..."}``.
        stream:
            When ``True`` return an :class:`AsyncIterator` that yields
            tokens one by one.
        """
        total_len = sum(len(m.get("content", "")) for m in messages)
        if total_len > MAX_LLM_INPUT_LENGTH:
            raise LLMGenerationError("Total message content too long")

        url = f"{self._ollama_base_url}/api/chat"
        body: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "stream": stream,
        }

        if stream:
            return self._stream_request(url, body)
        return await self._blocking_request(url, body, response_key="message")

    # ------------------------------------------------------------------
    # Model management helpers
    # ------------------------------------------------------------------

    async def get_available_models(self) -> list[dict[str, Any]]:
        """Return the list of locally available models from ``/api/tags``."""
        url = f"{self._ollama_base_url}/api/tags"
        try:
            async with self._lock:
                data = await self._http_client.get(url, platform="ollama")
        except Exception as exc:
            raise LLMConnectionError(
                f"Failed to list models: {exc}"
            ) from exc

        if isinstance(data, dict):
            return data.get("models", [])  # type: ignore[return-value]
        return []

    async def get_model_info(self, model_name: str) -> dict[str, Any]:
        """Return detailed information about *model_name* via ``/api/show``."""
        url = f"{self._ollama_base_url}/api/show"
        try:
            async with self._lock:
                data = await self._http_client.post(
                    url, json={"name": model_name}, platform="ollama"
                )
        except Exception as exc:
            raise LLMConnectionError(
                f"Failed to get model info for '{model_name}': {exc}"
            ) from exc

        if isinstance(data, dict):
            return data
        return {}

    async def check_health(self) -> bool:
        """Return ``True`` when the Ollama server responds on ``/``."""
        url = f"{self._ollama_base_url}/"
        try:
            async with self._lock:
                resp = await self._http_client.get(url, platform="ollama")
            # Ollama returns "Ollama is running" as plain text
            if isinstance(resp, str) and "Ollama is running" in resp:
                return True
            return True  # any 2xx is fine
        except Exception:
            return False

    async def switch_model(self, model_name: str) -> None:
        """Change the active model name at runtime."""
        logger.info("Switching LLM model: %s -> %s", self._model_name, model_name)
        self._model_name = model_name

    # ------------------------------------------------------------------
    # Internal: blocking (non-stream) request
    # ------------------------------------------------------------------

    async def _blocking_request(
        self,
        url: str,
        body: dict[str, Any],
        *,
        response_key: str,
    ) -> str:
        """POST *body* to *url* under the serialisation lock and return the
        generated text.

        For ``/api/generate`` *response_key* is ``"response"``.
        For ``/api/chat`` *response_key* is ``"message"`` (the content is
        nested under ``message.content``).
        """
        try:
            async with self._lock:
                data = await self._http_client.post(
                    url, json=body, platform="ollama"
                )
        except Exception as exc:
            raise LLMConnectionError(
                f"Ollama request failed: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise LLMGenerationError("Unexpected non-JSON response from Ollama")

        # /api/generate -> {"response": "..."}
        if response_key == "response":
            text = data.get("response", "")
        # /api/chat -> {"message": {"role": "assistant", "content": "..."}}
        elif response_key == "message":
            msg = data.get("message", {})
            text = msg.get("content", "") if isinstance(msg, dict) else ""
        else:
            text = ""

        if not text:
            raise LLMGenerationError("Ollama returned an empty response")

        return text

    # ------------------------------------------------------------------
    # Internal: streaming request
    # ------------------------------------------------------------------

    async def _stream_request(
        self,
        url: str,
        body: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Return an async iterator that yields tokens while holding the lock
        for the entire generation duration.

        The caller **must** fully consume the iterator (or break out of it)
        so that the lock is released.
        """
        return self._stream_inner(url, body)

    async def _stream_inner(
        self,
        url: str,
        body: dict[str, Any],
    ) -> AsyncIterator[str]:
        """The actual generator that holds ``_lock`` for the full stream."""
        import aiohttp

        async with self._lock:
            session = self._http_client._session  # noqa: SLF001
            if session is None or session.closed:
                raise LLMConnectionError(
                    "HttpClient session is not started. Call start() first."
                )

            timeout = aiohttp.ClientTimeout(total=_STREAM_TIMEOUT_SECONDS)
            try:
                async with session.post(url, json=body, timeout=timeout) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise LLMGenerationError(
                            f"Ollama stream returned {resp.status}: {text[:200]}"
                        )

                    async for raw_line in resp.content:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # /api/generate streams {"response": "token", "done": false}
                        token = chunk.get("response", "")
                        # /api/chat streams {"message": {"content": "token"}, "done": false}
                        if not token:
                            msg = chunk.get("message")
                            if isinstance(msg, dict):
                                token = msg.get("content", "")

                        if token:
                            yield token

                        if chunk.get("done", False):
                            return

            except aiohttp.ClientError as exc:
                raise LLMConnectionError(
                    f"Stream connection error: {exc}"
                ) from exc
