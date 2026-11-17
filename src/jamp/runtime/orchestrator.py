"""Parallel multi-model collection service; no E4 or verdict logic is invoked."""
from __future__ import annotations

import asyncio
import inspect
import re
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any


def _model_slug(model: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")
    if not slug:
        raise ValueError("model ID cannot produce a trace slug")
    return slug


class MultiModelOrchestrator:
    """Dispatch one prompt to independent provider model calls and collect evidence."""

    def __init__(self, executor: Any) -> None:
        if not callable(getattr(executor, "execute", None)):
            raise ValueError("executor must expose execute(model, messages, max_tokens)")
        self._executor = executor

    async def _call_one(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> dict[str, Any]:
        value = await asyncio.to_thread(
            self._executor.execute, model, messages, max_tokens
        )
        if inspect.isawaitable(value):
            value = await value
        if not isinstance(value, dict):
            raise TypeError("provider executor returned a non-object result")
        return value

    async def execute(
        self,
        prompt: str,
        models: list[str],
        *,
        max_tokens: int,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Run model calls concurrently; preserve per-model failures and costs."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        if not isinstance(models, list) or not models:
            raise ValueError("models must be a non-empty list")
        if any(not isinstance(model, str) or not model.strip() for model in models):
            raise ValueError("each model must be a non-empty catalog model ID")
        if len(set(models)) != len(models):
            raise ValueError("models must be unique")
        if type(max_tokens) is not int or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        resolved_run_id = run_id or uuid.uuid4().hex
        if not isinstance(resolved_run_id, str) or not resolved_run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        slugs = [_model_slug(model) for model in models]
        if len(set(slugs)) != len(slugs):
            raise ValueError("model IDs must produce unique trace slugs")

        messages = [{"role": "user", "content": prompt}]
        calls = [
            self._call_one(model, messages, max_tokens)
            for model in models
        ]
        outcomes = await asyncio.gather(*calls, return_exceptions=True)

        results: list[dict[str, Any]] = []
        costs: list[Decimal] = []
        all_costs_known = True
        for model, slug, outcome in zip(models, slugs, outcomes, strict=True):
            trace_id = f"{resolved_run_id}_{slug}"
            if isinstance(outcome, BaseException):
                results.append({
                    "model": model,
                    "trace_id": trace_id,
                    "response": None,
                    "usage": None,
                    "cost": "UNKNOWN",
                    "error": {
                        "type": type(outcome).__name__,
                        "message": "Provider execution failed",
                    },
                })
                all_costs_known = False
                continue

            raw_cost = outcome.get("cost_estimate_rub", "UNKNOWN")
            cost: str = "UNKNOWN"
            if isinstance(raw_cost, (str, int, float)) and not isinstance(raw_cost, bool):
                try:
                    parsed_cost = Decimal(str(raw_cost))
                    if parsed_cost.is_finite() and parsed_cost >= 0:
                        cost = format(parsed_cost, "f")
                        costs.append(parsed_cost)
                    else:
                        all_costs_known = False
                except InvalidOperation:
                    all_costs_known = False
            else:
                all_costs_known = False
            if cost == "UNKNOWN":
                all_costs_known = False

            response = {
                "raw_body": outcome.get("raw_body"),
                "raw_body_sha256": outcome.get("raw_body_sha256"),
                "model_id": outcome.get("model_id"),
                "provider_response_id": outcome.get("provider_response_id"),
                "content": outcome.get("content"),
            }
            results.append({
                "model": model,
                "trace_id": trace_id,
                "response": response,
                "usage": outcome.get("usage"),
                "cost": cost,
                "error": outcome.get("error"),
            })

        total_cost = (
            format(sum(costs, Decimal("0")), "f")
            if all_costs_known and len(costs) == len(models)
            else "PARTIAL"
        )
        return {
            "run_id": resolved_run_id,
            "results": results,
            "total_cost_rub": total_cost,
        }
