"""EXP-21 Phase 2 Step 3 — Intervention A telemetry.

Research-only causal intervention harness.

Control preserves the canonical ObservationAdjacencyGraph.is_acyclic()
algorithm and its list[int] color buffer. Intervention A changes only the
color buffer representation to bytearray while preserving state values
0/1/2 and traversal logic.

Graph construction is outside timed regions. The harness records raw paired
samples and descriptive statistics only; it does not declare CAUSAL or
FALSIFIED.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import time
from pathlib import Path
from typing import Callable

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

WORKLOAD_SPEC_ID = "EXP-21-PHASE2-HOTPATH-COST-G4-V1"
INTERVENTION_ID = "EXP-21-PHASE2-STEP3-INTERVENTION-A-V1"
EDGE_COUNT = 20_000
CHAIN_EDGES = 10_000
OFFSET_EDGES = 10_000
DEFAULT_REPEATS = 11
OUTPUT = Path("artifacts/research/exp21_phase2_step3_intervention_a.json")
FROZEN_CORE_BASE = "af2292bbfc8518716bdf5b76614efb33ed9496f0"

CANONICAL_WORKLOAD_DEFINITION = """edges = [(str(i), str(i + 1)) for i in range(10_000)]
edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
relations = tuple(
    ObservationRelation(source, target, "adjacent", {})
    for source, target in edges
)
graph = ObservationAdjacencyGraph(relations)
"""
WORKLOAD_DEFINITION_HASH = hashlib.sha256(
    CANONICAL_WORKLOAD_DEFINITION.encode("utf-8")
).hexdigest()


def resolve_target_commit() -> str:
    expected = os.getenv("TARGET_COMMIT", "").strip()
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()
    if len(actual) != 40 or any(c not in "0123456789abcdef" for c in actual):
        raise RuntimeError("git rev-parse HEAD returned an invalid SHA")
    if expected and expected != actual:
        raise RuntimeError(
            f"TARGET_COMMIT mismatch: expected {expected}, actual {actual}"
        )
    return actual


def build_graph() -> ObservationAdjacencyGraph:
    edges = [(str(i), str(i + 1)) for i in range(CHAIN_EDGES)]
    edges.extend((str(i), str(i + CHAIN_EDGES)) for i in range(OFFSET_EDGES))
    relations = tuple(
        ObservationRelation(source, target, "adjacent", {})
        for source, target in edges
    )
    return ObservationAdjacencyGraph(relations)


def control_is_acyclic(graph: ObservationAdjacencyGraph) -> bool:
    """Canonical traversal with the original list[int] color buffer."""
    adj = graph._adj_int
    v_count = graph._v_count
    color = [0] * v_count

    for start_node in range(v_count):
        if color[start_node] != 0:
            continue

        color[start_node] = 1
        children = adj[start_node]
        stack = [[start_node, 0, children, len(children)]]

        while stack:
            frame = stack[-1]
            index = frame[1]
            if index < frame[3]:
                target = frame[2][index]
                frame[1] = index + 1
                state = color[target]
                if state == 1:
                    return False
                if state == 0:
                    color[target] = 1
                    target_children = adj[target]
                    stack.append(
                        [target, 0, target_children, len(target_children)]
                    )
            else:
                stack.pop()
                color[frame[0]] = 2

    return True


def intervention_a_is_acyclic(graph: ObservationAdjacencyGraph) -> bool:
    """Identical traversal; only color changes from list to bytearray."""
    adj = graph._adj_int
    v_count = graph._v_count
    color = bytearray(v_count)

    for start_node in range(v_count):
        if color[start_node] != 0:
            continue

        color[start_node] = 1
        children = adj[start_node]
        stack = [[start_node, 0, children, len(children)]]

        while stack:
            frame = stack[-1]
            index = frame[1]
            if index < frame[3]:
                target = frame[2][index]
                frame[1] = index + 1
                state = color[target]
                if state == 1:
                    return False
                if state == 0:
                    color[target] = 1
                    target_children = adj[target]
                    stack.append(
                        [target, 0, target_children, len(target_children)]
                    )
            else:
                stack.pop()
                color[frame[0]] = 2

    return True


def timed_call(fn: Callable[[ObservationAdjacencyGraph], bool],
               graph: ObservationAdjacencyGraph) -> tuple[int, bool]:
    start = time.perf_counter_ns()
    result = fn(graph)
    elapsed = time.perf_counter_ns() - start
    return elapsed, result


def descriptive(samples: list[int]) -> dict[str, float | int | list[int]]:
    ordered = sorted(samples)
    median = statistics.median(ordered)
    q1, _, q3 = statistics.quantiles(ordered, n=4, method="inclusive")
    return {
        "samples_ns": samples,
        "min_ns": min(ordered),
        "median_ns": median,
        "max_ns": max(ordered),
        "mean_ns": statistics.mean(ordered),
        "stdev_ns": statistics.stdev(ordered) if len(ordered) > 1 else 0.0,
        "q1_ns": q1,
        "q3_ns": q3,
        "iqr_ns": q3 - q1,
        "iqr_over_median": (q3 - q1) / median if median else 0.0,
    }


def run_pairs(
    graph: ObservationAdjacencyGraph, repeats: int
) -> tuple[list[int], list[int]]:
    # Warm-up is deliberately outside timed samples.
    for _ in range(3):
        control = control_is_acyclic(graph)
        intervention = intervention_a_is_acyclic(graph)
        if control != intervention:
            raise AssertionError("control/intervention semantic mismatch")

    control_samples: list[int] = []
    intervention_samples: list[int] = []

    for _ in range(repeats):
        control_ns, control = timed_call(control_is_acyclic, graph)
        intervention_ns, intervention = timed_call(
            intervention_a_is_acyclic, graph
        )
        if control != intervention:
            raise AssertionError("control/intervention semantic mismatch")
        control_samples.append(control_ns)
        intervention_samples.append(intervention_ns)

    return control_samples, intervention_samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    if args.repeats < DEFAULT_REPEATS:
        raise SystemExit(f"--repeats must be >= {DEFAULT_REPEATS}")

    target_commit = resolve_target_commit()
    graph = build_graph()

    control_samples, intervention_samples = run_pairs(graph, args.repeats)
    control = descriptive(control_samples)
    intervention = descriptive(intervention_samples)
    median_delta = intervention["median_ns"] - control["median_ns"]
    relative_delta = (
        median_delta / control["median_ns"]
        if control["median_ns"]
        else 0.0
    )

    payload = {
        "experiment": "EXP-21-PHASE2-STEP3-INTERVENTION-A",
        "status": "MEASURED",
        "target_commit": target_commit,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "intervention_id": INTERVENTION_ID,
        "intervention": {
            "component": "is_acyclic color buffer",
            "control": "list[int], states 0/1/2",
            "treatment": "bytearray, states 0/1/2",
            "algorithm_otherwise_identical": True,
        },
        "workload": {
            "edge_count": EDGE_COUNT,
            "chain_edges": CHAIN_EDGES,
            "offset_edges": OFFSET_EDGES,
            "graph_construction": "UNTIMED",
        },
        "measurement": {
            "clock": "time.perf_counter_ns",
            "repeats": args.repeats,
            "pairing": "CONTROL_THEN_INTERVENTION",
            "warmup_runs_per_variant": 3,
            "instrumentation_in_timed_regions": [],
            "tracemalloc": False,
            "cProfile": False,
        },
        "control": control,
        "intervention_a": intervention,
        "comparison": {
            "median_delta_ns": median_delta,
            "relative_delta": relative_delta,
            "direction_observed": (
                "INTERVENTION_LOWER"
                if median_delta < 0
                else "INTERVENTION_NOT_LOWER"
            ),
        },
        "interpretation": {
            "verdict": "NOT_EVALUATED",
            "causal_acceptance_threshold": "EXTERNAL_PREDEFINED_CONTRACT",
            "note": (
                "This artifact contains telemetry and descriptive comparison "
                "only. No CAUSAL/FALSIFIED verdict is generated by the runner."
            ),
        },
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "frozen_core": {
            "base_commit": FROZEN_CORE_BASE,
            "expected_delta": "ZERO",
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "artifact": str(args.output),
                "artifact_sha256": digest,
                "target_commit": target_commit,
                "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
                "status": "MEASURED",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
