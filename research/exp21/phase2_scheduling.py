"""EXP-21 Phase 2 controlled CPU-affinity scheduling experiment.

Research-only harness. It measures the exact G4 hot-path target used by the
EXP-19 test, without modifying JAMP production/runtime code.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scipy import __version__ as scipy_version
from scipy.stats import wilcoxon

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation
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

OUTPUT = Path("artifacts/research/exp21_phase2_scheduling_results.json")
DEFAULT_SEED = "EXP-21-PHASE2-SCHEDULING-V1-SEED-20260922"


def build_graph() -> ObservationAdjacencyGraph:
    """Build the canonical 20,000-edge G4 workload outside measurement."""
    edges = [(str(i), str(i + 1)) for i in range(10_000)]
    edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
    relations = tuple(
        ObservationRelation(source, target, "adjacent", {}) for source, target in edges
    )
    return ObservationAdjacencyGraph(relations)


def measure_target(graph: ObservationAdjacencyGraph) -> tuple[float, float, float, int]:
    """Measure the exact G4 target boundary used by the historical test."""
    before_gen2 = gc.get_stats()[2]["collections"]
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    if graph.is_acyclic() is not True:
        raise RuntimeError("canonical G4 graph is not acyclic")
    graph.reachable("0")
    wall_ms = (time.perf_counter() - start_wall) * 1000.0
    cpu_ms = (time.process_time() - start_cpu) * 1000.0
    after_gen2 = gc.get_stats()[2]["collections"]
    return wall_ms, cpu_ms, wall_ms - cpu_ms, after_gen2 - before_gen2


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def affinity() -> list[int]:
    if not hasattr(os, "sched_getaffinity"):
        raise RuntimeError("CPU affinity API unavailable on this runner")
    return sorted(os.sched_getaffinity(0))


def run_observation(
    graph: ObservationAdjacencyGraph,
    *,
    pair_id: int,
    condition: str,
    target_commit: str,
    seed: str,
) -> dict[str, Any]:
    default_affinity = affinity()
    if not default_affinity:
        raise RuntimeError("default CPU affinity is empty")

    before = default_affinity
    treatment_cpu = min(default_affinity)

    if condition == "CPU_AFFINITY":
        if len(default_affinity) < 2:
            raise RuntimeError("treatment cannot differ from default single-CPU affinity")
        os.sched_setaffinity(0, {treatment_cpu})
    elif condition != "CONTROL":
        raise ValueError(f"unknown condition: {condition}")

    try:
        after = affinity()
        if condition == "CPU_AFFINITY":
            affinity_verified = after == [treatment_cpu] and after != before
        else:
            affinity_verified = after == before

        if not affinity_verified:
            raise RuntimeError(
                f"affinity verification failed: condition={condition} "
                f"before={before} after={after}"
            )

        graph_for_measurement = build_graph()
        wall_ms, cpu_ms, non_cpu_delta_ms, gc_gen2 = measure_target(
            graph_for_measurement
        )
    finally:
        if condition == "CPU_AFFINITY":
            os.sched_setaffinity(0, set(default_affinity))
            restored = affinity()
            if restored != default_affinity:
                raise RuntimeError(
                    f"failed to restore process affinity: "
                    f"expected={default_affinity} observed={restored}"
                )

    observation = {
        "experiment_id": EXPERIMENT_ID,
        "phase": PHASE,
        "pair_id": str(pair_id),
        "condition": condition,
        "target_commit": target_commit,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "experiment_seed": seed,
        "timestamp": utc_timestamp(),
        "runner_name": os.environ.get("RUNNER_NAME", "unknown"),
        "runner_os": os.environ.get("RUNNER_OS", platform.system()),
        "runner_arch": os.environ.get("RUNNER_ARCH", platform.machine()),
        "kernel": platform.release(),
        "python_version": platform.python_version(),
        "cpu_count_visible": os.cpu_count(),
        "cpu_affinity_before": before,
        "cpu_affinity_after": after,
        "affinity_verified": affinity_verified,
        "wall_ms": wall_ms,
        "cpu_ms": cpu_ms,
        "non_cpu_delta_ms": non_cpu_delta_ms,
        "gc_enabled": gc.isenabled(),
        "gc_gen2_collections": gc_gen2,
    }
    return observation


def compute_result(observations: list[dict[str, Any]]) -> tuple[float, float, str]:
    by_pair: dict[str, dict[str, float]] = {}
    for observation in observations:
        by_pair.setdefault(str(observation["pair_id"]), {})[
            observation["condition"]
        ] = float(observation["wall_ms"])

    deltas = [
        pair["CPU_AFFINITY"] - pair["CONTROL"]
        for pair in by_pair.values()
        if set(pair) == {"CONTROL", "CPU_AFFINITY"}
    ]
    if len(deltas) != REQUIRED_PAIRS:
        raise RuntimeError(f"expected {REQUIRED_PAIRS} complete pairs, got {len(deltas)}")

    statistic, p_value = wilcoxon(
        deltas,
        alternative="two-sided",
        method="auto",
    )
    del statistic
    median_delta_ms = float(sorted(deltas)[len(deltas) // 2]) if len(deltas) % 2 else float(
        (sorted(deltas)[len(deltas) // 2 - 1] + sorted(deltas)[len(deltas) // 2]) / 2.0
    )
    if not math.isfinite(float(p_value)):
        raise RuntimeError("Wilcoxon returned a non-finite p-value")
    status = "SCHEDULING_EFFECT_SUPPORTED" if float(p_value) < ALPHA else (
        "SCHEDULING_EFFECT_NOT_SUPPORTED"
    )
    return float(p_value), median_delta_ms, status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=REQUIRED_PAIRS)
    parser.add_argument("--target-commit", default=os.environ.get("TARGET_COMMIT", ""))
    parser.add_argument("--seed", default=DEFAULT_SEED)
    args = parser.parse_args()

    if args.pairs != REQUIRED_PAIRS:
        raise SystemExit(f"fail-closed: pairs must equal {REQUIRED_PAIRS}")
    if not args.target_commit:
        raise SystemExit("fail-closed: TARGET_COMMIT is missing")

    observations: list[dict[str, Any]] = []
    execution_errors: list[str] = []

    for pair_id in range(1, REQUIRED_PAIRS + 1):
        order = (
            ("CONTROL", "CPU_AFFINITY")
            if pair_id % 2
            else ("CPU_AFFINITY", "CONTROL")
        )
        for condition in order:
            try:
                observation = run_observation(
                    build_graph(),
                    pair_id=pair_id,
                    condition=condition,
                    target_commit=args.target_commit,
                    seed=args.seed,
                )
                observation_errors = validate_observation(
                    observation,
                    expected_target_commit=args.target_commit,
                )
                if observation_errors:
                    execution_errors.extend(
                        f"pair_{pair_id}:{condition}:{error}"
                        for error in observation_errors
                    )
                observations.append(observation)
            except Exception as exc:
                execution_errors.append(
                    f"pair_{pair_id}:{condition}:execution_error:{type(exc).__name__}:{exc}"
                )

    artifact: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "phase": PHASE,
        "target_commit": args.target_commit,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "experiment_seed": args.seed,
        "scipy_version": scipy_version,
        "n_pairs": 0,
        "wilcoxon_p": None,
        "alpha": ALPHA,
        "median_delta_ms": None,
        "status": "INCONCLUSIVE",
        "validation_errors": execution_errors,
        "observations": observations,
    }

    if not execution_errors and len(observations) == REQUIRED_PAIRS * 2:
        try:
            p_value, median_delta_ms, status = compute_result(observations)
            artifact["n_pairs"] = REQUIRED_PAIRS
            artifact["wilcoxon_p"] = p_value
            artifact["median_delta_ms"] = median_delta_ms
            artifact["status"] = status
        except Exception as exc:
            artifact["validation_errors"].append(
                f"statistics_error:{type(exc).__name__}:{exc}"
            )
    else:
        artifact["validation_errors"].append(
            f"observation_count={len(observations)};required={REQUIRED_PAIRS * 2}"
        )

    valid, validation_errors = validate_artifact(
        artifact,
        expected_target_commit=args.target_commit,
    )
    artifact["validation_errors"].extend(validation_errors)
    if not valid:
        artifact["status"] = "INCONCLUSIVE"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "artifact": str(OUTPUT),
        "target_commit": args.target_commit,
        "n_pairs": artifact["n_pairs"],
        "wilcoxon_p": artifact["wilcoxon_p"],
        "median_delta_ms": artifact["median_delta_ms"],
        "status": artifact["status"],
        "validation_errors": artifact["validation_errors"],
    }, indent=2, sort_keys=True))

    if not valid:
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    raise SystemExit(main())
