"""EXP-19 in-place lap replication. Research-only; mirrors G4 timing body."""
from __future__ import annotations

import statistics
import time

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation


def relation(source: str, target: str) -> ObservationRelation:
    return ObservationRelation(source, target, "adjacent", {})


def graph(edges: list[tuple[str, str]]) -> ObservationAdjacencyGraph:
    return ObservationAdjacencyGraph(tuple(relation(s, t) for s, t in edges))


def measure(repeats: int = 10) -> list[tuple[float, float, float]]:
    rows = []
    for _ in range(repeats):
        edges = [(str(i), str(i + 1)) for i in range(10_000)]
        edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
        g = graph(edges)

        start = time.perf_counter_ns()
        lap_0 = start
        res_acyclic = g.is_acyclic()
        lap_1 = time.perf_counter_ns()
        res_reachable = g.reachable("0")
        lap_2 = time.perf_counter_ns()

        assert res_acyclic is True
        assert res_reachable is not None
        rows.append(
            (
                (lap_1 - lap_0) / 1_000_000,
                (lap_2 - lap_1) / 1_000_000,
                (lap_2 - start) / 1_000_000,
            )
        )
    return rows


def test_exp19_in_place_lap_replication() -> None:
    print("EXP-19 IN-PLACE LAP REPLICATION — READ ONLY")
    rows = measure()

    acyclic = [row[0] for row in rows]
    reachable = [row[1] for row in rows]
    combined = [row[2] for row in rows]

    for name, values in (
        ("lap_acyclic_ms", acyclic),
        ("lap_reachable_ms", reachable),
        ("combined_ms", combined),
    ):
        print(
            f"{name}: median={statistics.median(values):.3f} "
            f"min={min(values):.3f} max={max(values):.3f} "
            f"samples={[round(x, 3) for x in values]}"
        )
    print("contract_ms=15.000")
