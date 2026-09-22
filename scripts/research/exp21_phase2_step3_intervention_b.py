#!/usr/bin/env python3
"""
Experiment 21 - Phase 2 Step 3: Intervention B (Reachable Single-Factor).

Target: ObservationAdjacencyGraph.reachable() adjacency iteration only.
Frozen Core: Delta src/jamp == 0; this harness imports research-only code.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import time
from collections import deque
from typing import Any

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation


BASELINE_SHA = "29ba828f7cea6e19b6a9a40f5dd9f35952c4959e"
N_RUNS = 11
RELATION_TYPE = "exp21_g4"
G4_CHAIN_EDGES = 10_000
G4_OFFSET_EDGES = 10_000
G4_OFFSET = 5_000


def build_g4_canonical() -> ObservationAdjacencyGraph:
    """Construct canonical G4: 10,000 chain + 10,000 offset relations."""
    relations: list[ObservationRelation] = []

    for i in range(G4_CHAIN_EDGES):
        relations.append(
            ObservationRelation(
                source_id=str(i),
                target_id=str(i + 1),
                relation_type=RELATION_TYPE,
                params={},
            )
        )

    for i in range(G4_OFFSET_EDGES):
        target = (i + G4_OFFSET) % (G4_CHAIN_EDGES + 1)
        if target == i:
            raise AssertionError("Canonical G4 generated a self-loop")
        relations.append(
            ObservationRelation(
                source_id=str(i),
                target_id=str(target),
                relation_type=RELATION_TYPE,
                params={},
            )
        )

    return ObservationAdjacencyGraph(tuple(relations))


def workload_descriptor() -> dict[str, Any]:
    return {
        "graph": "G4",
        "chain_edges": G4_CHAIN_EDGES,
        "offset_edges": G4_OFFSET_EDGES,
        "offset": G4_OFFSET,
        "total_edges": G4_CHAIN_EDGES + G4_OFFSET_EDGES,
        "start_node": "0",
        "relation_type": RELATION_TYPE,
    }


def workload_sha256() -> str:
    raw = json.dumps(
        workload_descriptor(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def control_reachable(
    graph: ObservationAdjacencyGraph,
    start_node: str,
) -> frozenset[str]:
    """Baseline: call the native reachable() implementation unchanged."""
    return graph.reachable(start_node)


def intervention_b_reachable_indexed(
    graph: ObservationAdjacencyGraph,
    start_node: str,
) -> frozenset[str]:
    """
    Single-factor intervention: replace only
    adjacency iteration from for-loop to indexed while.

    Queue, visited semantics, adjacency container, and output semantics
    intentionally match reachable() 1:1.
    """
    node_to_idx = graph._node_to_idx
    start_idx = node_to_idx.get(start_node)
    if start_idx is None:
        return frozenset()

    adj = graph._adj_int
    visited = {start_idx}
    queue = deque([start_idx])
    popleft = queue.popleft
    visited_add = visited.add
    queue_append = queue.append

    while queue:
        node = popleft()
        adj_node = adj[node]
        i = 0
        while i < len(adj_node):
            target = adj_node[i]
            if target not in visited:
                visited_add(target)
                queue_append(target)
            i += 1

    visited.discard(start_idx)
    idx_to_node = graph._idx_to_node
    return frozenset(idx_to_node[index] for index in visited)


def timed_call(fn: Any, graph: ObservationAdjacencyGraph, start_node: str) -> float:
    t0 = time.perf_counter_ns()
    result = fn(graph, start_node)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
    if not isinstance(result, frozenset):
        raise AssertionError("Reachability result type changed")
    return elapsed_ms


def run_paired_telemetry(n_runs: int = N_RUNS) -> dict[str, Any]:
    if n_runs < 11:
        raise ValueError("Intervention B requires N >= 11 paired runs")

    control_times: list[float] = []
    intervention_times: list[float] = []

    # Graph construction is outside each timed region.
    graph = build_g4_canonical()
    for _ in range(n_runs):
        control_times.append(timed_call(control_reachable, graph, "0"))
        intervention_times.append(
            timed_call(intervention_b_reachable_indexed, graph, "0")
        )

    med_control = statistics.median(control_times)
    med_intervention = statistics.median(intervention_times)
    delta_t = med_intervention - med_control

    return {
        "status": "NOT_EVALUATED",
        "baseline_sha": BASELINE_SHA,
        "target": "ObservationAdjacencyGraph.reachable",
        "single_factor": "adjacency iteration: for -> indexed while",
        "n_runs": n_runs,
        "workload": workload_descriptor(),
        "workload_sha256": workload_sha256(),
        "control_median_ms": med_control,
        "intervention_median_ms": med_intervention,
        "delta_t_ms": delta_t,
        "control_raw_ms": control_times,
        "intervention_raw_ms": intervention_times,
        "control_min_ms": min(control_times),
        "control_max_ms": max(control_times),
        "intervention_min_ms": min(intervention_times),
        "intervention_max_ms": max(intervention_times),
        "control_stdev_ms": statistics.stdev(control_times),
        "intervention_stdev_ms": statistics.stdev(intervention_times),
    }


if __name__ == "__main__":
    result = run_paired_telemetry()
    print("=== Intervention B Descriptive Telemetry ===")
    print(json.dumps(result, indent=2, sort_keys=True))
