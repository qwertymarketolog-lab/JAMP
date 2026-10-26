"""Minimal OpenAI-compatible OpenRouter chat executor.

This module performs one real provider call. It does not qualify models or
override JAMP's evidence gate; callers must pass the model selected by JAMP.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OpenRouterError(RuntimeError):
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


CROSSWALK_PATH = Path(__file__).resolve().parents[3] / "data/crosswalk/openrouter.json"
INTERNAL_MODEL_PREFIXES = ("am/", "ag/", "cx/")


def _load_crosswalk(path: Path = CROSSWALK_PATH) -> tuple[dict[str, str], str]:
    """Load verified production mappings; preserve unverified entries as non-routable."""
    try:
        raw = path.read_bytes()
        decoded = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise OpenRouterError("OPENROUTER_CROSSWALK_UNAVAILABLE_OR_INVALID") from None
    if not isinstance(decoded, dict) or decoded.get("version") != 1:
        raise OpenRouterError("OPENROUTER_CROSSWALK_SCHEMA_INVALID")
    mappings = decoded.get("mappings")
    if not isinstance(mappings, dict):
        raise OpenRouterError("OPENROUTER_CROSSWALK_SCHEMA_INVALID")
    normalized: dict[str, str] = {}
    for source, entry in mappings.items():
        if not isinstance(source, str) or not source.strip() or not isinstance(entry, dict):
            raise OpenRouterError("OPENROUTER_CROSSWALK_SCHEMA_INVALID")
        provider_id = entry.get("provider_id")
        verified = entry.get("verified_against_catalog")
        if (
            entry.get("provider") != "openrouter"
            or not isinstance(provider_id, str)
            or not provider_id.strip()
            or provider_id.endswith(":free")
            or type(verified) is not bool
        ):
            raise OpenRouterError("OPENROUTER_CROSSWALK_ENTRY_INVALID")
        if not verified:
            # Documented candidate only: do not expose it to production routing.
            continue
        normalized[source] = provider_id
    return normalized, "sha256:" + hashlib.sha256(raw).hexdigest()


class OpenRouterChatExecutor:
    """Callable JAMP executor for OpenRouter's chat-completions endpoint."""

    def __init__(
        self,
        api_key: str,
        *,
        chat_url: str = "https://openrouter.ai/api/v1/chat/completions",
        timeout: float = 30.0,
        max_tokens: int = 256,
        reasoning_effort: str | None = "low",
        model_id_map: dict[str, str] | None = None,
        fallback_models: list[str] | None = None,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenRouter API key is required")
        if not chat_url.startswith("https://"):
            raise ValueError("OpenRouter endpoint must use HTTPS")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if type(max_tokens) is not int or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        if reasoning_effort not in {None, "none", "minimal", "low", "medium", "high", "xhigh"}:
            raise ValueError("unsupported reasoning_effort")
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
        if fallback_models is not None and (
            not isinstance(fallback_models, list)
            or any(not isinstance(model, str) or not model.strip() for model in fallback_models)
        ):
            raise ValueError("fallback_models must be a list of non-empty strings")
        self._model_id_map = dict(model_id_map or {})
        self._fallback_models = list(fallback_models or [])
        self._crosswalk_digest = "sha256:local-model-id-map" if model_id_map is not None else None
        self._chat_url = chat_url
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._reasoning_effort = reasoning_effort
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
        max_tokens = int(os.environ.get("OPENROUTER_MAX_TOKENS", "256"))
        reasoning_effort = os.environ.get("OPENROUTER_REASONING_EFFORT", "low").strip().lower()
        if reasoning_effort in {"", "none"}:
            reasoning_effort = None if reasoning_effort == "" else "none"
        raw_model_id_map = os.environ.get("OPENROUTER_MODEL_ID_MAP", "").strip()
        fallback_models = [
            model.strip()
            for model in os.environ.get("OPENROUTER_FALLBACK_MODELS", "").split(",")
            if model.strip()
        ]
        if raw_model_id_map:
            environment = os.environ.get("JAMP_ENVIRONMENT", "production").strip().lower()
            if environment not in {"test", "local", "development"}:
                raise OpenRouterError(
                    "OPENROUTER_MODEL_ID_MAP_LOCAL_OVERRIDE_ONLY",
                    code="OPENROUTER_MODEL_ID_MAP_LOCAL_OVERRIDE_ONLY",
                )
        # Reject a production override before loading crosswalk data. A broken
        # crosswalk must not mask this security guard or its stable error code.
        model_id_map, crosswalk_digest = _load_crosswalk()
        if raw_model_id_map:
            try:
                decoded_model_id_map = json.loads(raw_model_id_map)
            except json.JSONDecodeError:
                raise ValueError("OPENROUTER_MODEL_ID_MAP must be a JSON object") from None
            if not isinstance(decoded_model_id_map, dict) or any(
                not isinstance(source, str)
                or not source.strip()
                or not isinstance(target, str)
                or not target.strip()
                for source, target in decoded_model_id_map.items()
            ):
                raise ValueError(
                    "OPENROUTER_MODEL_ID_MAP must map non-empty strings to non-empty strings"
                )
            model_id_map = decoded_model_id_map
            crosswalk_digest = "sha256:local-model-id-map"
        executor = cls(
            api_key,
            chat_url=chat_url,
            timeout=timeout,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            model_id_map=model_id_map,
            fallback_models=fallback_models,
        )
        executor._crosswalk_digest = crosswalk_digest
        return executor

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
        provider_requested_model = self._model_id_map.get(selected_model, selected_model)
        if (
            selected_model.startswith(INTERNAL_MODEL_PREFIXES)
            and selected_model not in self._model_id_map
        ):
            raise OpenRouterError(
                "MODEL_NOT_MAPPED",
                code="MODEL_NOT_MAPPED",
                diagnostics={
                    "requested_model_id": selected_model,
                    "crosswalk_digest": self._crosswalk_digest,
                },
            )
        messages = self._messages(payload)
        models_to_try = [provider_requested_model, *self._fallback_models]
        decoded: dict[str, Any] | None = None
        used_model: str | None = None
        last_error: Exception | None = None

        for model in models_to_try:
            body = json.dumps(
                {
                    "model": model,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": self._max_tokens,
                    **(
                        {"reasoning": {"effort": self._reasoning_effort}}
                        if self._reasoning_effort is not None
                        else {}
                    ),
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
            except HTTPError as exc:
                if exc.code >= 500:
                    last_error = exc
                    continue
                # 4xx is a hard failure; do not hide configuration/model errors.
                raise OpenRouterError(
                    f"OpenRouter returned HTTP {exc.code}",
                    code=f"OPENROUTER_HTTP_{exc.code}",
                    diagnostics={"provider_http_status": exc.code},
                ) from None
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                continue

            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise OpenRouterError("OpenRouter returned invalid JSON") from None
            if not isinstance(parsed, dict):
                raise OpenRouterError("OpenRouter response must be a JSON object")
            decoded = parsed
            used_model = model
            break

        if decoded is None or used_model is None:
            if isinstance(last_error, HTTPError):
                raise OpenRouterError(
                    f"All OpenRouter models failed; last HTTP status {last_error.code}",
                    code=f"OPENROUTER_HTTP_{last_error.code}",
                    diagnostics={"provider_http_status": last_error.code},
                ) from None
            raise OpenRouterError(
                "All OpenRouter models failed; last error: "
                + (type(last_error).__name__ if last_error is not None else "unknown"),
                code="OPENROUTER_ALL_MODELS_FAILED",
                diagnostics={
                    "last_error_type": type(last_error).__name__ if last_error is not None else None
                },
            ) from None

        provider_requested_model = used_model

        if not isinstance(decoded, dict):
            raise OpenRouterError("OpenRouter response must be a JSON object")
        choices = decoded.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise OpenRouterError("OpenRouter response has no completion choice")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            reasoning = message.get("reasoning") if isinstance(message, dict) else None
            diagnostics = {
                "finish_reason": choices[0].get("finish_reason"),
                "usage": decoded.get("usage") if isinstance(decoded.get("usage"), dict) else None,
                "content_len": len(content) if isinstance(content, str) else 0,
                "reasoning_len": len(reasoning) if isinstance(reasoning, str) else 0,
                "requested_max_tokens": self._max_tokens,
                "model": provider_requested_model,
            }
            raise OpenRouterError(
                "OpenRouter response has no text content",
                diagnostics=diagnostics,
            )

        result: dict[str, Any] = {
            "provider": "openrouter",
            "model": selected_model,
            "requested_model_id": selected_model,
            "provider_requested_model_id": provider_requested_model,
            "crosswalk_digest": self._crosswalk_digest,
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
