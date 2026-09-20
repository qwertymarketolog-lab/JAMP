"""EXP-19 pytest-context lap diagnostic. Research-only; no production changes."""
from __future__ import annotations

import gc
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


def measure(disable_gc: bool, repeats: int = 5) -> list[tuple[float, float, float]]:
    rows = []
    for _ in range(repeats):
        g = graph()
        gc.collect()
        if disable_gc:
            gc.disable()
        else:
            gc.enable()
        t0 = time.perf_counter()
        a0 = time.perf_counter()
        assert g.is_acyclic() is True
        a1 = time.perf_counter()
        r0 = time.perf_counter()
        reach = g.reachable("0")
        r1 = time.perf_counter()
        t1 = time.perf_counter()
        assert len(reach) == 19_999
        rows.append((a1 - a0, r1 - r0, t1 - t0))
        gc.enable()
    return rows


def show(label: str, rows: list[tuple[float, float, float]]) -> None:
    vals = [[row[i] * 1000 for row in rows] for i in range(3)]
    print(label)
    for name, values in zip(("lap_acyclic_ms", "lap_reachable_ms", "combined_ms"), vals):
        print(
            f"{name}: median={statistics.median(values):.3f} "
            f"min={min(values):.3f} max={max(values):.3f} "
            f"samples={[round(x, 3) for x in values]}"
        )


def test_pytest_context_lap_diagnostic() -> None:
    print("EXP-19 PYTEST-CONTEXT LAP DIAGNOSTIC — READ ONLY")
    show("gc_enabled_after_collect", measure(False))
    show("gc_disabled_after_collect", measure(True))
    print("contract_ms=15.000")
