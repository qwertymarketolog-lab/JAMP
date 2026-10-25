"""Minimal OpenAI-compatible Groq chat executor.

This module performs one real provider call. It does not qualify models or
override JAMP's evidence gate; callers must preserve the selected model identity.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
INTERNAL_MODEL_PREFIXES = ("am/", "ag/", "cx/")


class GroqError(RuntimeError):
    """Provider request or response failed the execution contract."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.diagnostics = dict(diagnostics or {})


class GroqChatExecutor:
    """Callable JAMP executor for Groq's OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        api_key: str,
        *,
        chat_url: str = "https://api.groq.com/openai/v1/chat/completions",
        timeout: float = 30.0,
        max_tokens: int = 256,
        default_model: str = DEFAULT_GROQ_MODEL,
        model_id_map: dict[str, str] | None = None,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Groq API key is required")
        if not chat_url.startswith("https://"):
            raise ValueError("Groq endpoint must use HTTPS")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if type(max_tokens) is not int or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        if not isinstance(default_model, str) or not default_model.strip():
            raise ValueError("default_model must be a non-empty string")
        if model_id_map is not None and (
            not isinstance(model_id_map, dict)
            or any(
                not isinstance(source, str)
                or not source.strip()
                or not isinstance(target, str)
                or not target.strip()
                for source, target in model_id_map.items()
            )
        ):
            raise ValueError("model_id_map must map non-empty strings to non-empty strings")
        self._api_key = api_key
        self._chat_url = chat_url
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._default_model = default_model
        self._model_id_map = dict(model_id_map or {})
        self._opener = opener or urlopen

    @classmethod
    def from_env(cls) -> GroqChatExecutor | None:
        """Build from environment; return None when no key is configured."""
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return None
        base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        chat_url = os.environ.get("GROQ_CHAT_URL", f"{base_url.rstrip('/')}/chat/completions")
        timeout = float(os.environ.get("GROQ_TIMEOUT_S", "30"))
        max_tokens = int(os.environ.get("GROQ_MAX_TOKENS", "256"))
        default_model = os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL).strip()
        raw_model_id_map = os.environ.get("GROQ_MODEL_ID_MAP", "").strip()
        if raw_model_id_map:
            try:
                model_id_map = json.loads(raw_model_id_map)
            except json.JSONDecodeError:
                raise ValueError("GROQ_MODEL_ID_MAP must be a JSON object") from None
            if not isinstance(model_id_map, dict) or any(
                not isinstance(source, str)
                or not source.strip()
                or not isinstance(target, str)
                or not target.strip()
                for source, target in model_id_map.items()
            ):
                raise ValueError(
                    "GROQ_MODEL_ID_MAP must map non-empty strings to non-empty strings"
                )
        else:
            model_id_map = {}
        return cls(
            api_key,
            chat_url=chat_url,
            timeout=timeout,
            max_tokens=max_tokens,
            default_model=default_model,
            model_id_map=model_id_map,
        )

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
                raise GroqError("A non-empty prompt or messages list is required")
            return [{"role": "user", "content": prompt}]

        if not isinstance(messages, list) or not messages:
            raise GroqError("messages must be a non-empty list")
        normalized: list[dict[str, str]] = []
        for item in messages:
            if not isinstance(item, dict):
                raise GroqError("Each message must be an object")
            role = item.get("role")
            content = item.get("content")
            if role not in {"system", "user", "assistant"}:
                raise GroqError("Message role is not supported")
            if not isinstance(content, str) or not content.strip():
                raise GroqError("Message content must be a non-empty string")
            normalized.append({"role": role, "content": content})
        return normalized

    def __call__(self, selected_model: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Call Groq and preserve both JAMP-selected and provider-requested identities."""
        if not isinstance(selected_model, str) or not selected_model.strip():
            raise GroqError("JAMP must select exactly one model for this executor")
        provider_model = self._model_id_map.get(selected_model)
        if provider_model is None:
            if selected_model.startswith(INTERNAL_MODEL_PREFIXES):
                raise GroqError(
                    "MODEL_NOT_MAPPED",
                    code="MODEL_NOT_MAPPED",
                    diagnostics={
                        "requested_model_id": selected_model,
                    },
                )
            provider_model = (
                self._default_model if selected_model == "groq/default" else selected_model
            )
        body = json.dumps(
            {
                "model": provider_model,
                "messages": self._messages(payload),
                "temperature": 0,
                "max_tokens": self._max_tokens,
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
                "User-Agent": "JAMP-Trust-Layer/1.0",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            raise GroqError(
                f"Groq returned HTTP {exc.code}",
                code=f"GROQ_HTTP_{exc.code}",
                diagnostics={"provider_http_status": exc.code},
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise GroqError(
                "Groq transport failed",
                code="GROQ_TRANSPORT_ERROR",
                diagnostics={"exception_type": type(exc).__name__},
            ) from None
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GroqError("Groq returned invalid JSON", code="GROQ_INVALID_JSON") from None
        if not isinstance(decoded, dict):
            raise GroqError("Groq response must be a JSON object")
        choices = decoded.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise GroqError("Groq response has no completion choice")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise GroqError("Groq response has no text content")

        result: dict[str, Any] = {
            "provider": "groq",
            "model": selected_model,
            "requested_model_id": selected_model,
            "provider_requested_model_id": provider_model,
            "content": content,
            "qualification": "UNKNOWN",
        }
        if isinstance(decoded.get("model"), str):
            result["provider_model_id"] = decoded["model"]
        if isinstance(decoded.get("id"), str):
            result["provider_response_id"] = decoded["id"]
        if isinstance(decoded.get("usage"), dict):
            result["usage"] = decoded["usage"]
        return result
