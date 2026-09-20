"""EXP-19 pytest wall-vs-process CPU diagnostic. Research-only; no production changes."""

from __future__ import annotations

import statistics
import time

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation


EDGES = [(str(i), str(i + 1)) for i in range(10_000)]
EDGES.extend((str(i), str(i + 10_000)) for i in range(10_000))


def graph() -> ObservationAdjacencyGraph:
    return ObservationAdjacencyGraph(
        tuple(ObservationRelation(s, t, "adjacent", {}) for s, t in EDGES)
    )


def measure(repeats: int = 10) -> list[tuple[float, float, float, float]]:
    rows = []
    for _ in range(repeats):
        g = graph()
        wall_start = time.perf_counter_ns()
        cpu_start = time.process_time_ns()

        assert g.is_acyclic() is True
        g.reachable("0")

        cpu_end = time.process_time_ns()
        wall_end = time.perf_counter_ns()

        wall_ms = (wall_end - wall_start) / 1_000_000
        cpu_ms = (cpu_end - cpu_start) / 1_000_000
        rows.append((wall_ms, cpu_ms, wall_ms - cpu_ms, wall_ms / cpu_ms))
    return rows


def test_pytest_wall_vs_process_cpu_diagnostic() -> None:
    print("EXP-19 PYTEST WALL VS PROCESS CPU — READ ONLY")
    rows = measure()

    wall = [row[0] for row in rows]
    cpu = [row[1] for row in rows]
    gap = [row[2] for row in rows]
    ratio = [row[3] for row in rows]

    print(
        "wall_ms: "
        f"median={statistics.median(wall):.3f} "
        f"min={min(wall):.3f} max={max(wall):.3f} "
        f"samples={[round(x, 3) for x in wall]}"
    )
    print(
        "cpu_ms: "
        f"median={statistics.median(cpu):.3f} "
        f"min={min(cpu):.3f} max={max(cpu):.3f} "
        f"samples={[round(x, 3) for x in cpu]}"
    )
    print(
        "wall_minus_cpu_ms: "
        f"median={statistics.median(gap):.3f} "
        f"min={min(gap):.3f} max={max(gap):.3f} "
        f"samples={[round(x, 3) for x in gap]}"
    )
    print(
        "wall_cpu_ratio: "
        f"median={statistics.median(ratio):.3f} "
        f"min={min(ratio):.3f} max={max(ratio):.3f} "
        f"samples={[round(x, 3) for x in ratio]}"
    )
    print("contract_ms=15.000")
