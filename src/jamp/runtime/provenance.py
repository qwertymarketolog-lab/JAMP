from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
EVIDENCE_SHA256 = "7785cbd5ae19704473b385b8b21ddbdf7cd9eeb06aee56ce0f66e7da7592f1f1"
AUDIT_TRACE_SCHEMA_VERSION = "jamp-audit-trace-v0.2"


def validate_audit_trace(trace: dict[str, Any]) -> None:
    schema_ver = trace.get("schema_version")
    if schema_ver not in ("jamp-audit-trace-v0.1", "jamp-audit-trace-v0.2"):
        raise ValueError("AuditTrace schema_version contract violation")

    if schema_ver == "jamp-audit-trace-v0.2" and trace.get("status") == "EXECUTE":
        details = trace.get("execution_details", {})
        if details.get("provider") == "openrouter" and details.get("evidence_status") != "VERIFIED":
            raise ValueError("OpenRouter EXECUTE requires evidence_status == 'VERIFIED'")


class ProvenanceTracker:
    @staticmethod
    def output_digest(output: Any) -> str:
        payload = json.dumps(
            output,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    def create_trace(
        self,
        task_profile: str,
        required_caps: tuple[str, ...],
        action: str,
        selected_model: str,
        eligible_count: int,
        output: Any = None,
        request_id: str | None = None,
        refusal_reason: str | None = None,
        failure_diagnostics: dict[str, Any] | None = None,
        evidence_status: str | None = None,
        evidence_details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        trace = {
            "schema_version": AUDIT_TRACE_SCHEMA_VERSION,
            "trace_id": f"trace_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id or f"req_{uuid.uuid4().hex[:8]}",
            "status": action,
            "task_profile": task_profile,
            "required_capabilities": list(required_caps),
            "gate_evaluator": {
                "evidence_base_sha256": EVIDENCE_SHA256,
                "eligible_models_count": eligible_count,
            },
            "evidence_hashes": {
                "raw_artifact_sha256": EVIDENCE_SHA256,
            },
            "frozen_core_state": {
                "blob": FROZEN_CORE_BLOB,
                "delta": 0,
            },
            "frozen_core": {
                "path": "src/jamp/run.py",
                "blob": FROZEN_CORE_BLOB,
                "delta": 0,
            },
        }
        if action == "EXECUTE":
            execution_details = {"selected_model": selected_model}
            if evidence_status is not None:
                execution_details["evidence_status"] = evidence_status
            if isinstance(evidence_details, dict):
                safe_evidence_details: dict[str, Any] = {}
                for key in (
                    "reason",
                    "error",
                    "provider_model",
                    "provider_name",
                    "generation_id",
                    "jamp_model",
                ):
                    value = evidence_details.get(key)
                    if isinstance(value, str) and value:
                        safe_evidence_details[key] = value
                if safe_evidence_details:
                    execution_details["evidence_details"] = safe_evidence_details
            if isinstance(output, dict):
                for key in (
                    "provider",
                    "requested_model_id",
                    "provider_requested_model_id",
                    "provider_model_id",
                    "provider_response_id",
                    "crosswalk_digest",
                ):
                    value = output.get(key)
                    if isinstance(value, str) and value:
                        execution_details[key] = value
                test_override = output.get("test_override")
                execution_details["test_override"] = (
                    test_override if isinstance(test_override, bool) else "UNKNOWN"
                )
                qualification = output.get("qualification")
                execution_details["qualification"] = (
                    qualification if isinstance(qualification, str) and qualification else "UNKNOWN"
                )
            if isinstance(output, dict) and output.get("test_only") is True:
                execution_details["test_only"] = True
            if output is not None:
                execution_details["output_digest"] = self.output_digest(output)
            trace["execution_details"] = execution_details
        else:
            reason = refusal_reason or "FAIL_CLOSED_ZERO_QUALIFIED_MODELS"
            trace["refusal_details"] = {
                "reason": reason,
                "message": (
                    f"Execution refused: {reason}."
                    if refusal_reason
                    else f"Execution blocked: no model satisfies {list(required_caps)}."
                ),
            }
            if isinstance(failure_diagnostics, dict):
                diagnostics: dict[str, Any] = {}
                for k in (
                    "evidence_status",
                    "reason",
                    "error",
                    "provider_model",
                    "generation_id",
                    "jamp_model",
                    "provider_name",
                ):
                    if k in failure_diagnostics:
                        diagnostics[k] = failure_diagnostics[k]
                for key in (
                    "code",
                    "finish_reason",
                    "model",
                    "selected_model",
                    "requested_model_id",
                    "crosswalk_digest",
                ):
                    value = failure_diagnostics.get(key)
                    if isinstance(value, str) and value:
                        diagnostics[key] = value
                    elif key == "finish_reason" and key in failure_diagnostics and value is None:
                        diagnostics[key] = None
                usage = failure_diagnostics.get("usage")
                if isinstance(usage, dict):
                    diagnostics["usage"] = usage
                for key in ("content_len", "reasoning_len", "requested_max_tokens"):
                    value = failure_diagnostics.get(key)
                    if type(value) is int and value >= 0:
                        diagnostics[key] = value
                if diagnostics:
                    trace["refusal_details"]["provider_diagnostics"] = diagnostics
        validate_audit_trace(trace)
        return trace
