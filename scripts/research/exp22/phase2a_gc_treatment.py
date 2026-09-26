"""EXP-22 Phase 2A: forced full-GC treatment inside the locked timed region.

Research-only. Frozen Core, canonical workload, and measurement clocks are unchanged.
Control: is_acyclic() -> reachable("0").
Treatment: gc.collect() -> is_acyclic() -> reachable("0"), with gc.collect() inside
the same timed region. No GC policy is changed.
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

EXPERIMENT_ID = "EXP-22-PHASE2A-GC-TREATMENT-V1"
WORKLOAD_SPEC_ID = "EXP-21-PHASE0-G4-CANONICAL-V1"
WORKLOAD_HASH = "f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
G4_THRESHOLD_MS = 15.0
DEFAULT_SEED = 2202
DEFAULT_PAIRS = 50


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def cpu_model() -> str | None:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def affinity() -> list[int] | None:
    getter = getattr(os, "sched_getaffinity", None)
    return sorted(getter(0)) if getter else None


def workload() -> ObservationAdjacencyGraph:
    edges = [
        ObservationRelation(str(i), str(i + 1), "adjacent", {})
        for i in range(10_000)
    ]
    edges.extend(
        ObservationRelation(str(i), str(i + 10_000), "adjacent", {})
        for i in range(10_000)
    )
    return ObservationAdjacencyGraph(tuple(edges))


def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    return values[max(0, math.ceil(p * len(values)) - 1)]


def summary(values: list[float]) -> dict[str, float]:
    return {
        "min": min(values),
        "median": statistics.median(values),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values),
        "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def paired_sign_permutation_pvalue(
    diffs: list[float], seed: int, samples: int = 20_000
) -> float | None:
    nonzero = [d for d in diffs if d != 0.0]
    if not nonzero:
        return None
    observed = abs(statistics.median(nonzero))
    state = seed & 0xFFFFFFFF
    extreme = 0
    for _ in range(samples):
        signed = []
        for value in nonzero:
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            signed.append(value if (state & 1) else -value)
        if abs(statistics.median(signed)) >= observed:
            extreme += 1
    return (extreme + 1) / (samples + 1)


def run(target_commit: str, seed: int, pairs: int, output: Path) -> dict[str, Any]:
    errors: list[str] = []
    actual = git("rev-parse", "HEAD")
    if target_commit != actual:
        errors.append("target_commit_mismatch")
    core = git("hash-object", "src/jamp/run.py")
    if core != FROZEN_CORE_BLOB:
        errors.append("frozen_core_blob_mismatch")
    if pairs <= 0:
        errors.append("pairs_invalid")

    aff0 = affinity()
    if aff0 is None:
        errors.append("cpu_affinity_missing")
    gc_initial = gc.isenabled()
    graph = workload()
    if len(graph._edges) != 20_000 or len(graph._idx_to_node) != 20_000:
        errors.append("canonical_workload_mismatch")

    observations: list[dict[str, Any]] = []
    for pair in range(1, pairs + 1):
        # Deterministic alternation prevents treatment from always occupying one side.
        first_treatment = pair % 2 == 0
        conditions = ["treatment", "control"] if first_treatment else ["control", "treatment"]
        for condition in conditions:
            gen2_before = gc.get_stats()[2]["collections"]
            wall_start = time.perf_counter_ns()
            cpu_start = time.process_time_ns()

            collected = 0
            if condition == "treatment":
                collected = gc.collect()

            acyclic = graph.is_acyclic()
            reachable = graph.reachable("0")

            cpu_end = time.process_time_ns()
            wall_end = time.perf_counter_ns()
            gen2_after = gc.get_stats()[2]["collections"]

            wall_ms = (wall_end - wall_start) / 1_000_000.0
            cpu_ms = (cpu_end - cpu_start) / 1_000_000.0
            delta_ms = wall_ms - cpu_ms
            if not acyclic or len(reachable) != 19_999:
                errors.append(f"pair_{pair}_{condition}:workload_result_mismatch")
            if affinity() != aff0:
                errors.append(f"pair_{pair}_{condition}:cpu_affinity_changed")
            if gc.isenabled() != gc_initial:
                errors.append(f"pair_{pair}_{condition}:gc_state_changed")

            observations.append({
                "pair": pair,
                "condition": condition,
                "wall_ms": wall_ms,
                "cpu_ms": cpu_ms,
                "non_cpu_delta_ms": delta_ms,
                "gc_gen2_collections": gen2_after - gen2_before,
                "gc_collect_returned": collected,
                "acyclic": acyclic,
                "reachable_from_0_count": len(reachable),
            })

    control = [o for o in observations if o["condition"] == "control"]
    treatment = [o for o in observations if o["condition"] == "treatment"]
    control_by_pair = {o["pair"]: o for o in control}
    treatment_by_pair = {o["pair"]: o for o in treatment}
    diffs = [
        treatment_by_pair[p]["wall_ms"] - control_by_pair[p]["wall_ms"]
        for p in sorted(control_by_pair)
        if p in treatment_by_pair
    ]
    p_value = paired_sign_permutation_pvalue(diffs, seed)
    distribution_shift = p_value is not None and p_value < 0.01

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "phase": 2,
        "treatment_factor": {
            "name": "forced_full_gc_inside_timed_region",
            "control": "is_acyclic() -> reachable('0')",
            "treatment": "gc.collect() -> is_acyclic() -> reachable('0')",
            "single_factor": True,
            "gc_policy_changed": False,
        },
        "target_commit": target_commit,
        "core_blob": core,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_HASH,
        "experiment_seed": seed,
        "pairs_requested": pairs,
        "pairs_completed": len(diffs),
        "timestamp": datetime.now(UTC).isoformat(),
        "environment_metadata": {
            "runner_name": os.environ.get("RUNNER_NAME", ""),
            "runner_os": platform.platform(),
            "runner_arch": platform.machine(),
            "kernel": platform.release(),
            "python_version": platform.python_version(),
            "cpu_model": cpu_model(),
            "cpu_count_visible": os.cpu_count(),
            "cpu_affinity": aff0,
            "clock_resolution_ns": {
                "wall": int(time.get_clock_info("perf_counter").resolution * 1_000_000_000),
                "cpu": int(time.get_clock_info("process_time").resolution * 1_000_000_000),
            },
        },
        "measurement_boundary": {
            "timed_region": (
                "control: is_acyclic() -> reachable('0'); "
                "treatment: gc.collect() -> is_acyclic() -> reachable('0')"
            ),
            "graph_construction": "outside_timed_region",
            "imports": "outside_timed_region",
            "serialization_logging_validation": "after_timed_region",
            "wall_clock_api": "time.perf_counter_ns",
            "cpu_clock_api": "time.process_time_ns",
            "non_cpu_delta_formula": "wall_ms - cpu_ms",
        },
        "control_summary": {
            "wall_ms": summary([o["wall_ms"] for o in control]),
            "cpu_ms": summary([o["cpu_ms"] for o in control]),
            "non_cpu_delta_ms": summary([o["non_cpu_delta_ms"] for o in control]),
            "g4_failures": sum(o["wall_ms"] > G4_THRESHOLD_MS for o in control),
        },
        "treatment_summary": {
            "wall_ms": summary([o["wall_ms"] for o in treatment]),
            "cpu_ms": summary([o["cpu_ms"] for o in treatment]),
            "non_cpu_delta_ms": summary([o["non_cpu_delta_ms"] for o in treatment]),
            "g4_failures": sum(o["wall_ms"] > G4_THRESHOLD_MS for o in treatment),
            "gen2_collections": sum(o["gc_gen2_collections"] for o in treatment),
        },
        "paired_effect": {
            "median_wall_delta_ms_treatment_minus_control": (
                statistics.median(diffs) if diffs else None
            ),
            "p_value": p_value,
            "p_value_method": "deterministic_paired_sign_permutation_20000",
            "distribution_shift": "VERIFIED" if distribution_shift else "NOT_VERIFIED",
        },
        "epistemic_classification": {
            "measurement_boundary": "VERIFIED" if not errors else "INCONCLUSIVE",
            "execution_identity": "VERIFIED" if target_commit == actual else "INCONCLUSIVE",
            "frozen_core": "VERIFIED" if core == FROZEN_CORE_BLOB else "INCONCLUSIVE",
            "perturbation": "PERTURBATION_ASSOCIATED" if distribution_shift else "NOT_ESTABLISHED",
            "historical_g4_signature_match": "NOT_TESTED",
            "g4_root_cause": "UNKNOWN",
        },
        "raw_observations": observations,
        "validation_errors": errors,
        "status": "VERIFIED" if not errors and len(diffs) == pairs else "INCONCLUSIVE",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-commit", required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--pairs", type=int, default=DEFAULT_PAIRS)
    parser.add_argument("--output-artifact", type=Path, required=True)
    args = parser.parse_args()
    artifact = run(args.target_commit, args.seed, args.pairs, args.output_artifact)
    print(json.dumps(artifact, indent=2, sort_keys=True))
    return 0 if artifact["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
