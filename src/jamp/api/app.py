from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jamp.provider.anymodel import AnyModelChatExecutor, AnyModelError
from jamp.runtime import (
    AuditPersistence,
    CapabilityResolver,
    EvidenceGate,
    ModelSelector,
    ProvenanceTracker,
    TaskClassifier,
)

DEFAULT_EVIDENCE = Path(__file__).parents[3] / "tests/fixtures/runtime_evidence_projection.json"


def _load_evidence(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def create_app(
    evidence_path: str | Path = DEFAULT_EVIDENCE,
    executor: Callable[[str, dict[str, Any]], Any] | None = None,
    audit_storage_path: str | Path | None = None,
):
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("FastAPI is required for the API serving layer") from exc

    evidence = _load_evidence(evidence_path)
    source = evidence["source"]
    gate = EvidenceGate(
        {
            "contract_version": "jamp-17-capability-v1",
            "canonical_manifest_sha256": source["manifest_sha256"],
            "frozen_core_blob": evidence["frozen_core_blob"],
            "expected_models": 17,
            "executed_models": 17,
            "expected_checks": 170,
            "executed_checks": 170,
            "models": evidence["models"],
        }
    )
    classifier = TaskClassifier()
    resolver = CapabilityResolver()
    selector = ModelSelector()
    provenance = ProvenanceTracker()
    persistence = AuditPersistence(audit_storage_path)
    configured_executor = executor if executor is not None else AnyModelChatExecutor.from_env()

    app = FastAPI(title="JAMP API", version="v1", openapi_version="3.0.3")

    @app.post("/v1/classify")
    def classify(payload: dict[str, Any]):
        task_profile = classifier.classify(payload)
        required = resolver.get_required_capabilities(task_profile)
        return {"task_profile": task_profile, "required_capabilities": list(required)}

    @app.post("/v1/execute")
    def execute(payload: dict[str, Any]):
        request_id = payload.get("request_id")
        try:
            task_profile = classifier.classify(payload)
            required = resolver.get_required_capabilities(task_profile)
            eligible = gate.get_eligible_models(required)
            action, selected = selector.select_model(eligible, task_profile)
        except ValueError as exc:
            trace = provenance.create_trace(
                "unknown",
                (),
                "REFUSE",
                str(exc),
                0,
                request_id=request_id,
                refusal_reason="UNKNOWN_OR_UNSUPPORTED_TASK",
            )
            persistence.write_trace(trace)
            return JSONResponse(
                status_code=422,
                content={
                    "status": "REFUSE",
                    "reason": "UNKNOWN_OR_UNSUPPORTED_TASK",
                    "trace_id": trace["trace_id"],
                },
            )

        if action == "REFUSE":
            trace = provenance.create_trace(
                task_profile,
                required,
                action,
                selected,
                len(eligible),
                request_id=request_id,
                refusal_reason=selected,
            )
            persistence.write_trace(trace)
            return {
                "status": "REFUSE",
                "reason": selected,
                "trace_id": trace["trace_id"],
            }

        if configured_executor is None:
            reason = "PROVIDER_NOT_CONFIGURED"
            trace = provenance.create_trace(
                task_profile,
                required,
                "REFUSE",
                reason,
                len(eligible),
                request_id=request_id,
                refusal_reason=reason,
            )
            persistence.write_trace(trace)
            return JSONResponse(
                status_code=503,
                content={"status": "REFUSE", "reason": reason, "trace_id": trace["trace_id"]},
            )

        try:
            output = configured_executor(selected, payload)
        except Exception as exc:
            reason = (
                "PROVIDER_EXECUTION_FAILED"
                if isinstance(exc, AnyModelError)
                else "EXECUTOR_ERROR"
            )
            trace = provenance.create_trace(
                task_profile,
                required,
                "REFUSE",
                reason,
                len(eligible),
                request_id=request_id,
                refusal_reason=reason,
            )
            persistence.write_trace(trace)
            return JSONResponse(
                status_code=502,
                content={"status": "REFUSE", "reason": reason, "trace_id": trace["trace_id"]},
            )

        trace = provenance.create_trace(
            task_profile,
            required,
            action,
            selected,
            len(eligible),
            output=output,
            request_id=request_id,
        )
        persistence.write_trace(trace)
        response = {
            "status": "EXECUTE",
            "selected_model": selected,
            "trace_id": trace["trace_id"],
        }
        if output is not None:
            response["output"] = output
        return response

    @app.get("/v1/provenance/{trace_id}")
    def get_provenance(trace_id: str):
        trace = persistence.read_trace_by_id(trace_id)
        if trace is None:
            return JSONResponse(status_code=404, content={"detail": "Trace not found"})
        return trace

    return app
