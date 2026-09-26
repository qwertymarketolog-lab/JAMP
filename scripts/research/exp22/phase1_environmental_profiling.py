"""EXP-22 Phase 1 environmental profiling.

Research-only. Repeats the verified EXP-22 Phase 0 measurement boundary
without changing production code, GC policy, CPU affinity, or workload.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import platform
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

EXPERIMENT_ID = "EXP-22-PHASE1-ENVIRONMENTAL-PROFILING"
PHASE = 1
WORKLOAD_SPEC_ID = "EXP-21-PHASE0-G4-CANONICAL-V1"
WORKLOAD_DEFINITION_HASH = (
    "f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
)
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
G4_THRESHOLD_MS = 15.0
DEFAULT_SEED = 2201
DEFAULT_ITERATIONS = 50
ARTIFACT = Path("artifacts/research/exp22_phase1_evidence.json")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _cpu_model() -> str | None:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        return None
    return None


def _affinity() -> list[int] | None:
    getter = getattr(os, "sched_getaffinity", None)
    if getter is None:
        return None
    return sorted(getter(0))


def _canonical_workload() -> ObservationAdjacencyGraph:
    edges = [
        ObservationRelation(str(i), str(i + 1), "adjacent", {})
        for i in range(10_000)
    ]
    edges.extend(
        ObservationRelation(str(i), str(i + 10_000), "adjacent", {})
        for i in range(10_000)
    )
    return ObservationAdjacencyGraph(tuple(edges))


def _validate_workload(graph: ObservationAdjacencyGraph) -> list[str]:
    errors: list[str] = []
    if len(graph._edges) != 20_000:
        errors.append("workload_edge_count_mismatch")
    if len(graph._idx_to_node) != 20_000:
        errors.append("workload_node_count_mismatch")
    return errors


def _rank(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][1] == ordered[i][1]:
            j += 1
        average = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[ordered[k][0]] = average
        i = j
    return ranks


def _spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    rx = _rank(x)
    ry = _rank(y)
    mean_x = statistics.mean(rx)
    mean_y = statistics.mean(ry)
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry, strict=True))
    denom_x = math.sqrt(sum((a - mean_x) ** 2 for a in rx))
    denom_y = math.sqrt(sum((b - mean_y) ** 2 for b in ry))
    if denom_x == 0.0 or denom_y == 0.0:
        return None
    return numerator / (denom_x * denom_y)


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "min": min(values),
        "median": statistics.median(values),
        "p95": ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)],
        "p99": ordered[max(0, math.ceil(0.99 * len(ordered)) - 1)],
        "max": max(values),
        "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def run(target_commit: str, seed: int, iterations: int, artifact_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    if iterations <= 0:
        errors.append("iterations_invalid")
    if not target_commit:
        errors.append("target_commit_missing")

    actual_commit = _git("rev-parse", "HEAD")
    if target_commit != actual_commit:
        errors.append("target_commit_mismatch")

    core_blob = _git("hash-object", "src/jamp/run.py")
    if core_blob != FROZEN_CORE_BLOB:
        errors.append("frozen_core_blob_mismatch")

    affinity_before = _affinity()
    if affinity_before is None:
        errors.append("cpu_affinity_missing")

    wall_clock = time.get_clock_info("perf_counter")
    cpu_clock = time.get_clock_info("process_time")
    runner_name = os.environ.get("RUNNER_NAME", "")
    if not runner_name:
        errors.append("runner_name_missing")

    timestamp = datetime.now(UTC).isoformat()
    graph = _canonical_workload()
    errors.extend(_validate_workload(graph))

    initial_gc_enabled = gc.isenabled()
    initial_affinity = affinity_before

    observations: list[dict[str, Any]] = []
    for iteration in range(1, iterations + 1):
        gen2_before = gc.get_stats()[2]["collections"]
        measurement_start = time.perf_counter_ns()
        cpu_start = time.process_time_ns()

        acyclic = graph.is_acyclic()
        reachable = graph.reachable("0")

        cpu_end = time.process_time_ns()
        measurement_end = time.perf_counter_ns()

        gen2_after = gc.get_stats()[2]["collections"]
        wall_ms = (measurement_end - measurement_start) / 1_000_000.0
        cpu_ms = (cpu_end - cpu_start) / 1_000_000.0
        non_cpu_delta_ms = wall_ms - cpu_ms

        affinity_after = _affinity()
        gc_after = gc.isenabled()

        if not acyclic:
            errors.append(f"iteration_{iteration}_acyclicity_failed")
        if len(reachable) != 19_999:
            errors.append(f"iteration_{iteration}_reachability_size_mismatch")
        if affinity_after != initial_affinity:
            errors.append(f"iteration_{iteration}_cpu_affinity_changed")
        if gc_after != initial_gc_enabled:
            errors.append(f"iteration_{iteration}_gc_state_changed")
        if any(
            not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in (wall_ms, cpu_ms, non_cpu_delta_ms)
        ):
            errors.append(f"iteration_{iteration}_non_finite_timing")

        observations.append(
            {
                "iteration": iteration,
                "wall_ms": wall_ms,
                "cpu_ms": cpu_ms,
                "non_cpu_delta_ms": non_cpu_delta_ms,
                "gc_gen2_collections": gen2_after - gen2_before,
                "acyclic": acyclic,
                "reachable_from_0_count": len(reachable),
            }
        )

    wall_values = [item["wall_ms"] for item in observations]
    cpu_values = [item["cpu_ms"] for item in observations]
    delta_values = [item["non_cpu_delta_ms"] for item in observations]
    gc_values = [float(item["gc_gen2_collections"]) for item in observations]
    fail_values = [1.0 if value > G4_THRESHOLD_MS else 0.0 for value in wall_values]

    environment = {
        "runner_name": runner_name,
        "runner_os": platform.platform(),
        "runner_arch": platform.machine(),
        "kernel": platform.release(),
        "python_version": platform.python_version(),
        "cpu_model": _cpu_model(),
        "cpu_count_visible": os.cpu_count(),
        "cpu_affinity": affinity_before,
        "clock_resolution_ns": {
            "wall": int(wall_clock.resolution * 1_000_000_000),
            "cpu": int(cpu_clock.resolution * 1_000_000_000),
        },
    }

    gc_total = sum(int(item["gc_gen2_collections"]) for item in observations)
    association = {
        "wall_vs_non_cpu": {
            "method": "spearman_rank_correlation",
            "rho": _spearman(wall_values, delta_values),
            "interpretation": "ASSOCIATION_ONLY",
        },
        "wall_vs_gc": {
            "method": "spearman_rank_correlation",
            "rho": _spearman(wall_values, gc_values),
            "gc_active_observations": sum(value > 0 for value in gc_values),
            "interpretation": "ASSOCIATION_ONLY",
        },
        "wall_vs_g4_failure": {
            "method": "spearman_rank_correlation",
            "rho": _spearman(wall_values, fail_values),
            "interpretation": "DESCRIPTIVE_ONLY",
        },
    }

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "phase": PHASE,
        "target_commit": target_commit,
        "core_blob": core_blob,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "experiment_seed": seed,
        "iterations_requested": iterations,
        "iterations_completed": len(observations),
        "timestamp": timestamp,
        "environment_metadata": environment,
        "measurement_boundary": {
            "timed_region": "graph.is_acyclic() followed by graph.reachable('0')",
            "graph_construction": "outside_timed_region",
            "imports": "outside_timed_region",
            "gc": "existing process state observed; no policy change",
            "serialization_logging_validation": "after_timed_region",
            "wall_clock_api": "time.perf_counter_ns",
            "cpu_clock_api": "time.process_time_ns",
            "non_cpu_delta_formula": "wall_ms - cpu_ms",
        },
        "summary_stats": {
            "wall_ms": _summary(wall_values),
            "cpu_ms": _summary(cpu_values),
            "non_cpu_delta_ms": _summary(delta_values),
            "fail_count_gt_15ms": sum(value > G4_THRESHOLD_MS for value in wall_values),
            "fail_rate_gt_15ms": sum(value > G4_THRESHOLD_MS for value in wall_values)
            / len(wall_values),
            "gc_gen2_collections_total": gc_total,
        },
        "raw_observations": observations,
        "associations": association,
        "epistemic_classification": {
            "measurement_boundary": "VERIFIED" if not errors else "INCONCLUSIVE",
            "execution_identity": "VERIFIED" if target_commit == actual_commit else "INCONCLUSIVE",
            "frozen_core": "VERIFIED" if core_blob == FROZEN_CORE_BLOB else "INCONCLUSIVE",
            "g4_root_cause": "UNKNOWN",
        },
        "status": "VERIFIED" if not errors and len(observations) == iterations else "INCONCLUSIVE",
        "validation_errors": errors,
    }

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-commit", required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--output-artifact", type=Path, default=ARTIFACT)
    args = parser.parse_args()
    artifact = run(
        args.target_commit,
        args.seed,
        args.iterations,
        Path(args.output_artifact),
    )
    print(json.dumps(artifact, indent=2, sort_keys=True))
    return 0 if artifact["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
