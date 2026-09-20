"""EXP-19 Vector #3: single-factor sys.setswitchinterval sweep, read-only."""

from __future__ import annotations

import contextlib
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
CONTRACT_MS = 15.0
N = 40
INTERVALS = (0.001, 0.005, 0.050)


def _run_mode(interval: float) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    original_acyclic = ObservationAdjacencyGraph.is_acyclic
    original_reachable = ObservationAdjacencyGraph.reachable
    previous = sys.getswitchinterval()
    sys.setswitchinterval(interval)
    try:
        for index in range(N):
            lap: dict[str, int] = {}

            def traced_acyclic(
                self: ObservationAdjacencyGraph,
                lap: dict[str, int] = lap,
            ) -> bool:
                start = REAL_PERF_COUNTER()
                try:
                    return original_acyclic(self)
                finally:
                    lap["acyclic_ns"] = int((REAL_PERF_COUNTER() - start) * 1_000_000_000)

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

            wall_start = REAL_PERF_COUNTER()
            cpu_start = REAL_PROCESS_TIME()
            with (
                patch.object(ObservationAdjacencyGraph, "is_acyclic", traced_acyclic),
                patch.object(ObservationAdjacencyGraph, "reachable", traced_reachable),
                contextlib.suppress(AssertionError),
            ):
                canonical_g4()
            wall_ns = int((REAL_PERF_COUNTER() - wall_start) * 1_000_000_000)
            cpu_ns = int((REAL_PROCESS_TIME() - cpu_start) * 1_000_000_000)
            rows.append(
                {
                    "i": index + 1,
                    "acyclic_ms": lap["acyclic_ns"] / 1_000_000,
                    "reachable_ms": lap["reachable_ns"] / 1_000_000,
                    "elapsed_ms": (lap["acyclic_ns"] + lap["reachable_ns"]) / 1_000_000,
                    "wall_cpu_delta_ms": (wall_ns - cpu_ns) / 1_000_000,
                }
            )
    finally:
        sys.setswitchinterval(previous)
    return rows


def _summarize(interval: float, rows: list[dict[str, float]]) -> None:
    elapsed = [row["elapsed_ms"] for row in rows]
    acyclic = [row["acyclic_ms"] for row in rows]
    reachable = [row["reachable_ms"] for row in rows]
    tails = [row for row in rows if row["elapsed_ms"] > CONTRACT_MS]
    print(f"MODE interval_s={interval:.3f} N={len(rows)}")
    print(f"tail_count={len(tails)}")
    print(f"tail_indices={[int(row['i']) for row in tails]}")
    print(f"p50_ms={statistics.median(elapsed):.3f}")
    print(f"p95_ms={statistics.quantiles(elapsed, n=20, method='inclusive')[-1]:.3f}")
    print(f"max_ms={max(elapsed):.3f}")
    print(f"acyclic_p50_ms={statistics.median(acyclic):.3f}")
    print(f"reachable_p50_ms={statistics.median(reachable):.3f}")
    print(
        f"wall_cpu_delta_abs_max_ms={max(abs(row['wall_cpu_delta_ms']) for row in rows):.3f}"
    )
    print(f"rows={rows}")


def test_vector3_switchinterval_sweep() -> None:
    print("EXP-19 VECTOR #3 — READ ONLY — SWITCHINTERVAL SWEEP")
    print(f"contract_ms={CONTRACT_MS:.3f}")
    print(f"intervals={INTERVALS}")
    for interval in INTERVALS:
        _summarize(interval, _run_mode(interval))
