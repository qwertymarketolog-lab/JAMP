"""Fail-closed validation for EXP-21 Phase 2 evidence."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

EXPERIMENT_ID = "EXP-21-PHASE2-SCHEDULING-V1"
PHASE = 2
WORKLOAD_SPEC_ID = "EXP-21-PHASE0-G4-CANONICAL-V1"
WORKLOAD_DEFINITION_HASH = (
    "f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
)
ALPHA = 0.01
REQUIRED_PAIRS = 30
CONDITIONS = {"CONTROL", "CPU_AFFINITY"}


def validate_observation(
    observation: dict[str, Any],
    *,
    expected_target_commit: str,
) -> list[str]:
    """Return validation errors; an empty list means valid observation."""
    errors: list[str] = []

    if observation.get("experiment_id") != EXPERIMENT_ID:
        errors.append("experiment_id_mismatch")
    if observation.get("phase") != PHASE:
        errors.append("phase_mismatch")
    if not expected_target_commit:
        errors.append("expected_target_commit_missing")
    elif observation.get("target_commit") != expected_target_commit:
        errors.append("target_commit_mismatch")

    if observation.get("workload_spec_id") != WORKLOAD_SPEC_ID:
        errors.append("workload_spec_id_mismatch")
    if observation.get("workload_definition_hash") != WORKLOAD_DEFINITION_HASH:
        errors.append("workload_definition_hash_mismatch")

    if not observation.get("experiment_seed"):
        errors.append("experiment_seed_missing")
    if not observation.get("pair_id"):
        errors.append("pair_id_missing")
    if observation.get("condition") not in CONDITIONS:
        errors.append("condition_invalid")

    for field in (
        "timestamp",
        "runner_name",
        "runner_os",
        "runner_arch",
        "kernel",
        "python_version",
        "cpu_count_visible",
        "cpu_affinity_before",
        "cpu_affinity_after",
        "wall_ms",
        "cpu_ms",
        "non_cpu_delta_ms",
        "gc_enabled",
        "gc_gen2_collections",
    ):
        if field not in observation:
            errors.append(f"{field}_missing")

    if not observation.get("affinity_verified"):
        errors.append("affinity_not_verified")

    for field in ("wall_ms", "cpu_ms", "non_cpu_delta_ms"):
        value = observation.get(field)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            errors.append(f"{field}_invalid")

    if observation.get("condition") == "CPU_AFFINITY":
        before = observation.get("cpu_affinity_before")
        after = observation.get("cpu_affinity_after")
        if not isinstance(after, (list, tuple)) or len(after) != 1:
            errors.append("treatment_affinity_not_single_cpu")
        if before == after:
            errors.append("treatment_affinity_not_changed")

    return errors


def validate_artifact(
    artifact: dict[str, Any],
    *,
    expected_target_commit: str,
) -> tuple[bool, list[str]]:
    """Validate the complete Phase 2 artifact without repairing evidence."""
    errors: list[str] = []

    observations = artifact.get("observations")
    if not isinstance(observations, list):
        return False, ["observations_missing_or_not_list"]

    pair_ids = [item.get("pair_id") for item in observations if isinstance(item, dict)]
    duplicates = [pair_id for pair_id, count in Counter(pair_ids).items() if pair_id and count > 2]
    if duplicates:
        errors.append("duplicate_pair_observation")

    by_pair: dict[str, list[dict[str, Any]]] = {}
    for observation in observations:
        if not isinstance(observation, dict):
            errors.append("observation_not_object")
            continue
        obs_errors = validate_observation(
            observation,
            expected_target_commit=expected_target_commit,
        )
        if obs_errors:
            errors.extend(
                f"pair_{observation.get('pair_id', 'UNKNOWN')}:{item}"
                for item in obs_errors
            )
            continue
        by_pair.setdefault(str(observation["pair_id"]), []).append(observation)

    valid_pairs = 0
    for pair_id, pair in by_pair.items():
        conditions = {item["condition"] for item in pair}
        if len(pair) != 2 or conditions != CONDITIONS:
            errors.append(f"pair_{pair_id}:incomplete_or_invalid_conditions")
            continue
        valid_pairs += 1

    if valid_pairs != REQUIRED_PAIRS:
        errors.append(f"valid_pair_count={valid_pairs};required={REQUIRED_PAIRS}")

    for field in ("n_pairs", "wilcoxon_p", "alpha", "median_delta_ms", "status"):
        if field not in artifact:
            errors.append(f"artifact_{field}_missing")

    if artifact.get("n_pairs") != REQUIRED_PAIRS:
        errors.append("artifact_n_pairs_mismatch")
    if artifact.get("alpha") != ALPHA:
        errors.append("artifact_alpha_mismatch")

    p_value = artifact.get("wilcoxon_p")
    if not isinstance(p_value, (int, float)) or not math.isfinite(p_value):
        errors.append("artifact_wilcoxon_p_invalid")

    if not isinstance(artifact.get("median_delta_ms"), (int, float)):
        errors.append("artifact_median_delta_invalid")

    status = artifact.get("status")
    if status not in {
        "SCHEDULING_EFFECT_SUPPORTED",
        "SCHEDULING_EFFECT_NOT_SUPPORTED",
        "INCONCLUSIVE",
    }:
        errors.append("artifact_status_invalid")

    return not errors, errors
