"""Minimal OpenAI-compatible AnyModel chat executor.

This module performs one real provider call. It does not qualify models or
override JAMP's evidence gate; callers must pass the model selected by JAMP.
"""

from __future__ import annotations

import json
import logging
import math
import os
from collections.abc import Callable
from typing import Any
from urllib.request import Request, urlopen

COST_PER_MILLION_TOKENS_USD = 0.12
DEFAULT_MAX_INPUT_TOKENS = 8192
LEGACY_MAX_TOKENS = 512
DEFAULT_USER_AGENT = "JAMP-GPT-6-Astra-API-Probe/1.0"


class AnyModelError(RuntimeError):
    """Provider request or response failed the execution contract."""


class AnyModelBudgetError(AnyModelError):
    """A request exceeded its configured input or cost budget."""


class AnyModelChatExecutor:
    """Callable JAMP executor for AnyModel's chat-completions endpoint."""

    preserves_content_blocks = True

    def __init__(
        self,
        api_key: str,
        *,
        chat_url: str = "https://anymodel.org/v1/chat/completions",
        timeout: float = 30.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("AnyModel API key is required")
        if not chat_url.startswith("https://"):
            raise ValueError("AnyModel endpoint must use HTTPS")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._api_key = api_key
        self._chat_url = chat_url
        self._timeout = timeout
        self._opener = opener or urlopen

    @classmethod
    def from_env(cls) -> AnyModelChatExecutor | None:
        """Build from environment; return None when no key is configured."""
        api_key = os.environ.get("ANYMODEL_API_KEY")
        if not api_key:
            return None
        base_url = os.environ.get("ANYMODEL_BASE_URL", "https://anymodel.org/v1")
        chat_url = os.environ.get(
            "ANYMODEL_CHAT_URL", f"{base_url.rstrip('/')}/chat/completions"
        )
        timeout = float(os.environ.get("ANYMODEL_TIMEOUT_S", "30"))
        return cls(api_key, chat_url=chat_url, timeout=timeout)

    @staticmethod
    def estimate_cost_usd(max_input_tokens: int, max_tokens: int) -> float:
        """Return the configured conservative flat-rate request estimate."""
        return (
            (max_input_tokens + max_tokens)
            * COST_PER_MILLION_TOKENS_USD
            / 1_000_000
        )

    @staticmethod
    def _messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
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
                raise AnyModelError("A non-empty prompt or messages list is required")
            return [{"role": "user", "content": prompt}]

        if not isinstance(messages, list) or not messages:
            raise AnyModelError("messages must be a non-empty list")
        normalized: list[dict[str, Any]] = []
        for item in messages:
            if not isinstance(item, dict):
                raise AnyModelError("Each message must be an object")
            role = item.get("role")
            content = item.get("content")
            if role not in {"system", "user", "assistant"}:
                raise AnyModelError("Message role is not supported")
            if isinstance(content, str) and content.strip():
                normalized_content: str | list[dict[str, Any]] = content
            elif (
                isinstance(content, list)
                and content
                and all(
                    isinstance(part, dict)
                    and isinstance(part.get("type"), str)
                    and part["type"].strip()
                    for part in content
                )
            ):
                normalized_content = [dict(part) for part in content]
            else:
                raise AnyModelError(
                    "Message content must be a non-empty string or typed content-block list"
                )
            normalized.append({"role": role, "content": normalized_content})
        return normalized

    def _send(
        self, selected_model: str, payload: dict[str, Any], *, max_tokens: int
    ) -> dict[str, Any]:
        if not isinstance(selected_model, str) or not selected_model:
            raise AnyModelError("JAMP must select exactly one model for this executor")
        body = json.dumps(
            {
                "model": selected_model,
                "messages": self._messages(payload),
                "temperature": 0,
                "max_tokens": max_tokens,
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
                "User-Agent": DEFAULT_USER_AGENT,
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                raw = response.read()
            decoded = json.loads(raw.decode("utf-8"))
        # Preserve urllib transport exceptions for caller-side safe diagnostics.
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AnyModelError("AnyModel returned invalid JSON") from None

        if not isinstance(decoded, dict):
            raise AnyModelError("AnyModel response must be a JSON object")
        choices = decoded.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise AnyModelError("AnyModel response has no completion choice")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise AnyModelError("AnyModel response has no text content")

        result: dict[str, Any] = {
            "provider": "anymodel",
            "model": selected_model,
            "content": content,
        }
        if isinstance(decoded.get("model"), str) and decoded["model"].strip():
            result["provider_model_id"] = decoded["model"]
        if isinstance(decoded.get("id"), str):
            result["provider_response_id"] = decoded["id"]
        if isinstance(decoded.get("usage"), dict):
            result["usage"] = decoded["usage"]
        return result

    def execute(
        self,
        selected_model: str,
        payload: dict[str, Any],
        *,
        max_tokens: int | None = None,
        max_budget_usd: float | None = None,
        max_input_tokens: int = DEFAULT_MAX_INPUT_TOKENS,
    ) -> dict[str, Any]:
        """Execute only when explicit output and USD budgets pass preflight."""
        if (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or max_tokens <= 0
        ):
            raise ValueError("max_tokens must be an explicitly supplied positive integer")
        if (
            isinstance(max_input_tokens, bool)
            or not isinstance(max_input_tokens, int)
            or max_input_tokens <= 0
        ):
            raise ValueError("max_input_tokens must be a positive integer")
        if (
            isinstance(max_budget_usd, bool)
            or not isinstance(max_budget_usd, (int, float))
            or not math.isfinite(max_budget_usd)
            or max_budget_usd <= 0
        ):
            raise ValueError("max_budget_usd must be a finite positive number")

        messages = self._messages(payload)
        input_representation = json.dumps(
            {"model": selected_model, "messages": messages, "temperature": 0},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(input_representation) > max_input_tokens:
            raise AnyModelBudgetError(
                f"INPUT_LIMIT_EXCEEDED: request bytes {len(input_representation)} "
                f"> max_input_tokens {max_input_tokens}"
            )
        estimated_cost = self.estimate_cost_usd(max_input_tokens, max_tokens)
        if estimated_cost > max_budget_usd:
            raise AnyModelBudgetError(
                f"BUDGET_EXCEEDED: estimated_cost_usd={estimated_cost:.8f} "
                f"> max_budget_usd={max_budget_usd:.8f}"
            )
        return self._send(selected_model, {"messages": messages}, max_tokens=max_tokens)

    def __call__(self, selected_model: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Backward-compatible legacy call; new code must use execute()."""
        logging.getLogger(__name__).warning(
            "Legacy AnyModelChatExecutor.__call__ uses max_tokens=%s; "
            "migrate to execute(max_tokens=..., max_budget_usd=...).",
            LEGACY_MAX_TOKENS,
        )
        return self._send(selected_model, payload, max_tokens=LEGACY_MAX_TOKENS)
