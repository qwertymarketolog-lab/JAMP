from __future__ import annotations

import json
from pathlib import Path

CANONICAL_ARTIFACT_ID = 11369355096
CANONICAL_EVIDENCE_SHA256 = "7785cbd5ae19704473b385b8b21ddbdf7cd9eeb06aee56ce0f66e7da7592f1f1"
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"


class EvidenceGate:
    def __init__(self, raw_evidence: dict) -> None:
        self._validate(raw_evidence)
        self.models = {m["model_id"]: m for m in raw_evidence["models"]}

    @classmethod
    def from_json_file(cls, path: str | Path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @staticmethod
    def _validate(doc: dict) -> None:
        if doc.get("contract_version") != "jamp-17-capability-v1":
            raise ValueError("Unsupported evidence contract")
        if (doc.get("expected_models"), doc.get("executed_models")) != (17, 17):
            raise ValueError("Canonical model cardinality is not 17")
        if (doc.get("expected_checks"), doc.get("executed_checks")) != (170, 170):
            raise ValueError("Canonical check cardinality is not 170")
        if not doc.get("canonical_manifest_sha256"):
            raise ValueError("Missing canonical manifest hash")
        if doc.get("frozen_core_blob") != FROZEN_CORE_BLOB:
            raise ValueError("Frozen Core evidence mismatch")
        if not isinstance(doc.get("models"), list) or len(doc["models"]) != 17:
            raise ValueError("Canonical models list is invalid")

    def evaluate_model(self, model_id: str, required_capabilities) -> bool:
        model = self.models.get(model_id)
        return model is not None and all(
            model.get("checks", {}).get(capability, {}).get("raw_status") == "VERIFIED"
            for capability in required_capabilities
        )

    def get_eligible_models(self, required_capabilities) -> list[str]:
        return [
            model_id
            for model_id in self.models
            if self.evaluate_model(model_id, required_capabilities)
        ]
