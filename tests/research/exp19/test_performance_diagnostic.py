"""Read-only performance diagnostics for EXP-19.R1.

This diagnostic does not alter production code or the EXP-19 contract test.
It reports build/acyclic/reachable timings and scale behavior.
"""

from __future__ import annotations

import gc
import statistics
import time

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation


def _graph(edge_count: int) -> ObservationAdjacencyGraph:
    edges = [
        ObservationRelation(str(i), str(i + 1), "adjacent", {})
        for i in range(edge_count // 2)
    ]
    edges.extend(
        ObservationRelation(str(i), str(i + edge_count // 2), "adjacent", {})
        for i in range(edge_count // 2)
    )
    return ObservationAdjacencyGraph(tuple(edges))


def _measure(
    edge_count: int, repeats: int = 25
) -> tuple[list[float], list[float], list[float]]:
    build: list[float] = []
    acyclic: list[float] = []
    reachable: list[float] = []

    for _ in range(repeats + 5):
        gc.collect()

        start = time.perf_counter()
        graph = _graph(edge_count)
        build_elapsed = time.perf_counter() - start

        start = time.perf_counter()
        assert graph.is_acyclic() is True
        acyclic_elapsed = time.perf_counter() - start

        start = time.perf_counter()
        graph.reachable("0")
        reachable_elapsed = time.perf_counter() - start

        if len(build) >= 0:
            build.append(build_elapsed)
            acyclic.append(acyclic_elapsed)
            reachable.append(reachable_elapsed)

    return build[5:], acyclic[5:], reachable[5:]


def _summary(values: list[float]) -> tuple[float, float, float]:
    ordered = sorted(values)
    p50 = statistics.median(ordered)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    p99 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))]
    return p50, p95, p99


def test_exp19_performance_diagnostic() -> None:
    for edge_count in (5_000, 10_000, 20_000, 40_000):
        build, acyclic, reachable = _measure(edge_count)
        b = _summary(build)
        a = _summary(acyclic)
        r = _summary(reachable)
        print(
            f"EXP19_DIAG E={edge_count} "
            f"build_p50/p95/p99={b[0]:.6f}/{b[1]:.6f}/{b[2]:.6f} "
            f"acyclic_p50/p95/p99={a[0]:.6f}/{a[1]:.6f}/{a[2]:.6f} "
            f"reachable_p50/p95/p99={r[0]:.6f}/{r[1]:.6f}/{r[2]:.6f}"
        )
