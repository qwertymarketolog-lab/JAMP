"""EXP-22 Phase 0 measurement-boundary audit.

Research-only. This module reproduces the existing G4 measured operation boundary
without modifying production code or introducing a causal intervention.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

EXPERIMENT_ID = "EXP-22-PHASE0-MEASUREMENT-BOUNDARY-V1"
PHASE = 0
WORKLOAD_SPEC_ID = "EXP-21-PHASE0-G4-CANONICAL-V1"
WORKLOAD_DEFINITION_HASH = (
    "f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
)
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
G4_THRESHOLD_MS = 15.0
DEFAULT_SEED = 2201
ARTIFACT = Path("artifacts/research/exp22_phase0_measurement_boundary.json")


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


def run(target_commit: str, seed: int) -> dict[str, Any]:
    errors: list[str] = []

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

    timestamp = datetime.now(timezone.utc).isoformat()
    runner_name = os.environ.get("RUNNER_NAME", "")
    if not runner_name:
        errors.append("runner_name_missing")

    workload_initialization_start = time.perf_counter_ns()
    graph = _canonical_workload()
    workload_initialization_end = time.perf_counter_ns()
    errors.extend(_validate_workload(graph))

    gc_before = gc.isenabled()
    gen2_before = gc.get_stats()[2]["collections"]

    measurement_start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()

    # Exact G4 operation boundary: graph construction is outside; the two
    # measured graph operations are inside the timed region.
    acyclic = graph.is_acyclic()
    reachable = graph.reachable("0")

    cpu_end = time.process_time_ns()
    measurement_end = time.perf_counter_ns()

    gen2_after = gc.get_stats()[2]["collections"]
    gc_after = gc.isenabled()
    affinity_after = _affinity()

    wall_ms = (measurement_end - measurement_start) / 1_000_000.0
    cpu_ms = (cpu_end - cpu_start) / 1_000_000.0
    non_cpu_delta_ms = wall_ms - cpu_ms

    if not acyclic:
        errors.append("acyclicity_check_failed")
    if len(reachable) != 19_999:
        errors.append("reachability_size_mismatch")
    if not all(
        isinstance(value, (int, float)) and value == value and abs(value) != float("inf")
        for value in (wall_ms, cpu_ms, non_cpu_delta_ms)
    ):
        errors.append("non_finite_timing")
    if wall_clock.resolution <= 0:
        errors.append("wall_clock_resolution_invalid")
    if cpu_clock.resolution <= 0:
        errors.append("cpu_clock_resolution_invalid")
    if gc_before != gc_after:
        errors.append("gc_state_changed")
    if affinity_before != affinity_after:
        errors.append("cpu_affinity_changed")

    observation = {
        "observation_id": "obs-0001",
        "experiment_id": EXPERIMENT_ID,
        "phase": PHASE,
        "target_commit": target_commit,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "experiment_seed": seed,
        "timestamp": timestamp,
        "runner_name": runner_name,
        "runner_os": platform.platform(),
        "runner_arch": platform.machine(),
        "kernel": platform.release(),
        "python_version": platform.python_version(),
        "cpu_model": _cpu_model(),
        "cpu_count_visible": os.cpu_count(),
        "cpu_affinity": affinity_before,
        "clock_source": {
            "wall": "time.perf_counter_ns",
            "cpu": "time.process_time_ns",
        },
        "clock_resolution": {
            "wall_seconds": wall_clock.resolution,
            "cpu_seconds": cpu_clock.resolution,
        },
        "wall_ms": wall_ms,
        "cpu_ms": cpu_ms,
        "non_cpu_delta_ms": non_cpu_delta_ms,
        "gc_enabled": gc_before,
        "gc_gen2_collections": gen2_after - gen2_before,
        "measurement_boundary_markers": {
            "workload_initialization_start_ns": workload_initialization_start,
            "workload_initialization_end_ns": workload_initialization_end,
            "measurement_start_ns": measurement_start,
            "measurement_end_ns": measurement_end,
            "graph_construction": "outside_timed_region",
            "imports": "outside_timed_region",
            "gc": "enabled_as_observed; no policy change",
            "serialization_logging_validation": "outside_timed_region",
        },
        "workload_observed": {
            "edge_count": 20_000,
            "node_count": 20_000,
            "acyclic": acyclic,
            "reachable_from_0_count": len(reachable),
        },
    }

    boundary = {
        "initialization": "starts before canonical graph construction",
        "timed_region": "graph.is_acyclic() followed by graph.reachable('0')",
        "graph_construction": "outside_timed_region",
        "imports": "outside_timed_region",
        "gc": "existing process GC state observed; no intervention",
        "serialization_logging_validation": "after_timed_region",
        "wall_clock_api": "time.perf_counter_ns",
        "cpu_clock_api": "time.process_time_ns",
        "non_cpu_delta_formula": "wall_ms - cpu_ms",
        "g4_threshold_ms": G4_THRESHOLD_MS,
    }

    environment = {
        "runner_name": runner_name,
        "runner_os": platform.platform(),
        "runner_arch": platform.machine(),
        "kernel": platform.release(),
        "python_version": platform.python_version(),
        "cpu_model": _cpu_model(),
        "cpu_count_visible": os.cpu_count(),
        "cpu_affinity": affinity_before,
    }

    status = "VERIFIED" if not errors else "INCONCLUSIVE"
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "phase": PHASE,
        "target_commit": target_commit,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "experiment_seed": seed,
        "observations": [observation],
        "measurement_boundary": boundary,
        "environment_summary": environment,
        "n_observations": 1,
        "status": status,
        "validation_errors": errors,
        "frozen_core_blob": core_blob,
        "interpretation": {
            "observed": [
                "timing_values",
                "timing_api_identity",
                "timing_boundary_metadata",
                "runner_environment_metadata",
                "workload_identity",
            ],
            "verified": [
                "provenance_contract" if not errors else "none",
                "measurement_boundary" if not errors else "none",
                "frozen_core_identity" if core_blob == FROZEN_CORE_BLOB else "none",
            ],
            "inferred": [],
            "unknown": [
                "causal_explanation_of_g4_latency",
                "whether_an_alternative_measurement_path_would_change_the_observation",
                "whether_environment_differences_cause_the_observed_latency",
            ],
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
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    artifact = run(args.target_commit, args.seed)
    print(json.dumps(artifact, indent=2, sort_keys=True))
    return 0 if artifact["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
