"""OpenAI-compatible Beget AI Gateway chat executor.

Transport only: this module does not qualify models or invoke E4. Model pricing is
read from a dated JSON snapshot and matched only by the provider-returned model ID.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://api-llm.beget.com/v1"
DEFAULT_TIMEOUT_S = 30.0
PRICING_PATH = Path(__file__).resolve().parents[3] / "config" / "beget_pricing_v1.json"


class BegetChatExecutor:
    """Execute one chat-completion request through Beget's shared LLM gateway."""

    preserves_raw_response = True

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_S,
        opener: Callable[..., Any] | None = None,
        pricing_path: Path | str = PRICING_PATH,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Beget API key is required")
        if not isinstance(base_url, str) or not base_url.startswith("https://"):
            raise ValueError("Beget base URL must use HTTPS")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._api_key = api_key
        self._chat_url = f"{base_url.rstrip('/')}/chat/completions"
        self._timeout = timeout
        self._opener = opener or urlopen
        self._pricing_path = Path(pricing_path)

    @classmethod
    def from_env(cls) -> BegetChatExecutor | None:
        """Build from BEGET_* environment variables; None when no key is configured."""
        api_key = os.environ.get("BEGET_API_KEY")
        if not api_key:
            return None
        return cls(
            api_key,
            base_url=os.environ.get("BEGET_BASE_URL", DEFAULT_BASE_URL),
            timeout=float(os.environ.get("BEGET_TIMEOUT_S", str(DEFAULT_TIMEOUT_S))),
        )

    @staticmethod
    def _validate_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list")
        normalized: list[dict[str, Any]] = []
        for item in messages:
            if not isinstance(item, dict):
                raise ValueError("each message must be an object")
            role = item.get("role")
            content = item.get("content")
            if role not in {"system", "user", "assistant"}:
                raise ValueError("message role is not supported")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("message content must be a non-empty string")
            normalized.append({"role": role, "content": content})
        return normalized

    def _load_pricing(self) -> dict[str, Any]:
        try:
            raw = self._pricing_path.read_bytes()
            data = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict) or data.get("version") != 1:
            return {}
        models = data.get("models")
        return data if isinstance(models, dict) else {}

    def _estimate_cost(self, model_id: str | None, usage: dict[str, Any] | None) -> str:
        if not model_id or not isinstance(usage, dict):
            return "UNKNOWN"
        entry = self._load_pricing().get("models", {}).get(model_id)
        if not isinstance(entry, dict):
            return "UNKNOWN"
        input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
        output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
        if (
            type(input_tokens) is not int
            or type(output_tokens) is not int
            or input_tokens < 0
            or output_tokens < 0
        ):
            return "UNKNOWN"
        try:
            input_rate = Decimal(str(entry["input_rub_per_million"]))
            output_rate = Decimal(str(entry["output_rub_per_million"]))
            if (
                not input_rate.is_finite()
                or not output_rate.is_finite()
                or input_rate < 0
                or output_rate < 0
            ):
                return "UNKNOWN"
            total = (
                Decimal(input_tokens) * input_rate
                + Decimal(output_tokens) * output_rate
            ) / Decimal(1_000_000)
        except (KeyError, InvalidOperation, TypeError, ValueError):
            return "UNKNOWN"
        return format(total.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP), "f")

    @staticmethod
    def _error(
        error_type: str,
        code: str,
        message: str,
        *,
        status: int | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"type": error_type, "code": code, "message": message}
        if status is not None:
            result["http_status"] = status
        return result

    def execute(
        self,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> dict[str, Any]:
        """Return raw response evidence, parsed usage, RUB estimate, and safe error."""
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty catalog model ID")
        if type(max_tokens) is not int or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        normalized_messages = self._validate_messages(messages)
        request_body = json.dumps(
            {"model": model, "messages": normalized_messages, "max_tokens": max_tokens},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            self._chat_url,
            data=request_body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        status: int | None = None
        try:
            with self._opener(request, timeout=self._timeout) as response:
                status = getattr(response, "status", 200)
                raw = response.read()
        except HTTPError as exc:
            raw = exc.read()
            raw_text = raw.decode("utf-8", errors="replace")
            return {
                "raw_body": raw_text,
                "raw_body_sha256": hashlib.sha256(raw).hexdigest(),
                "model_id": None,
                "usage": None,
                "cost_estimate_rub": "UNKNOWN",
                "error": self._error(
                    "HTTPError", f"HTTP_{exc.code}", f"Beget returned HTTP {exc.code}",
                    status=exc.code,
                ),
            }
        except (TimeoutError, URLError, OSError) as exc:
            error_type = "TimeoutError" if isinstance(exc, TimeoutError) else type(exc).__name__
            code = "TIMEOUT" if isinstance(exc, TimeoutError) else "TRANSPORT_ERROR"
            return {
                "raw_body": None,
                "raw_body_sha256": None,
                "model_id": None,
                "usage": None,
                "cost_estimate_rub": "UNKNOWN",
                "error": self._error(error_type, code, "Beget request failed before a response body was received"),
            }

        raw_text = raw.decode("utf-8", errors="replace")
        raw_hash = hashlib.sha256(raw).hexdigest()
        try:
            decoded = json.loads(raw_text)
        except json.JSONDecodeError:
            return {
                "raw_body": raw_text,
                "raw_body_sha256": raw_hash,
                "model_id": None,
                "usage": None,
                "cost_estimate_rub": "UNKNOWN",
                "error": self._error("InvalidResponse", "INVALID_JSON", "Beget returned invalid JSON", status=status),
            }
        if not isinstance(decoded, dict):
            return {
                "raw_body": raw_text,
                "raw_body_sha256": raw_hash,
                "model_id": None,
                "usage": None,
                "cost_estimate_rub": "UNKNOWN",
                "error": self._error("InvalidResponse", "INVALID_BODY", "Beget response must be a JSON object", status=status),
            }

        model_id = decoded.get("model")
        if not isinstance(model_id, str) or not model_id.strip():
            model_id = None
        usage = decoded.get("usage")
        if not isinstance(usage, dict):
            usage = None
        choices = decoded.get("choices")
        content: str | None = None
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                content = message["content"]
        error = None
        if content is None:
            error = self._error("InvalidResponse", "CONTENT_MISSING", "Beget response has no text completion", status=status)

        return {
            "raw_body": raw_text,
            "raw_body_sha256": raw_hash,
            "model_id": model_id,
            "provider_response_id": decoded.get("id") if isinstance(decoded.get("id"), str) else None,
            "content": content,
            "usage": usage,
            "cost_estimate_rub": self._estimate_cost(model_id, usage),
            "error": error,
        }
