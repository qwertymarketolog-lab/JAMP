"""Authenticated Arena HTTP endpoint, deliberately separate from E4 verification."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from jamp.api.auth import OrganizationContext, require_api_key
from jamp.db.arena import (
    ArenaIdempotencyConflict,
    complete_arena_run,
    reserve_arena_run,
)
from jamp.runtime.orchestrator import MultiModelOrchestrator


def create_arena_router(
    orchestrator: MultiModelOrchestrator | None,
) -> APIRouter:
    router = APIRouter(tags=["JAMP Arena"])

    @router.post("/v1/arena/run")
    async def run_arena(
        payload: dict[str, Any],
        organization: OrganizationContext = Depends(require_api_key),  # noqa: B008
    ):
        """Run a bounded model comparison; agreement is not an evidence verdict."""
        if set(payload) != {"prompt", "models", "idempotency_key"}:
            return JSONResponse(
                status_code=422,
                content={
                    "detail": (
                        "prompt, models and idempotency_key are required; "
                        "extra fields are forbidden"
                    )
                },
            )
        prompt = payload.get("prompt")
        models = payload.get("models")
        idempotency_key = payload.get("idempotency_key")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20_000:
            return JSONResponse(
                status_code=422,
                content={"detail": "prompt must contain 1 to 20000 characters"},
            )
        if (
            not isinstance(models, list)
            or not 1 <= len(models) <= 5
            or any(
                not isinstance(model, str) or not model.strip() or len(model) > 128
                for model in models
            )
            or len(set(models)) != len(models)
        ):
            return JSONResponse(
                status_code=422,
                content={"detail": "models must contain 1 to 5 unique non-empty model IDs"},
            )
        if (
            not isinstance(idempotency_key, str)
            or not idempotency_key.strip()
            or len(idempotency_key) > 128
        ):
            return JSONResponse(
                status_code=422,
                content={"detail": "idempotency_key must contain 1 to 128 characters"},
            )
        if orchestrator is None:
            return JSONResponse(
                status_code=503,
                content={"status": "REFUSE", "reason": "ARENA_PROVIDER_NOT_CONFIGURED"},
            )

        try:
            reservation, created = reserve_arena_run(
                organization_id=organization.org_id,
                idempotency_key=idempotency_key,
                prompt=prompt,
                models=models,
            )
        except ArenaIdempotencyConflict:
            return JSONResponse(
                status_code=409,
                content={
                    "status": "REFUSE",
                    "reason": "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_REQUEST",
                },
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "REFUSE", "reason": "ARENA_PERSISTENCE_UNAVAILABLE"},
            )

        run_id = reservation["run_id"]
        if not created:
            cached = {
                "run_id": run_id,
                "status": reservation["status"],
                "results": reservation["results"],
            }
            if reservation["status"] == "RUNNING":
                return JSONResponse(status_code=202, content=cached)
            return cached

        try:
            execution = await orchestrator.execute(
                prompt,
                models,
                max_tokens=1024,
                run_id=run_id,
            )
        except Exception:
            # A durable RUNNING reservation prevents a retry from spending again.
            return JSONResponse(
                status_code=502,
                content={
                    "run_id": run_id,
                    "status": "RUNNING",
                    "reason": "ARENA_EXECUTION_INTERRUPTED",
                },
            )

        results = []
        for item in execution["results"]:
            response = item.get("response")
            response = response if isinstance(response, dict) else {}
            error = item.get("error")
            content = response.get("content")
            failed = error is not None or not isinstance(content, str)
            if failed and error is None:
                error = {"type": "InvalidResponse", "message": "Provider returned no text response"}
            results.append(
                {
                    "model": item["model"],
                    "execution_status": "FAILED" if failed else "COMPLETED",
                    "evidence_verdict": "UNKNOWN",
                    "raw_response": content,
                    "raw_response_sha256": response.get("raw_body_sha256"),
                    "trace_id": item["trace_id"],
                    "cost_estimate_rub": item.get("cost", "UNKNOWN"),
                    "error": error,
                }
            )

        # PARTIAL is an execution outcome only. E4 is intentionally not invoked.
        status = (
            "PARTIAL"
            if any(result["execution_status"] == "FAILED" for result in results)
            else "COMPLETED"
        )
        try:
            complete_arena_run(
                organization_id=organization.org_id,
                run_id=run_id,
                status=status,
                results=results,
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={
                    "run_id": run_id,
                    "status": "RUNNING",
                    "reason": "ARENA_PERSISTENCE_UNAVAILABLE",
                },
            )
        return {"run_id": run_id, "status": status, "results": results}

    return router
