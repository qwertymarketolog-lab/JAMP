"""Research vectors for EXP-23 AI/harness provenance."""

from __future__ import annotations

from copy import deepcopy

from tests.research.exp23.ai_harness_observation import (
    build_observation,
    observation_digest,
)

BASE_RECORD = {
    "source_ref": "fixture:ai:001",
    "model_id": "model-a",
    "model_version": "v1",
    "harness": {
        "harness_id": "harness-a",
        "harness_version": "v1",
        "tools": ["search", "calculator"],
        "policy": "observe-only",
    },
    "attempt_index": 0,
    "input_payload": {"task": "classify", "text": "alpha"},
    "output_payload": {"candidate": "A", "confidence": 0.8},
    "provenance": {"input_hash": "input-001", "run_id": "run-001"},
}


def test_identical_execution_context_is_deterministic() -> None:
    first = build_observation(BASE_RECORD)
    second = build_observation(deepcopy(BASE_RECORD))
    assert first == second
    assert first.observation_id == first.immutable_hash


def test_harness_identity_changes_observation() -> None:
    baseline = build_observation(BASE_RECORD)
    changed = deepcopy(BASE_RECORD)
    changed["harness"]["harness_id"] = "harness-b"
    assert build_observation(changed).immutable_hash != baseline.immutable_hash


def test_tool_surface_changes_observation() -> None:
    baseline = build_observation(BASE_RECORD)
    changed = deepcopy(BASE_RECORD)
    changed["harness"]["tools"] = ["search"]
    assert build_observation(changed).immutable_hash != baseline.immutable_hash


def test_model_identity_changes_observation() -> None:
    baseline = build_observation(BASE_RECORD)
    changed = deepcopy(BASE_RECORD)
    changed["model_version"] = "v2"
    assert build_observation(changed).immutable_hash != baseline.immutable_hash


def test_attempt_index_binds_retry_history() -> None:
    first = build_observation(BASE_RECORD)
    changed = deepcopy(BASE_RECORD)
    changed["attempt_index"] = 1
    retry = build_observation(changed)
    assert first.immutable_hash != retry.immutable_hash


def test_provenance_binds_observation_to_run() -> None:
    baseline = build_observation(BASE_RECORD)
    changed = deepcopy(BASE_RECORD)
    changed["provenance"]["run_id"] = "run-002"
    assert build_observation(changed).immutable_hash != baseline.immutable_hash


def test_output_change_is_observable() -> None:
    baseline = build_observation(BASE_RECORD)
    changed = deepcopy(BASE_RECORD)
    changed["output_payload"]["candidate"] = "B"
    assert build_observation(changed).immutable_hash != baseline.immutable_hash


def test_digest_binds_full_execution_envelope() -> None:
    observation = build_observation(BASE_RECORD)
    assert observation.immutable_hash == observation_digest(
        source_ref=observation.source_ref,
        model_id=observation.model_id,
        model_version=observation.model_version,
        harness=observation.harness,
        attempt_index=observation.attempt_index,
        input_payload=observation.input_payload,
        output_payload=observation.output_payload,
        provenance=observation.provenance,
    )


def test_observation_contains_no_semantic_verdict() -> None:
    observation = build_observation(BASE_RECORD)
    forbidden = {"SUPPORTED", "REJECTED", "INCONCLUSIVE"}
    assert not forbidden.intersection(observation.output_payload)
    assert not forbidden.intersection(observation.provenance)
