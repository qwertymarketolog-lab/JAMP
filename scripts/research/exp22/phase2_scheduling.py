"""EXP-21 Phase 2 controlled CPU-affinity scheduling experiment.

Research-only. Production code is not modified.
Fail-closed: requested affinity is never treated as evidence.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

EXPERIMENT_ID = "EXP-21-PHASE2-SCHEDULING-V1"
PHASE = 2
WORKLOAD_SPEC_ID = "EXP-21-PHASE0-G4-CANONICAL-V1"
WORKLOAD_DEFINITION_HASH = (
    "f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
)
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
G4_THRESHOLD_MS = 15.0
ALPHA = 0.01
N_PAIRS = 30
ARTIFACT = Path("artifacts/research/exp21_phase2_scheduling.json")

HISTORICAL_CANONICAL_WORKLOAD_CODE = """from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

edges = [(str(i), str(i + 1)) for i in range(10_000)]
edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
relations = tuple(
    ObservationRelation(source, target, "adjacent", {}) for source, target in edges
)
g = ObservationAdjacencyGraph(relations)

gc_gen2_before = gc.get_stats()[2]["collections"]
wall_start = time.perf_counter()
cpu_start = time.process_time()
_ = g.is_acyclic()
_ = g.reachable("0")
cpu_end = time.process_time()
wall_end = time.perf_counter()
gc_gen2_after = gc.get_stats()[2]["collections"]
"""


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _affinity() -> list[int] | None:
    getter = getattr(os, "sched_getaffinity", None)
    if getter is None:
        return None
    return sorted(getter(0))


def _environment() -> dict[str, Any]:
    return {
        "runner_name": os.environ.get("RUNNER_NAME", ""),
        "runner_os": platform.platform(),
        "runner_arch": platform.machine(),
        "kernel": platform.release(),
        "python_version": platform.python_version(),
        "cpu_count_visible": os.cpu_count(),
    }


def _environment_errors(env: dict[str, Any], pair_id: int) -> list[str]:
    errors: list[str] = []
    for field in ("runner_name", "runner_os", "runner_arch", "kernel", "python_version"):
        if not isinstance(env.get(field), str) or not env[field].strip():
            errors.append(f"pair_{pair_id}_{field}_missing")
    cpu_count = env.get("cpu_count_visible")
    if not isinstance(cpu_count, int) or cpu_count < 1:
        errors.append(f"pair_{pair_id}_cpu_count_visible_invalid")
    return errors


def _verify_historical_workload_lineage() -> bool:
    actual = hashlib.sha256(
        HISTORICAL_CANONICAL_WORKLOAD_CODE.encode("utf-8")
    ).hexdigest()
    return actual == WORKLOAD_DEFINITION_HASH


def _canonical_workload():
    from research.exp19.adjacency_graph import ObservationAdjacencyGraph
    from research.exp19.observation_relation import ObservationRelation

    edges = [(str(i), str(i + 1)) for i in range(10_000)]
    edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
    relations = tuple(
        ObservationRelation(source, target, "adjacent", {}) for source, target in edges
    )
    return ObservationAdjacencyGraph(relations)


def _run_boundary(graph) -> tuple[float, float, float, dict[str, Any]]:
    gc_before = gc.isenabled()
    gen2_before = gc.get_stats()[2]["collections"]

    wall_start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()

    acyclic = graph.is_acyclic()
    reachable = graph.reachable("0")

    cpu_end = time.process_time_ns()
    wall_end = time.perf_counter_ns()

    gen2_after = gc.get_stats()[2]["collections"]
    gc_after = gc.isenabled()

    wall_ms = (wall_end - wall_start) / 1_000_000.0
    cpu_ms = (cpu_end - cpu_start) / 1_000_000.0
    non_cpu_delta_ms = wall_ms - cpu_ms

    finite = all(
        isinstance(value, (int, float))
        and value == value
        and abs(value) != float("inf")
        for value in (wall_ms, cpu_ms, non_cpu_delta_ms)
    )
    checks = {
        "acyclic": acyclic,
        "reachable_count": len(reachable),
        "gc_state_unchanged": gc_before == gc_after,
        "gc_enabled": gc_before,
        "gc_gen2_collections": gen2_after - gen2_before,
        "timing_finite": finite,
    }
    return wall_ms, cpu_ms, non_cpu_delta_ms, checks


def _observation(
    *,
    pair_id: int,
    condition: str,
    target_commit: str,
    seed: int,
    affinity_before: list[int],
    affinity_after: list[int] | None,
    affinity_verified: bool,
    affinity_restored: bool,
    wall_ms: float,
    cpu_ms: float,
    non_cpu_delta_ms: float,
    checks: dict[str, Any],
    env: dict[str, Any],
) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "phase": PHASE,
        "pair_id": pair_id,
        "condition": condition,
        "target_commit": target_commit,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "experiment_seed": seed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **env,
        "cpu_affinity_before": affinity_before,
        "cpu_affinity_after": affinity_after,
        "affinity_verified": affinity_verified,
        "affinity_restored": affinity_restored,
        "wall_ms": wall_ms,
        "cpu_ms": cpu_ms,
        "non_cpu_delta_ms": non_cpu_delta_ms,
        "gc_enabled": checks["gc_enabled"],
        "gc_gen2_collections": checks["gc_gen2_collections"],
        "result_valid": (
            checks["acyclic"]
            and checks["reachable_count"] == 19_999
            and checks["gc_state_unchanged"]
            and checks["timing_finite"]
            and affinity_verified
            and affinity_restored
        ),
    }


def _measure(
    *,
    pair_id: int,
    condition: str,
    target_commit: str,
    seed: int,
    treatment_cpu: int | None,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    initial = _affinity()
    env = _environment()

    if initial is None:
        errors.append(f"pair_{pair_id}_{condition}_affinity_missing")
        return {}, errors
    errors.extend(_environment_errors(env, pair_id))

    if condition not in {"CONTROL", "CPU_AFFINITY"}:
        errors.append(f"pair_{pair_id}_unknown_condition")
        return {}, errors

    intervention_active = False
    if condition == "CPU_AFFINITY":
        if treatment_cpu is None or treatment_cpu not in initial:
            errors.append(f"pair_{pair_id}_invalid_treatment_cpu")
            return {}, errors
        try:
            os.sched_setaffinity(0, {treatment_cpu})
            intervention_active = True
        except (AttributeError, OSError):
            errors.append(f"pair_{pair_id}_affinity_intervention_failed")
            return {}, errors

    affinity_restored = not intervention_active
    try:
        after_intervention = _affinity()
        if condition == "CONTROL":
            affinity_verified = after_intervention == initial
        else:
            affinity_verified = after_intervention == [treatment_cpu]

        if not affinity_verified:
            errors.append(f"pair_{pair_id}_{condition}_affinity_mismatch")

        graph = _canonical_workload()
        if len(graph._edges) != 20_000:
            errors.append(f"pair_{pair_id}_workload_edge_count_mismatch")
        if len(graph._idx_to_node) != 20_000:
            errors.append(f"pair_{pair_id}_workload_node_count_mismatch")

        wall_ms, cpu_ms, non_cpu_delta_ms, checks = _run_boundary(graph)

        if not checks["acyclic"]:
            errors.append(f"pair_{pair_id}_acyclicity_failed")
        if checks["reachable_count"] != 19_999:
            errors.append(f"pair_{pair_id}_reachability_mismatch")
        if not checks["gc_state_unchanged"]:
            errors.append(f"pair_{pair_id}_gc_state_changed")
        if not checks["timing_finite"]:
            errors.append(f"pair_{pair_id}_non_finite_timing")

    except Exception as exc:
        errors.append(f"pair_{pair_id}_measurement_exception:{type(exc).__name__}")
        return {}, errors

    finally:
        if intervention_active:
            try:
                os.sched_setaffinity(0, set(initial))
            except (AttributeError, OSError) as exc:
                affinity_restored = False
                errors.append(
                    f"pair_{pair_id}_affinity_restoration_failed:{type(exc).__name__}:{exc}"
                )
            restored = _affinity()
            print(
                f"AFFINITY_RESTORE pair={pair_id} expected={initial!r} "
                f"actual={restored!r} restored={restored == initial}"
            )
            if restored != initial:
                affinity_restored = False
                errors.append(
                    f"pair_{pair_id}_affinity_restoration_mismatch:"
                    f"expected={initial!r}:actual={restored!r}"
                )

    observation = _observation(
        pair_id=pair_id,
        condition=condition,
        target_commit=target_commit,
        seed=seed,
        affinity_before=initial,
        affinity_after=after_intervention,
        affinity_verified=affinity_verified,
        affinity_restored=affinity_restored,
        wall_ms=wall_ms,
        cpu_ms=cpu_ms,
        non_cpu_delta_ms=non_cpu_delta_ms,
        checks=checks,
        env=env,
    )
    if errors:
        observation["result_valid"] = False
    return observation, errors


def _validate_observation(
    observation: dict[str, Any],
    *,
    target_commit: str,
    seed: int,
) -> list[str]:
    required = {
        "experiment_id", "phase", "pair_id", "condition", "target_commit",
        "workload_spec_id", "workload_definition_hash", "experiment_seed",
        "timestamp", "runner_name", "runner_os", "runner_arch", "kernel",
        "python_version", "cpu_count_visible", "cpu_affinity_before",
        "cpu_affinity_after", "affinity_verified", "affinity_restored",
        "wall_ms", "cpu_ms", "non_cpu_delta_ms", "gc_enabled",
        "gc_gen2_collections", "result_valid",
    }
    errors = [f"missing_field:{field}" for field in sorted(required - observation.keys())]
    if observation.get("experiment_id") != EXPERIMENT_ID:
        errors.append("experiment_id_mismatch")
    if observation.get("phase") != PHASE:
        errors.append("phase_mismatch")
    if observation.get("target_commit") != target_commit:
        errors.append("target_commit_mismatch")
    if observation.get("workload_spec_id") != WORKLOAD_SPEC_ID:
        errors.append("workload_spec_id_mismatch")
    if observation.get("workload_definition_hash") != WORKLOAD_DEFINITION_HASH:
        errors.append("workload_definition_hash_mismatch")
    if observation.get("experiment_seed") != seed:
        errors.append("experiment_seed_mismatch")
    if observation.get("condition") not in {"CONTROL", "CPU_AFFINITY"}:
        errors.append("unknown_condition")
    if not isinstance(observation.get("pair_id"), int) or not 1 <= observation["pair_id"] <= N_PAIRS:
        errors.append("invalid_pair_id")
    if observation.get("condition") == "CPU_AFFINITY":
        before = observation.get("cpu_affinity_before")
        after = observation.get("cpu_affinity_after")
        if not isinstance(before, list) or not before:
            errors.append("treatment_affinity_before_missing")
        if after != [min(before)] if isinstance(before, list) and before else True:
            errors.append("treatment_affinity_observation_mismatch")
        if observation.get("affinity_verified") is not True:
            errors.append("treatment_affinity_not_verified")
    for field in ("runner_name", "runner_os", "runner_arch", "kernel", "python_version"):
        if not isinstance(observation.get(field), str) or not observation[field].strip():
            errors.append(f"{field}_missing")
    if not isinstance(observation.get("cpu_count_visible"), int) or observation["cpu_count_visible"] < 1:
        errors.append("cpu_count_visible_invalid")
    return errors


def run(target_commit: str, seed: int) -> dict[str, Any]:
    errors: list[str] = []

    if not isinstance(seed, int):
        errors.append("experiment_seed_missing")
    if not target_commit or target_commit != _git("rev-parse", "HEAD"):
        errors.append("target_commit_mismatch")
    if _git("hash-object", "src/jamp/run.py") != FROZEN_CORE_BLOB:
        errors.append("frozen_core_blob_mismatch")
    if not _verify_historical_workload_lineage():
        errors.append("workload_definition_lineage_mismatch")

    observations: list[dict[str, Any]] = []
    if not errors:
        for pair_id in range(1, N_PAIRS + 1):
            order = (
                ("CONTROL", "CPU_AFFINITY")
                if pair_id % 2
                else ("CPU_AFFINITY", "CONTROL")
            )
            initial = _affinity()
            if initial is None or not initial:
                errors.append(f"pair_{pair_id}_initial_affinity_missing")
                break
            treatment_cpu = min(initial)

            for condition in order:
                observation, pair_errors = _measure(
                    pair_id=pair_id,
                    condition=condition,
                    target_commit=target_commit,
                    seed=seed,
                    treatment_cpu=treatment_cpu,
                )
                if observation:
                    observations.append(observation)
                    errors.extend(pair_errors)
                else:
                    errors.extend(pair_errors)
                    break

    seen_ids: set[tuple[int, str]] = set()
    for observation in observations:
        key = (observation.get("pair_id"), observation.get("condition"))
        if key in seen_ids:
            errors.append(f"duplicate_observation:{key[0]}:{key[1]}")
        seen_ids.add(key)
        errors.extend(
            _validate_observation(
                observation,
                target_commit=target_commit,
                seed=seed,
            )
        )

    pairs: dict[int, dict[str, dict[str, Any]]] = {}
    for observation in observations:
        pairs.setdefault(observation["pair_id"], {})[observation["condition"]] = observation

    valid_pairs: list[tuple[float, float]] = []
    for pair_id in range(1, N_PAIRS + 1):
        pair = pairs.get(pair_id, {})
        if set(pair) != {"CONTROL", "CPU_AFFINITY"}:
            errors.append(f"pair_{pair_id}_incomplete")
            continue
        control = pair["CONTROL"]
        treatment = pair["CPU_AFFINITY"]
        if not control["result_valid"] or not treatment["result_valid"]:
            errors.append(f"pair_{pair_id}_invalid_result")
            continue
        valid_pairs.append((treatment["wall_ms"], control["wall_ms"]))

    p_value: float | None = None
    deltas = [treatment - control for treatment, control in valid_pairs]
    if len(valid_pairs) == N_PAIRS and not errors:
        try:
            from scipy.stats import wilcoxon

            result = wilcoxon(deltas, alternative="two-sided", method="auto")
            p_value = float(result.pvalue)
        except Exception as exc:
            errors.append(f"statistical_calculation_unavailable:{type(exc).__name__}")
    else:
        if len(valid_pairs) < N_PAIRS:
            errors.append("fewer_than_30_valid_pairs")

    status = "INCONCLUSIVE"
    if not errors:
        status = "VERIFIED / SUPPORTED" if p_value is not None and p_value < ALPHA else "VERIFIED / NOT_SUPPORTED"

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "phase": PHASE,
        "target_commit": target_commit,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "experiment_seed": seed,
        "observations": observations,
        "n_pairs": len(valid_pairs),
        "wilcoxon_p": p_value,
        "alpha": ALPHA,
        "median_delta_ms": median(deltas) if deltas else None,
        "status": status,
        "validation_errors": sorted(set(errors)),
        "frozen_core_blob": _git("hash-object", "src/jamp/run.py"),
        "g4_threshold_ms": G4_THRESHOLD_MS,
        "measurement_boundary": {
            "timed_region": "graph.is_acyclic() followed by graph.reachable('0')",
            "graph_construction": "outside_timed_region",
            "wall_clock": "time.perf_counter_ns",
            "cpu_clock": "time.process_time_ns",
            "non_cpu_delta_formula": "wall_ms - cpu_ms",
            "gc": "existing process GC state observed; no policy change",
        },
    }

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-commit", required=True)
    parser.add_argument("--seed", required=True, type=int)
    args = parser.parse_args()
    artifact = run(args.target_commit, args.seed)
    return 0 if artifact["status"] != "INCONCLUSIVE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
