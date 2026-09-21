"""Research-only decomposition of the canonical EXP-21 G4 graph hot path.

No tracemalloc/cProfile/other hooks are used inside timed regions.
No JAMP core/runtime code is modified.

The microbenchmarks are comparative measurements. They do not establish that
any measured operation causes the G4 wall-clock contract breach.
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
EDGE_COUNT = 20_000
CHAIN_EDGES = 10_000
OFFSET_EDGES = 10_000
DEFAULT_REPEATS = 11
DEFAULT_INNER = 1
OUTPUT = Path("artifacts/research/exp21_phase2_hotpath_cost.json")

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


def timed_ns(fn: Callable[[], object], repeats: int, inner: int) -> list[int]:
    samples: list[int] = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            fn()
        samples.append(time.perf_counter_ns() - start)
    return samples


def summary(samples: list[int], units: int) -> dict[str, float | int | list[int]]:
    ordered = sorted(samples)
    median_ns = statistics.median(ordered)
    return {
        "samples_ns": samples,
        "min_ns": min(ordered),
        "median_ns": median_ns,
        "max_ns": max(ordered),
        "mean_ns": statistics.mean(ordered),
        "stdev_ns": statistics.stdev(ordered) if len(ordered) > 1 else 0.0,
        "units": units,
        "median_ns_per_unit": median_ns / units,
    }


def run_benchmarks(graph: ObservationAdjacencyGraph, repeats: int, inner: int) -> dict:
    adj = graph._adj_int
    node_to_idx = graph._node_to_idx
    idx_to_node = graph._idx_to_node
    all_indices = list(range(len(adj)))
    all_targets = [target for targets in adj for target in targets]
    all_keys = list(node_to_idx)
    visited = set(all_indices)
    popleft_like = list(all_indices)
    noop_result = 0

    def noop() -> int:
        return 1

    def string_dict_lookup() -> None:
        nonlocal noop_result
        value = 0
        for key in all_keys:
            value += node_to_idx.get(key, -1)
        noop_result = value

    def adjacency_access() -> None:
        nonlocal noop_result
        value = 0
        for index in all_indices:
            value += len(adj[index])
        noop_result = value

    def adjacency_iteration() -> None:
        nonlocal noop_result
        value = 0
        for targets in adj:
            for target in targets:
                value += target
        noop_result = value

    def state_membership() -> None:
        nonlocal noop_result
        value = 0
        for target in all_targets:
            if target in visited:
                value += 1
        noop_result = value

    def state_update() -> None:
        nonlocal noop_result
        local = set()
        for target in all_targets:
            local.add(target)
        noop_result = len(local)

    def index_to_string_lookup() -> None:
        nonlocal noop_result
        value = 0
        for index in all_indices:
            value += len(idx_to_node[index])
        noop_result = value

    def empty_function_calls() -> None:
        nonlocal noop_result
        value = 0
        for _ in all_targets:
            value += noop()
        noop_result = value

    # The actual G4 operations: graph construction remains outside timed blocks.
    def g4_acyclic() -> None:
        nonlocal noop_result
        noop_result = int(graph.is_acyclic())

    def g4_reachable() -> None:
        nonlocal noop_result
        noop_result = len(graph.reachable("0"))

    benchmarks = [
        ("string_dict_lookup", string_dict_lookup, len(all_keys)),
        ("adjacency_access", adjacency_access, len(all_indices)),
        ("adjacency_iteration", adjacency_iteration, len(all_targets)),
        ("state_membership", state_membership, len(all_targets)),
        ("state_update", state_update, len(all_targets)),
        ("index_to_string_lookup", index_to_string_lookup, len(all_indices)),
        ("empty_function_calls", empty_function_calls, len(all_targets)),
        ("is_acyclic_hotpath", g4_acyclic, 1),
        ("reachable_hotpath", g4_reachable, 1),
    ]

    results = {}
    for name, fn, units in benchmarks:
        for _ in range(3):
            fn()
        results[name] = summary(timed_ns(fn, repeats, inner), units * inner)

    # Prevent an over-aggressive optimizer/interpreter change from making the
    # benchmark semantically empty. CPython does not currently optimize these
    # loops away, but retaining the sink makes the intent explicit.
    if noop_result < 0:
        raise AssertionError("unreachable benchmark sink")

    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--inner", type=int, default=DEFAULT_INNER)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    if args.repeats < 5:
        raise SystemExit("--repeats must be >= 5")
    if args.inner < 1:
        raise SystemExit("--inner must be >= 1")

    target_commit = resolve_target_commit()
    graph = build_graph()

    results = run_benchmarks(graph, args.repeats, args.inner)

    payload = {
        "experiment": "EXP-21-PHASE2-HOTPATH-COST",
        "status": "MEASURED",
        "target_commit": target_commit,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "workload": {
            "edge_count": EDGE_COUNT,
            "chain_edges": CHAIN_EDGES,
            "offset_edges": OFFSET_EDGES,
            "graph_construction": "UNTIMED",
        },
        "measurement": {
            "clock": "time.perf_counter_ns",
            "repeats": args.repeats,
            "inner": args.inner,
            "instrumentation_in_timed_regions": [],
            "tracemalloc": False,
            "cProfile": False,
        },
        "benchmarks": results,
        "interpretation": {
            "hotpath_aggregate": [
                "is_acyclic_hotpath",
                "reachable_hotpath",
            ],
            "micro_components": [
                "string_dict_lookup",
                "adjacency_access",
                "adjacency_iteration",
                "state_membership",
                "state_update",
                "index_to_string_lookup",
                "empty_function_calls",
            ],
            "string_key_boundary": (
                "The canonical is_acyclic() traversal uses integer adjacency; "
                "string-key lookup is therefore measured separately and is not "
                "assumed to be a dominant hot-loop component."
            ),
            "causality": "NOT_ESTABLISHED",
            "hypothesis_test": (
                "Relative operation costs are observed; no operation is declared "
                "the cause of G4 latency without an independent causal intervention."
            ),
        },
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "frozen_core": {
            "base_commit": "af2292bbfc8518716bdf5b76614efb33ed9496f0",
            "expected_delta": "ZERO",
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(json.dumps({
        "artifact": str(args.output),
        "artifact_sha256": digest,
        "target_commit": target_commit,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "status": "MEASURED",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
