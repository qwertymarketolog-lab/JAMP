from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
EVIDENCE_SHA256 = "7785cbd5ae19704473b385b8b21ddbdf7cd9eeb06aee56ce0f66e7da7592f1f1"


class ProvenanceTracker:
    @staticmethod
    def output_digest(output):
        payload = json.dumps(
            output,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    def create_trace(
        self,
        task_profile,
        required_caps,
        action,
        selected_model,
        eligible_count,
        output=None,
    ):
        trace = {
            "trace_id": f"trace_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now(UTC).isoformat(),
            "status": action,
            "task_profile": task_profile,
            "required_capabilities": list(required_caps),
            "gate_evaluator": {
                "evidence_base_sha256": EVIDENCE_SHA256,
                "eligible_models_count": eligible_count,
            },
            "frozen_core_state": {
                "blob": FROZEN_CORE_BLOB,
                "delta": 0,
            },
        }
        if action == "EXECUTE":
            trace["execution_details"] = {"selected_model": selected_model}
            if output is not None:
                trace["execution_details"]["output_digest"] = self.output_digest(output)
        else:
            trace["refusal_details"] = {
                "reason": "FAIL_CLOSED_ZERO_QUALIFIED_MODELS",
                "message": f"Execution blocked: no model satisfies {list(required_caps)}.",
            }
        return trace
