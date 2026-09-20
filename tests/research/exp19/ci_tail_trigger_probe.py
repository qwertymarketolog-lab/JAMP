"""EXP-19 read-only tail-trigger probe: canonical G4 x40 with runtime-state telemetry."""
from __future__ import annotations

import contextlib
import gc
import statistics
import sys
import time
from unittest.mock import patch

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from tests.research.exp19.test_adjacency_graph import (
    test_g4_large_graph_is_linear_scale as canonical_g4,
)

REAL_PERF_COUNTER = time.perf_counter
REAL_PROCESS_TIME = time.process_time


def _gc_counts() -> tuple[int, int, int]:
    return tuple(int(item["collections"]) for item in gc.get_stats())


def _size_snapshot(graph: ObservationAdjacencyGraph) -> dict[str, int]:
    result: dict[str, int] = {}
    for name in ("_edges", "_node_to_idx", "_idx_to_node", "_adj_int", "_v_count"):
        if hasattr(graph, name):
            value = getattr(graph, name)
            with contextlib.suppress(TypeError):
                result[name] = sys.getsizeof(value)
    return result


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    xbar = statistics.fmean(xs)
    ybar = statistics.fmean(ys)
    num = sum(
        (x - xbar) * (y - ybar) for x, y in zip(xs, ys, strict=True)
    )
    den_x = sum((x - xbar) ** 2 for x in xs)
    den_y = sum((y - ybar) ** 2 for y in ys)
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y) ** 0.5


def test_exp19_tail_trigger_probe_n40() -> None:
    rows: list[dict[str, object]] = []
    original_acyclic = ObservationAdjacencyGraph.is_acyclic
    original_reachable = ObservationAdjacencyGraph.reachable

    for index in range(40):
        gc_before = _gc_counts()
        lap: dict[str, int] = {}

        def traced_acyclic(
            self: ObservationAdjacencyGraph, lap: dict[str, int] = lap
        ) -> bool:
            start = REAL_PERF_COUNTER()
            try:
                return original_acyclic(self)
            finally:
                lap["acyclic_ns"] = int(
                    (REAL_PERF_COUNTER() - start) * 1_000_000_000
                )

        def traced_reachable(
            self: ObservationAdjacencyGraph,
            start_id: str,
            lap: dict[str, int] = lap,
        ) -> frozenset[str]:
            start = REAL_PERF_COUNTER()
            try:
                return original_reachable(self, start_id)
            finally:
                lap["reachable_ns"] = int(
                    (REAL_PERF_COUNTER() - start) * 1_000_000_000
                )

        graph_ref: dict[str, ObservationAdjacencyGraph] = {}

        def capture_acyclic(
            self: ObservationAdjacencyGraph,
            graph_ref: dict[str, ObservationAdjacencyGraph] = graph_ref,
        ) -> bool:
            graph_ref["g"] = self
            return traced_acyclic(self)

        wall_start = REAL_PERF_COUNTER()
        cpu_start = REAL_PROCESS_TIME()
        with (
            patch.object(ObservationAdjacencyGraph, "is_acyclic", capture_acyclic),
            patch.object(ObservationAdjacencyGraph, "reachable", traced_reachable),
            contextlib.suppress(AssertionError),
        ):
            canonical_g4()
        wall_ns = int((REAL_PERF_COUNTER() - wall_start) * 1_000_000_000)
        cpu_ns = int((REAL_PROCESS_TIME() - cpu_start) * 1_000_000_000)

        gc_after = _gc_counts()
        gc_delta = tuple(
            after - before for after, before in zip(gc_after, gc_before, strict=True)
        )
        graph = graph_ref["g"]

        rows.append(
            {
                "i": index + 1,
                "acyclic_ms": lap["acyclic_ns"] / 1_000_000,
                "reachable_ms": lap["reachable_ns"] / 1_000_000,
                "canonical_elapsed_ms": (
                    lap["acyclic_ns"] + lap["reachable_ns"]
                ) / 1_000_000,
                "wall_call_ms": wall_ns / 1_000_000,
                "cpu_call_ms": cpu_ns / 1_000_000,
                "wall_cpu_delta_ms": (wall_ns - cpu_ns) / 1_000_000,
                "gc_gen0": gc_delta[0],
                "gc_gen1": gc_delta[1],
                "gc_gen2": gc_delta[2],
                "graph_sizes": _size_snapshot(graph),
            }
        )

    elapsed = [float(row["canonical_elapsed_ms"]) for row in rows]
    gen0 = [int(row["gc_gen0"]) for row in rows]
    gen1 = [int(row["gc_gen1"]) for row in rows]
    tails = [value > 15.0 for value in elapsed]

    print("EXP-19 TAIL-TRIGGER PROBE — READ ONLY — N=40")
    print("contract_ms=15.000")
    print(f"tail_count={sum(tails)}")
    print(
        f"tail_indices={[row['i'] for row, tail in zip(rows, tails, strict=True) if tail]}"
    )
    print(f"canonical_ms={[round(x, 3) for x in elapsed]}")
    print(f"p50_ms={statistics.median(elapsed):.3f}")
    print(f"p95_ms={statistics.quantiles(elapsed, n=20, method='inclusive')[-1]:.3f}")
    print(f"max_ms={max(elapsed):.3f}")
    print(f"pearson_elapsed_gen0={_pearson(elapsed, [float(x) for x in gen0])}")
    print(f"pearson_elapsed_gen1={_pearson(elapsed, [float(x) for x in gen1])}")
    tail_gc = [
        (row["i"], row["gc_gen0"], row["gc_gen1"])
        for row, tail in zip(rows, tails, strict=True)
        if tail
    ]
    print(f"tail_gc_triggered={tail_gc}")
    print("rows:")
    for row in rows:
        print(row)
