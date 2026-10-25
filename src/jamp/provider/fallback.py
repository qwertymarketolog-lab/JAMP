"""Bounded, auditable provider fallback execution."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any


class FallbackChainExecutor:
    """Try configured executors in order and retain sanitized failure history."""

    def __init__(
        self,
        executors: list[Callable[[str, dict[str, Any]], Any]],
        *,
        max_attempts: int = 5,
    ):
        if not isinstance(executors, list):
            raise TypeError("executors must be a list")
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if any(not callable(executor) for executor in executors):
            raise TypeError("every executor must be callable")
        self.executors = list(executors)
        self.max_attempts = min(max_attempts, 5)

    @staticmethod
    def _status(exc: Exception) -> int:
        candidates = (
            getattr(exc, "http_status", None),
            getattr(exc, "status_code", None),
            getattr(exc, "status", None),
            getattr(exc, "code", None),
        )
        for candidate in candidates:
            if (
                isinstance(candidate, int)
                and not isinstance(candidate, bool)
                and 100 <= candidate <= 599
            ):
                return candidate
            if isinstance(candidate, str):
                match = re.search(r"(?:HTTP[_ ]?)?(\d{3})$", candidate)
                if match:
                    return int(match.group(1))
        match = re.search(r"\bHTTP\s+(\d{3})\b", str(exc), re.IGNORECASE)
        return int(match.group(1)) if match else 500

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        message = str(exc)
        message = re.sub(r"(?i)(bearer\s+)[^\s,;]+", r"\1[REDACTED]", message)
        message = re.sub(r"(?i)(api[_ -]?key|token|secret)(\s*[:=]\s*)[^\s,;]+", r"\1\2[REDACTED]", message)
        return message[:150]

    def __call__(self, selected_model: str, payload: dict[str, Any]) -> dict[str, Any]:
        history: list[dict[str, Any]] = []
        for executor in self.executors[: self.max_attempts]:
            try:
                result = executor(selected_model, payload)
                if not isinstance(result, dict):
                    raise RuntimeError("Provider returned a non-object result")
                # Do not trust an executor to overwrite the audit trail.
                result = dict(result)
                result["fallback_history"] = list(history)
                return result
            except Exception as exc:
                history.append(
                    {
                        "provider": type(executor).__name__,
                        "requested_model": selected_model,
                        "http_status": self._status(exc),
                        "error": self._safe_error(exc),
                    }
                )
        error = RuntimeError("All fallback providers failed.")
        error.fallback_history = history  # type: ignore[attr-defined]
        raise error
