"""Minimal OpenAI-compatible OpenRouter chat executor.

This module performs one real provider call. It does not qualify models or
override JAMP's evidence gate; callers must pass the model selected by JAMP.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OpenRouterError(RuntimeError):
    """Provider request or response failed the execution contract."""


class OpenRouterChatExecutor:
    """Callable JAMP executor for OpenRouter's chat-completions endpoint."""

    def __init__(
        self,
        api_key: str,
        *,
        chat_url: str = "https://openrouter.ai/api/v1/chat/completions",
        timeout: float = 30.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenRouter API key is required")
        if not chat_url.startswith("https://"):
            raise ValueError("OpenRouter endpoint must use HTTPS")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._api_key = api_key
        self._chat_url = chat_url
        self._timeout = timeout
        self._opener = opener or urlopen

    @classmethod
    def from_env(cls) -> OpenRouterChatExecutor | None:
        """Build from environment; return None when no key is configured."""
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            return None
        base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        chat_url = os.environ.get("OPENROUTER_CHAT_URL", f"{base_url.rstrip('/')}/chat/completions")
        timeout = float(os.environ.get("OPENROUTER_TIMEOUT_S", "30"))
        return cls(api_key, chat_url=chat_url, timeout=timeout)

    @staticmethod
    def _messages(payload: dict[str, Any]) -> list[dict[str, str]]:
        messages = payload.get("messages")
        if messages is None:
            prompt = next(
                (
                    payload.get(key)
                    for key in ("prompt", "query", "text", "input")
                    if isinstance(payload.get(key), str) and payload[key].strip()
                ),
                None,
            )
            if prompt is None:
                raise OpenRouterError("A non-empty prompt or messages list is required")
            return [{"role": "user", "content": prompt}]

        if not isinstance(messages, list) or not messages:
            raise OpenRouterError("messages must be a non-empty list")
        normalized: list[dict[str, str]] = []
        for item in messages:
            if not isinstance(item, dict):
                raise OpenRouterError("Each message must be an object")
            role = item.get("role")
            content = item.get("content")
            if role not in {"system", "user", "assistant"}:
                raise OpenRouterError("Message role is not supported")
            if not isinstance(content, str) or not content.strip():
                raise OpenRouterError("Message content must be a non-empty string")
            normalized.append({"role": role, "content": content})
        return normalized

    def __call__(self, selected_model: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Call the selected model and return a compact, auditable result."""
        if not isinstance(selected_model, str) or not selected_model:
            raise OpenRouterError("JAMP must select exactly one model for this executor")
        body = json.dumps(
            {
                "model": selected_model,
                "messages": self._messages(payload),
                "temperature": 0,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            self._chat_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                raw = response.read()
            decoded = json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            raise OpenRouterError(f"OpenRouter returned HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError):
            raise OpenRouterError("OpenRouter transport failed") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OpenRouterError("OpenRouter returned invalid JSON") from None

        if not isinstance(decoded, dict):
            raise OpenRouterError("OpenRouter response must be a JSON object")
        choices = decoded.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise OpenRouterError("OpenRouter response has no completion choice")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise OpenRouterError("OpenRouter response has no text content")

        result: dict[str, Any] = {
            "provider": "openrouter",
            "model": selected_model,
            "content": content,
        }
        if isinstance(decoded.get("id"), str):
            result["provider_response_id"] = decoded["id"]
        if isinstance(decoded.get("usage"), dict):
            result["usage"] = decoded["usage"]
        return result
