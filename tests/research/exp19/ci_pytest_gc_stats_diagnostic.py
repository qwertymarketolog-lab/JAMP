"""EXP-19 pytest-context GC stats diagnostic. Research-only; no production changes."""
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


def measure(repeats: int = 5) -> list[tuple[float, float, tuple, tuple]]:
    rows = []
    for _ in range(repeats):
        g = graph()
        gc.enable()
        before = tuple(
            (item["collections"], item["collected"], item["uncollectable"])
            for item in gc.get_stats()
        )
        t0 = time.perf_counter()
        assert g.is_acyclic() is True
        a1 = time.perf_counter()
        reach = g.reachable("0")
        r1 = time.perf_counter()
        after = tuple(
            (item["collections"], item["collected"], item["uncollectable"])
            for item in gc.get_stats()
        )
        t1 = time.perf_counter()
        assert len(reach) == 19_999
        rows.append((a1 - t0, r1 - a1, before, after))
        print(
            "sample "
            f"acyclic_ms={(a1 - t0) * 1000:.3f} "
            f"reachable_ms={(r1 - a1) * 1000:.3f} "
            f"combined_ms={(t1 - t0) * 1000:.3f} "
            f"gc_before={before} gc_after={after}"
        )
    return rows


def test_pytest_gc_stats_no_preclean() -> None:
    print("EXP-19 PYTEST GC-STATS NO-PRECLEAN — READ ONLY")
    rows = measure()
    combined = [(row[1] + row[0]) * 1000 for row in rows]
    print(
        f"combined_ms: median={statistics.median(combined):.3f} "
        f"min={min(combined):.3f} max={max(combined):.3f} "
        f"samples={[round(x, 3) for x in combined]}"
    )
    print("contract_ms=15.000")
