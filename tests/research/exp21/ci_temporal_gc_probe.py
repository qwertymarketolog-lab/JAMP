"""EXP-21 temporal GC probe against the exact historical EXP-19 workload.

Read-only probe. The workload and measurement boundary are inherited from
commit 8c6b6a40f019d727a1ef630975a2691a390affd6.
"""

from __future__ import annotations

import contextlib
import gc
import json
import statistics
import time
from pathlib import Path
from unittest.mock import patch

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from tests.research.exp19.test_adjacency_graph import (
    test_g4_large_graph_is_linear_scale as canonical_g4,
)

TARGET_COMMIT = "8c6b6a40f019d727a1ef630975a2691a390affd6"
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
CONTRACT_MS = 15.0
N = 40
HISTORICAL_TAILS = (2, 15, 22, 35)
REAL_PERF_COUNTER = time.perf_counter
REAL_PROCESS_TIME = time.process_time


def _gc_snapshot() -> list[int]:
    return [int(item["collections"]) for item in gc.get_stats()]


def _run_once(index: int) -> dict[str, object]:
    lap: dict[str, int] = {}
    original_acyclic = ObservationAdjacencyGraph.is_acyclic
    original_reachable = ObservationAdjacencyGraph.reachable

    def traced_acyclic(
        self: ObservationAdjacencyGraph,
        lap: dict[str, int] = lap,
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

    gc_before = _gc_snapshot()
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
    gc_after = _gc_snapshot()

    if len(gc_before) != 3 or len(gc_after) != 3:
        raise RuntimeError("unexpected gc.get_stats() generation count")

    gc_delta = [after - before for before, after in zip(gc_before, gc_after)]

    return {
        "i": index,
        "wall_ms": wall_ns / 1_000_000,
        "cpu_ms": cpu_ns / 1_000_000,
        "wall_cpu_delta_ms": (wall_ns - cpu_ns) / 1_000_000,
        "acyclic_ms": lap["acyclic_ns"] / 1_000_000,
        "reachable_ms": lap["reachable_ns"] / 1_000_000,
        "component_sum_ms": (
            lap["acyclic_ns"] + lap["reachable_ns"]
        )
        / 1_000_000,
        "gc_before": gc_before,
        "gc_after": gc_after,
        "gc_delta": gc_delta,
    }


def main() -> None:
    rows = [_run_once(index) for index in range(1, N + 1)]
    tails = [
        int(row["i"])
        for row in rows
        if float(row["component_sum_ms"]) > CONTRACT_MS
    ]

    historical = {
        str(index): next(row for row in rows if int(row["i"]) == index)
        for index in HISTORICAL_TAILS
    }

    payload = {
        "experiment": "EXP-21-TEMPORAL-GC-PROBE",
        "target_commit": TARGET_COMMIT,
        "frozen_core_blob_expected": FROZEN_CORE_BLOB,
        "workload": "tests.research.exp19.test_adjacency_graph.test_g4_large_graph_is_linear_scale",
        "measurement_boundary": "wall/cpu starts immediately before canonical_g4() and ends immediately after it",
        "n": N,
        "contract_ms": CONTRACT_MS,
        "historical_tail_indices": list(HISTORICAL_TAILS),
        "observed_tail_indices": tails,
        "tail_count": len(tails),
        "gc_delta_semantics": "gc.get_stats()[gen]['collections'] after - before each canonical G4 lap",
        "rows": rows,
        "historical_rows": historical,
        "summary": {
            "wall_p50_ms": statistics.median(float(r["wall_ms"]) for r in rows),
            "cpu_p50_ms": statistics.median(float(r["cpu_ms"]) for r in rows),
            "component_sum_p50_ms": statistics.median(
                float(r["component_sum_ms"]) for r in rows
            ),
            "max_abs_wall_cpu_delta_ms": max(
                abs(float(r["wall_cpu_delta_ms"])) for r in rows
            ),
        },
    }

    output = Path("artifacts/research/exp21_temporal_gc_probe.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\\n")
    print(json.dumps(payload["summary"], sort_keys=True))
    print(f"observed_tail_indices={tails}")
    for index in HISTORICAL_TAILS:
        row = historical[str(index)]
        print(
            f"historical_lap={index} wall_ms={row['wall_ms']:.6f} "
            f"cpu_ms={row['cpu_ms']:.6f} component_sum_ms={row['component_sum_ms']:.6f} "
            f"gc_delta={row['gc_delta']}"
        )


if __name__ == "__main__":
    main()
