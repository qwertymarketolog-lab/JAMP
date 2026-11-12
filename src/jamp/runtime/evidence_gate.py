from __future__ import annotations

import json
from pathlib import Path

CANONICAL_ARTIFACT_ID = 11369355096
CANONICAL_EVIDENCE_SHA256 = "7785cbd5ae19704473b385b8b21ddbdf7cd9eeb06aee56ce0f66e7da7592f1f1"
CANONICAL_MANIFEST_SHA256 = "e208f0e8565815020e5718191f61075f1eb95282052c75c4ca0a80ed07c12ed6"
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
EXPECTED_CAPABILITIES = tuple(f"C{i:02d}" for i in range(1, 11))
ALLOWED_RAW_STATUSES = frozenset({"VERIFIED", "CONTRADICTED", "INCONCLUSIVE"})


class EvidenceGate:
    def __init__(self, raw_evidence: dict) -> None:
        self._validate(raw_evidence)
        self.models = {m["model_id"]: m for m in raw_evidence["models"]}

    @classmethod
    def from_json_file(cls, path: str | Path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @staticmethod
    def _validate(doc: dict) -> None:
        if not isinstance(doc, dict):
            raise ValueError("Evidence document must be an object")
        if doc.get("contract_version") != "jamp-17-capability-v1":
            raise ValueError("Unsupported evidence contract")
        if (doc.get("expected_models"), doc.get("executed_models")) != (17, 17):
            raise ValueError("Canonical model cardinality is not 17")
        if (doc.get("expected_checks"), doc.get("executed_checks")) != (170, 170):
            raise ValueError("Canonical check cardinality is not 170")
        if doc.get("canonical_manifest_sha256") != CANONICAL_MANIFEST_SHA256:
            raise ValueError("Canonical manifest hash mismatch")
        if doc.get("frozen_core_blob") != FROZEN_CORE_BLOB:
            raise ValueError("Frozen Core evidence mismatch")

        models = doc.get("models")
        if not isinstance(models, list) or len(models) != 17:
            raise ValueError("Canonical models list is invalid")

        seen_model_ids: set[str] = set()
        for expected_ordinal, model in enumerate(models, start=1):
            if not isinstance(model, dict):
                raise ValueError("Canonical model entry is invalid")
            model_id = model.get("model_id")
            if not isinstance(model_id, str) or not model_id.strip():
                raise ValueError("Canonical model ID is missing")
            if model_id in seen_model_ids:
                raise ValueError("Duplicate canonical model ID")
            seen_model_ids.add(model_id)

            ordinal = model.get("ordinal")
            if type(ordinal) is not int or ordinal != expected_ordinal:
                raise ValueError("Canonical model ordinals are invalid")

            checks = model.get("checks")
            if not isinstance(checks, dict) or set(checks) != set(EXPECTED_CAPABILITIES):
                raise ValueError("Canonical model checks must be exactly C01-C10")
            for capability in EXPECTED_CAPABILITIES:
                check = checks[capability]
                if not isinstance(check, dict):
                    raise ValueError(f"Invalid raw check structure: {capability}")
                if check.get("raw_status") not in ALLOWED_RAW_STATUSES:
                    raise ValueError(f"Invalid raw status: {capability}")

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
