from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
MATRIX_SCHEMA = "jamp-task-scoped-derived-matrix-v2"
MATRIX_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "research"
    / "jamp_task_scoped_derived_matrix_v2.json"
)


@dataclass(frozen=True)
class TaskSpec:
    task_type: str
    required_confidence: str
    max_latency: float | None = None


@dataclass(frozen=True)
class RoutingDecision:
    status: str
    selected_model: str | None
    evidence_trace: dict[str, Any]


class CapabilityRouter:
    """Deterministic, evidence-backed, fail-closed task router."""

    def __init__(self, matrix_path: str | Path = MATRIX_PATH) -> None:
        self._matrix_path = Path(matrix_path)

    def route_task(self, task_spec: TaskSpec) -> RoutingDecision:
        matrix = self._load_matrix()
        profiles = matrix["task_profiles"]

        if task_spec.task_type not in profiles:
            return self._refuse(
                task_spec,
                matrix,
                "UNKNOWN_TASK_PROFILE",
                required_capabilities=[],
                candidates=[],
            )

        required = tuple(profiles[task_spec.task_type]["required_capabilities"])

        if task_spec.required_confidence != "VERIFIED":
            return self._refuse(
                task_spec,
                matrix,
                "UNSUPPORTED_CONFIDENCE_CONTRACT",
                required_capabilities=required,
                candidates=[],
            )

        if task_spec.max_latency is not None:
            return self._refuse(
                task_spec,
                matrix,
                "LATENCY_EVIDENCE_UNAVAILABLE",
                required_capabilities=required,
                candidates=[],
            )

        candidates = self._eligible_models(matrix, required)
        if not candidates:
            return self._refuse(
                task_spec,
                matrix,
                "INSUFFICIENT_EVIDENCE",
                required_capabilities=required,
                candidates=[],
            )

        selected = candidates[0]
        return RoutingDecision(
            status="EXECUTE",
            selected_model=selected,
            evidence_trace=self._trace(
                task_spec,
                matrix,
                required,
                candidates,
                reason="ALL_REQUIRED_CAPABILITIES_VERIFIED",
            ),
        )

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("Capability evidence matrix must be an object")
        return data

    def _load_matrix(self) -> dict[str, Any]:
        matrix = self._load_json(self._matrix_path)
        if matrix.get("schema_version") != MATRIX_SCHEMA:
            raise ValueError("Unsupported capability evidence matrix")
        source = matrix.get("source_contract", {})
        if (source.get("expected_models"), source.get("executed_models")) != (
            17,
            17,
        ):
            raise ValueError("Capability evidence model cardinality mismatch")
        if (source.get("expected_checks"), source.get("executed_checks")) != (
            170,
            170,
        ):
            raise ValueError("Capability evidence check cardinality mismatch")
        if matrix.get("frozen_core", {}).get("blob") != FROZEN_CORE_BLOB:
            raise ValueError("Frozen Core evidence mismatch")
        return matrix

    @staticmethod
    def _eligible_models(matrix: dict[str, Any], required: tuple[str, ...]) -> list[str]:
        eligible: list[str] = []
        for row in matrix.get("matrix", []):
            model_id = row.get("model_id")
            capabilities = row.get("capabilities", {})
            if not isinstance(model_id, str) or not isinstance(capabilities, dict):
                continue
            if all(capabilities.get(capability) == "VERIFIED" for capability in required):
                eligible.append(model_id)
        return sorted(eligible)

    @staticmethod
    def _trace(
        task_spec: TaskSpec,
        matrix: dict[str, Any],
        required: tuple[str, ...],
        candidates: list[str],
        reason: str,
    ) -> dict[str, Any]:
        return {
            "contract_version": "jamp-capability-router-v0.1",
            "task_type": task_spec.task_type,
            "required_confidence": task_spec.required_confidence,
            "required_capabilities": list(required),
            "decision_reason": reason,
            "candidate_models": list(candidates),
            "evidence_anchor": dict(matrix["evidence_anchor"]),
            "evidence_schema": matrix["schema_version"],
            "frozen_core": {
                "path": "src/jamp/run.py",
                "blob": FROZEN_CORE_BLOB,
                "delta": 0,
            },
        }

    @classmethod
    def _refuse(
        cls,
        task_spec: TaskSpec,
        matrix: dict[str, Any],
        reason: str,
        required_capabilities: list[str] | tuple[str, ...],
        candidates: list[str],
    ) -> RoutingDecision:
        return RoutingDecision(
            status="REFUSE",
            selected_model=None,
            evidence_trace=cls._trace(
                task_spec,
                matrix,
                tuple(required_capabilities),
                candidates,
                reason=reason,
            ),
        )


__all__ = ["CapabilityRouter", "RoutingDecision", "TaskSpec"]
