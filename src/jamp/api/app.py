from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from jamp.runtime import (
    CapabilityResolver,
    EvidenceGate,
    ModelSelector,
    ProvenanceTracker,
    TaskClassifier,
)


DEFAULT_EVIDENCE = Path(__file__).parents[3] / "tests" / "fixtures" / "runtime_evidence_projection.json"


def _load_evidence(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def create_app(
    evidence_path: str | Path = DEFAULT_EVIDENCE,
    executor: Callable[[str, dict[str, Any]], Any] | None = None,
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
    traces: dict[str, dict[str, Any]] = {}

    app = FastAPI(title="JAMP API", version="v1", openapi_version="3.0.3")

    @app.post("/v1/classify")
    def classify(payload: dict[str, Any]):
        task_profile = classifier.classify(payload)
        required = resolver.get_required_capabilities(task_profile)
        return {"task_profile": task_profile, "required_capabilities": list(required)}

    @app.post("/v1/execute")
    def execute(payload: dict[str, Any]):
        try:
            task_profile = classifier.classify(payload)
            required = resolver.get_required_capabilities(task_profile)
            eligible = gate.get_eligible_models(required)
            action, selected = selector.select_model(eligible, task_profile)
        except ValueError as exc:
            return JSONResponse(status_code=422, content={"status": "REFUSE", "reason": str(exc)})

        if action == "REFUSE":
            trace = provenance.create_trace(task_profile, required, action, selected, len(eligible))
            traces[trace["trace_id"]] = trace
            return {"status": "REFUSE", "reason": selected, "trace_id": trace["trace_id"]}

        output = executor(selected, payload) if executor is not None else None
        trace = provenance.create_trace(
            task_profile, required, action, selected, len(eligible), output=output
        )
        traces[trace["trace_id"]] = trace
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
        trace = traces.get(trace_id)
        if trace is None:
            return JSONResponse(status_code=404, content={"detail": "Trace not found"})
        return trace

    return app
