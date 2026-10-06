from __future__ import annotations

import json
from pathlib import Path

CAPABILITY_MAP = {
    "search_and_extraction": ("C01", "C06"),
    "tool_execution_agent": ("C02", "C05"),
    "long_context_analysis": ("C03", "C08"),
    "strict_compliance_safety": ("C04", "C07", "C09"),
}

_MATRIX_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "research"
    / "jamp_task_scoped_derived_matrix_v2.json"
)


def _load_derived_matrix() -> dict:
    with _MATRIX_PATH.open(encoding="utf-8") as handle:
        matrix = json.load(handle)
    if matrix.get("schema_version") != "jamp-task-scoped-derived-matrix-v2":
        raise ValueError("Unsupported task-scoped capability matrix")
    if matrix.get("evidence_anchor", {}).get("artifact_id") != 11369355096:
        raise ValueError("Unexpected capability evidence anchor")
    if matrix.get("frozen_core", {}).get("blob") != "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a":
        raise ValueError("Frozen Core anchor mismatch")
    return matrix


class CapabilityResolver:
    def get_required_capabilities(self, task_profile: str) -> tuple[str, ...]:
        try:
            return CAPABILITY_MAP[task_profile]
        except KeyError as exc:
            raise ValueError(f"Unknown task profile: {task_profile}") from exc

    def get_eligible_models(self, task_profile: str) -> tuple[str, ...]:
        self.get_required_capabilities(task_profile)
        matrix = _load_derived_matrix()
        try:
            models = matrix["task_profiles"][task_profile]["eligible_models"]
        except KeyError as exc:
            raise ValueError(f"Unknown task profile: {task_profile}") from exc
        return tuple(models)
