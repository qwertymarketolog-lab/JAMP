"""Read-only performance diagnostics for EXP-19.R1.

This diagnostic does not alter production code or the EXP-19 contract test.
It reports build/acyclic/reachable timings and scale behavior.
"""

from __future__ import annotations

import gc
import json
import os
import statistics
import time
import warnings

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation


def _graph(edge_count: int) -> ObservationAdjacencyGraph:
    edges = [
        ObservationRelation(str(i), str(i + 1), "adjacent", {}) for i in range(edge_count // 2)
    ]
    edges.extend(
        ObservationRelation(str(i), str(i + edge_count // 2), "adjacent", {})
        for i in range(edge_count // 2)
    )
    return ObservationAdjacencyGraph(tuple(edges))


def _measure(edge_count: int, repeats: int = 25) -> tuple[list[float], list[float], list[float]]:
    build: list[float] = []
    acyclic: list[float] = []
    reachable: list[float] = []

    for iteration in range(repeats + 5):
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

        if iteration >= 5:
            build.append(build_elapsed)
            acyclic.append(acyclic_elapsed)
            reachable.append(reachable_elapsed)

    return build, acyclic, reachable


def _summary(values: list[float]) -> tuple[float, float, float]:
    ordered = sorted(values)
    p50 = statistics.median(ordered)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    p99 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))]
    return p50, p95, p99


def _export_summary(rows: list[dict[str, object]]) -> None:
    payload = json.dumps(rows, separators=(",", ":"), sort_keys=True)
    warnings.warn(
        f"EXP19_DIAG_PAYLOAD: {payload}",
        UserWarning,
        stacklevel=2,
    )

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    lines = [
        "## EXP-19 performance diagnostic",
        "",
        "| Edges | build p50/p95/p99 | acyclic p50/p95/p99 | reachable p50/p95/p99 |",
        "| ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['edges']} | "
            f"{row['build_p50']:.6f}/{row['build_p95']:.6f}/{row['build_p99']:.6f} | "
            f"{row['acyclic_p50']:.6f}/{row['acyclic_p95']:.6f}/{row['acyclic_p99']:.6f} | "
            f"{row['reachable_p50']:.6f}/{row['reachable_p95']:.6f}/{row['reachable_p99']:.6f} |"
        )

    with open(summary_path, "a", encoding="utf-8") as summary:
        summary.write("\n".join(lines) + "\n")


def test_exp19_performance_diagnostic() -> None:
    rows: list[dict[str, object]] = []

    for edge_count in (5_000, 10_000, 20_000, 40_000):
        build, acyclic, reachable = _measure(edge_count)
        b = _summary(build)
        a = _summary(acyclic)
        r = _summary(reachable)
        rows.append(
            {
                "edges": edge_count,
                "build_p50": b[0],
                "build_p95": b[1],
                "build_p99": b[2],
                "acyclic_p50": a[0],
                "acyclic_p95": a[1],
                "acyclic_p99": a[2],
                "reachable_p50": r[0],
                "reachable_p95": r[1],
                "reachable_p99": r[2],
            }
        )

    _export_summary(rows)
