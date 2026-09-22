from __future__ import annotations

from research.exp21.phase2_contract import (
    ALPHA,
    EXPERIMENT_ID,
    PHASE,
    REQUIRED_PAIRS,
    WORKLOAD_DEFINITION_HASH,
    WORKLOAD_SPEC_ID,
    validate_artifact,
    validate_observation,
)


def _observation(condition: str, pair_id: str = "p01") -> dict[str, object]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "phase": PHASE,
        "pair_id": pair_id,
        "condition": condition,
        "target_commit": "a" * 40,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "experiment_seed": 21,
        "timestamp": "2026-09-22T00:00:00Z",
        "runner_name": "runner-1",
        "runner_os": "Linux",
        "runner_arch": "x86_64",
        "kernel": "test-kernel",
        "python_version": "3.11",
        "cpu_count_visible": 2,
        "cpu_affinity_before": [0, 1],
        "cpu_affinity_after": [0, 1],
        "affinity_verified": True,
        "wall_ms": 10.0,
        "cpu_ms": 9.0,
        "non_cpu_delta_ms": 1.0,
        "gc_enabled": True,
        "gc_gen2_collections": 0,
    }


def test_control_observation_validates() -> None:
    observation = _observation("CONTROL")
    assert (
        validate_observation(
            observation,
            expected_target_commit="a" * 40,
        )
        == []
    )


def test_treatment_requires_observed_single_cpu_affinity() -> None:
    observation = _observation("CPU_AFFINITY")
    observation["cpu_affinity_after"] = [0]
    assert validate_observation(
        observation,
        expected_target_commit="a" * 40,
    ) == []


def test_treatment_rejects_unverified_affinity() -> None:
    observation = _observation("CPU_AFFINITY")
    observation["cpu_affinity_after"] = [0]
    observation["affinity_verified"] = False
    errors = validate_observation(
        observation,
        expected_target_commit="a" * 40,
    )
    assert "affinity_not_verified" in errors


def test_artifact_fails_closed_below_required_n() -> None:
    artifact = {
        "observations": [_observation("CONTROL"), _observation("CPU_AFFINITY")],
        "n_pairs": 1,
        "wilcoxon_p": 0.5,
        "alpha": ALPHA,
        "median_delta_ms": 0.1,
        "status": "INCONCLUSIVE",
    }
    valid, errors = validate_artifact(
        artifact,
        expected_target_commit="a" * 40,
    )
    assert not valid
    assert any("valid_pair_count" in error for error in errors)


def test_required_pair_count_is_contractual() -> None:
    assert REQUIRED_PAIRS == 30
