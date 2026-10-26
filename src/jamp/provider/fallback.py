"""Bounded, auditable provider fallback execution with task-scoped qualification."""

from __future__ import annotations

import collections.abc
import re
import typing

QualificationChecker = collections.abc.Callable[[str, str], str]


class FallbackChainExecutor:
    """Try providers in order, but never retry an unqualified model on another provider."""

    def __init__(
        self,
        executors: list[collections.abc.Callable[[str, dict[str, typing.Any]], typing.Any]],
        *,
        max_attempts: int = 5,
        qualification_checker: QualificationChecker | None = None,
    ):
        if not isinstance(executors, list):
            raise TypeError("executors must be a list")
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        if any(not callable(executor) for executor in executors):
            raise TypeError("every executor must be callable")
        if qualification_checker is not None and not callable(qualification_checker):
            raise TypeError("qualification_checker must be callable")
        self.executors = list(executors)
        self.max_attempts = min(max_attempts, 5)
        self._qualification_checker = qualification_checker

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
        message = re.sub(
            r"(?i)(api[_ -]?key|token|secret)(\s*[:=]\s*)[^\s,;]+",
            r"\1\2[REDACTED]",
            message,
        )
        return message[:150]

    @staticmethod
    def _task_profile(payload: dict[str, typing.Any]) -> str | None:
        candidate = payload.get("task_profile") or payload.get("intent")
        return (
            candidate
            if candidate
            in {
                "search_and_extraction",
                "tool_execution_agent",
                "long_context_analysis",
                "strict_compliance_safety",
            }
            else None
        )

    def _is_qualified(self, model_id: str, task_profile: str | None) -> bool:
        if task_profile is None:
            return False
        checker = self._qualification_checker
        if checker is None:
            from jamp.runtime.qualification import evaluate_model_qualification

            checker = evaluate_model_qualification
        try:
            return checker(model_id, task_profile) == "QUALIFIED"
        except Exception:
            return False

    def __call__(
        self, selected_model: str, payload: dict[str, typing.Any]
    ) -> dict[str, typing.Any]:
        history: list[dict[str, typing.Any]] = []
        for index, executor in enumerate(self.executors[: self.max_attempts]):
            if index > 0 and not self._is_qualified(selected_model, self._task_profile(payload)):
                error = RuntimeError("Fallback refused: model is not QUALIFIED for this task.")
                error.fallback_history = list(history)  # type: ignore[attr-defined]
                raise error
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
