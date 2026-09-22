"""EXP-21 Phase 2 Step 4 read-only frontier/allocation/dispatch diagnostic.

This harness measures the existing EXP-19 ObservationAdjacencyGraph without
modifying production/runtime code. It intentionally reimplements traversal
only inside the diagnostic to count frontier/edge work.
"""

from __future__ import annotations

import gc
import json
import os
import statistics
import sys
import time
import tracemalloc
from collections import deque
from pathlib import Path

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

SIZES = (64, 128, 256, 512)
REPEATS = 15
WARMUPS = 5


def _graph(layer_size: int) -> ObservationAdjacencyGraph:
    edges: list[ObservationRelation] = []
    for layer in range(3):
        source_base = layer * layer_size
        target_base = (layer + 1) * layer_size
        for i in range(layer_size):
            source = source_base + i
            for offset in (0, 1):
                target = target_base + ((2 * i + offset) % layer_size)
                edges.append(ObservationRelation(str(source), str(target), "adjacent", {}))
    return ObservationAdjacencyGraph(tuple(edges))


def _instrumented_traversal(graph: ObservationAdjacencyGraph, start_id: str) -> dict[str, int]:
    """Mirror reachable() locally so counters do not alter production code."""
    node_to_idx = graph._node_to_idx
    start_idx = node_to_idx.get(start_id)
    if start_idx is None:
        return {
            "frontier_sum": 0,
            "frontier_max": 0,
            "edge_inspections": 0,
            "visited": 0,
            "discovered": 0,
        }

    adj = graph._adj_int
    visited = {start_idx}
    queue = deque([start_idx])
    frontier_sum = 0
    frontier_max = 1
    edge_inspections = 0
    discovered = 1

    while queue:
        frontier = len(queue)
        frontier_sum += frontier
        frontier_max = max(frontier_max, frontier)
        node = queue.popleft()
        for target in adj[node]:
            edge_inspections += 1
            if target not in visited:
                visited.add(target)
                discovered += 1
                queue.append(target)

    visited.discard(start_idx)
    return {
        "frontier_sum": frontier_sum,
        "frontier_max": frontier_max,
        "edge_inspections": edge_inspections,
        "visited": len(visited),
        "discovered": discovered,
    }


def _profiled_reachable(graph: ObservationAdjacencyGraph, start_id: str) -> tuple[float, int]:
    calls = 0

    def profiler(frame, event, arg):  # type: ignore[no-untyped-def]
        nonlocal calls
        if event == "call":
            calls += 1

    old = sys.getprofile()
    sys.setprofile(profiler)
    try:
        start = time.perf_counter()
        graph.reachable(start_id)
        elapsed = time.perf_counter() - start
    finally:
        sys.setprofile(old)
    return elapsed, calls


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "p50": statistics.median(values),
        "p95": sorted(values)[min(len(values) - 1, int(len(values) * 0.95))],
    }


def _canonical_g4_graph() -> ObservationAdjacencyGraph:
    """Reproduce the verified EXP-19 G4 large-graph fixture read-only."""
    edges: list[ObservationRelation] = []
    for i in range(10_000):
        edges.append(ObservationRelation(str(i), str(i + 1), "adjacent", {}))
    for i in range(10_000):
        edges.append(ObservationRelation(str(i), str(i + 10_000), "adjacent", {}))
    return ObservationAdjacencyGraph(tuple(edges))


def _run_start_node_dispersion(sample_size: int = 100) -> dict[str, object]:
    """Sample deterministic start nodes across the verified canonical G4 node space."""
    graph = _canonical_g4_graph()
    node_ids = [str(i) for i in range(20_000)]
    step = (len(node_ids) - 1) / (sample_size - 1)
    starts = [node_ids[round(i * step)] for i in range(sample_size)]

    rows: list[dict[str, object]] = []
    for start_id in starts:
        counters = _instrumented_traversal(graph, start_id)
        peak_bytes: list[int] = []
        for _ in range(3):
            gc.collect()
            tracemalloc.start()
            try:
                graph.reachable(start_id)
                _, peak = tracemalloc.get_traced_memory()
                peak_bytes.append(peak)
            finally:
                tracemalloc.stop()
        rows.append(
            {
                "start_id": start_id,
                "edge_inspections": counters["edge_inspections"],
                "frontier_max": counters["frontier_max"],
                "frontier_sum": counters["frontier_sum"],
                "visited": counters["visited"],
                "discovered": counters["discovered"],
                "tracemalloc_peak_bytes_p50": statistics.median(peak_bytes),
            }
        )

    def percentile(values: list[int], fraction: float) -> float:
        ordered = sorted(values)
        index = min(len(ordered) - 1, int(len(ordered) * fraction))
        return float(ordered[index])

    edge_values = [int(row["edge_inspections"]) for row in rows]
    frontier_max_values = [int(row["frontier_max"]) for row in rows]
    frontier_sum_values = [int(row["frontier_sum"]) for row in rows]
    peak_values = [int(row["tracemalloc_peak_bytes_p50"]) for row in rows]

    return {
        "fixture": {
            "vertices": graph._v_count,
            "edges": sum(len(targets) for targets in graph._adj_int),
            "source": "tests/research/exp19/test_adjacency_graph.py::test_g4_large_graph_is_linear_scale",
            "source_kind": "verified_canonical_fixture",
        },
        "sample_size": sample_size,
        "summary": {
            "edge_inspections": {
                "p50": percentile(edge_values, 0.50),
                "p95": percentile(edge_values, 0.95),
                "p99": percentile(edge_values, 0.99),
                "max": max(edge_values),
            },
            "frontier_max": {
                "p50": percentile(frontier_max_values, 0.50),
                "p95": percentile(frontier_max_values, 0.95),
                "p99": percentile(frontier_max_values, 0.99),
                "max": max(frontier_max_values),
            },
            "frontier_sum": {
                "p50": percentile(frontier_sum_values, 0.50),
                "p95": percentile(frontier_sum_values, 0.95),
                "p99": percentile(frontier_sum_values, 0.99),
                "max": max(frontier_sum_values),
            },
            "tracemalloc_peak_bytes_p50": {
                "p50": percentile(peak_values, 0.50),
                "p95": percentile(peak_values, 0.95),
                "p99": percentile(peak_values, 0.99),
                "max": max(peak_values),
            },
        },
        "rows": rows,
    }


def _run_size(layer_size: int) -> dict[str, object]:
    graph = _graph(layer_size)
    start_id = "0"

    for _ in range(WARMUPS):
        graph.reachable(start_id)

    counters = _instrumented_traversal(graph, start_id)
    timings: list[float] = []
    current_bytes: list[int] = []
    peak_bytes: list[int] = []
    gc_before = gc.get_count()
    gc_stats_before = [item["collections"] for item in gc.get_stats()]

    for _ in range(REPEATS):
        gc.collect()
        tracemalloc.start()
        try:
            start = time.perf_counter()
            graph.reachable(start_id)
            timings.append(time.perf_counter() - start)
            current, peak = tracemalloc.get_traced_memory()
            current_bytes.append(current)
            peak_bytes.append(peak)
        finally:
            tracemalloc.stop()

    gc_after = gc.get_count()
    gc_stats_after = [item["collections"] for item in gc.get_stats()]

    profiled_elapsed, frame_calls = _profiled_reachable(graph, start_id)

    return {
        "layer_size": layer_size,
        "vertices": graph._v_count,
        "edges": sum(len(targets) for targets in graph._adj_int),
        "frontier_sum": counters["frontier_sum"],
        "frontier_max": counters["frontier_max"],
        "edge_inspections": counters["edge_inspections"],
        "visited": counters["visited"],
        "discovered": counters["discovered"],
        "visited_discovered_ratio": (
            counters["visited"] / counters["discovered"] if counters["discovered"] else 0.0
        ),
        "reachable_seconds": _stats(timings),
        "tracemalloc_current_bytes_p50": statistics.median(current_bytes),
        "tracemalloc_peak_bytes_p50": statistics.median(peak_bytes),
        "gc_count_before": list(gc_before),
        "gc_count_after": list(gc_after),
        "gc_collections_delta": [
            after - before for before, after in zip(gc_stats_before, gc_stats_after, strict=True)
        ],
        "profiled_reachable_seconds": profiled_elapsed,
        "profiled_python_call_events": frame_calls,
    }


def main() -> None:
    rows = [_run_size(size) for size in SIZES]
    payload = {
        "experiment": "EXP-21 Phase 2 Step 4",
        "diagnostic": "frontier_allocation_dispatch",
        "production_runtime_impact": 0.0,
        "frozen_core_scope": "src/jamp unchanged",
        "python": sys.version,
        "rows": rows,
    }

    output = Path(
        os.environ.get(
            "EXP21_STEP4_OUTPUT",
            "artifacts/exp21-step4/diagnostic.json",
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
