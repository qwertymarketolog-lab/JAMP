import json

import pytest

from src.jamp.runtime.router import CapabilityRouter, TaskSpec


def test_execute_selects_deterministically_from_verified_evidence(tmp_path):
    matrix = {
        "schema_version": "jamp-task-scoped-derived-matrix-v2",
        "evidence_anchor": {"artifact_id": 123, "artifact_sha256": "sha256:test"},
        "frozen_core": {"blob": "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"},
        "source_contract": {
            "expected_models": 17,
            "executed_models": 17,
            "expected_checks": 170,
            "executed_checks": 170,
        },
        "task_profiles": {"tool_execution_agent": {"required_capabilities": ["C02", "C05"]}},
        "matrix": [
            {
                "model_id": "z-model",
                "capabilities": {"C02": "VERIFIED", "C05": "VERIFIED"},
            },
            {
                "model_id": "a-model",
                "capabilities": {"C02": "VERIFIED", "C05": "VERIFIED"},
            },
        ],
    }
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(matrix), encoding="utf-8")

    decision = CapabilityRouter(path).route_task(
        TaskSpec("tool_execution_agent", "VERIFIED")
    )

    assert decision.status == "EXECUTE"
    assert decision.selected_model == "a-model"
    assert decision.evidence_trace["candidate_models"] == ["a-model", "z-model"]
    assert decision.evidence_trace["evidence_anchor"]["artifact_id"] == 123


@pytest.mark.parametrize("status", ["CONTRADICTED", "INCONCLUSIVE"])
def test_non_verified_capability_refuses(tmp_path, status):
    matrix = _matrix_with_status(status, "C05")
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(matrix), encoding="utf-8")

    decision = CapabilityRouter(path).route_task(
        TaskSpec("tool_execution_agent", "VERIFIED")
    )

    assert decision.status == "REFUSE"
    assert decision.selected_model is None
    assert decision.evidence_trace["decision_reason"] == "INSUFFICIENT_EVIDENCE"


def test_missing_capability_refuses(tmp_path):
    matrix = _matrix_with_status(None, "C05")
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(matrix), encoding="utf-8")

    decision = CapabilityRouter(path).route_task(
        TaskSpec("tool_execution_agent", "VERIFIED")
    )

    assert decision.status == "REFUSE"


def test_latency_bound_refuses_without_latency_evidence(tmp_path):
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(_base_matrix()), encoding="utf-8")

    decision = CapabilityRouter(path).route_task(
        TaskSpec("tool_execution_agent", "VERIFIED", max_latency=250)
    )

    assert decision.status == "REFUSE"
    assert decision.evidence_trace["decision_reason"] == "LATENCY_EVIDENCE_UNAVAILABLE"


def test_unknown_task_and_confidence_fail_closed(tmp_path):
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(_base_matrix()), encoding="utf-8")

    unknown = CapabilityRouter(path).route_task(TaskSpec("unknown", "VERIFIED"))
    assert unknown.status == "REFUSE"

    unsupported = CapabilityRouter(path).route_task(
        TaskSpec("tool_execution_agent", "LIKELY")
    )
    assert unsupported.status == "REFUSE"
    assert unsupported.evidence_trace["decision_reason"] == "UNSUPPORTED_CONFIDENCE_CONTRACT"


def test_matrix_integrity_is_required(tmp_path):
    matrix = _base_matrix()
    matrix["source_contract"]["executed_checks"] = 169
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(matrix), encoding="utf-8")

    with pytest.raises(ValueError, match="check cardinality"):
        CapabilityRouter(path).route_task(TaskSpec("tool_execution_agent", "VERIFIED"))


def _base_matrix():
    return {
        "schema_version": "jamp-task-scoped-derived-matrix-v2",
        "evidence_anchor": {"artifact_id": 123, "artifact_sha256": "sha256:test"},
        "frozen_core": {"blob": "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"},
        "source_contract": {
            "expected_models": 17,
            "executed_models": 17,
            "expected_checks": 170,
            "executed_checks": 170,
        },
        "task_profiles": {"tool_execution_agent": {"required_capabilities": ["C02", "C05"]}},
        "matrix": [
            {
                "model_id": "model-a",
                "capabilities": {"C02": "VERIFIED", "C05": "VERIFIED"},
            }
        ],
    }


def _matrix_with_status(status, capability):
    matrix = _base_matrix()
    matrix["matrix"][0]["capabilities"][capability] = status
    return matrix
