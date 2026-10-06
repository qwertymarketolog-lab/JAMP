from __future__ import annotations

import argparse
import json

from jamp.api.app import DEFAULT_EVIDENCE, _load_evidence
from jamp.runtime import (
    CapabilityResolver,
    EvidenceGate,
    ModelSelector,
    ProvenanceTracker,
    TaskClassifier,
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="jamp-run")
    parser.add_argument("--payload", required=True)
    args = parser.parse_args()
    payload = json.loads(args.payload)

    evidence = _load_evidence(DEFAULT_EVIDENCE)
    gate = EvidenceGate(
        {
            "contract_version": "jamp-17-capability-v1",
            "canonical_manifest_sha256": evidence["source"]["manifest_sha256"],
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
    task = classifier.classify(payload)
    required = resolver.get_required_capabilities(task)
    eligible = gate.get_eligible_models(required)
    action, selected = selector.select_model(eligible, task)
    trace = ProvenanceTracker().create_trace(task, required, action, selected, len(eligible))
    print(
        json.dumps(
            {
                "status": action,
                "task_profile": task,
                "required_capabilities": list(required),
                "selected_model": selected,
                "trace": trace,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
