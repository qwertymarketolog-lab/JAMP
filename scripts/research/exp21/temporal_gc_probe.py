"""Read-only temporal GC probe against the exact historical EXP-19 G4 workload.

The workload and measurement boundary are inherited from
8c6b6a40f019d727a1ef630975a2691a390affd6. No GC policy, threshold, enablement,
or Frozen Core code is modified.
"""

from __future__ import annotations

import contextlib
import gc
import json
import statistics
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from tests.research.exp19.test_adjacency_graph import (
    test_g4_large_graph_is_linear_scale as canonical_g4,
)

EXPERIMENT_ID = "EXP-21-TEMPORAL-GC-PROBE-V2"
TARGET_COMMIT = "8c6b6a40f019d727a1ef630975a2691a390affd6"
WORKLOAD_SPEC_ID = "EXP-21-PHASE0-G4-CANONICAL-V1"
WORKLOAD_DEFINITION_HASH = (
    "f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
)
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
CONTRACT_MS = 15.0
N = 40
HISTORICAL_TAILS = (2, 15, 22, 35)
REAL_PERF_COUNTER = time.perf_counter
REAL_PROCESS_TIME = time.process_time
ARTIFACT = Path("artifacts/research/exp21_temporal_gc_probe.json")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _gc_stats() -> list[int]:
    stats = gc.get_stats()
    if len(stats) != 3:
        raise RuntimeError(f"unexpected gc generations: {len(stats)}")
    return [int(item["collections"]) for item in stats]


def _run_lap(index: int) -> dict[str, object]:
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

    gc_before = _gc_stats()
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
    gc_after = _gc_stats()

    return {
        "index": index,
        "wall_ms": wall_ns / 1_000_000,
        "cpu_ms": cpu_ns / 1_000_000,
        "wall_cpu_delta_ms": (wall_ns - cpu_ns) / 1_000_000,
        "acyclic_ms": lap["acyclic_ns"] / 1_000_000,
        "reachable_ms": lap["reachable_ns"] / 1_000_000,
        "component_sum_ms": (
            lap["acyclic_ns"] + lap["reachable_ns"]
        ) / 1_000_000,
        "gc_before_collections": gc_before,
        "gc_after_collections": gc_after,
        "gc_delta_collections": [
            after - before for before, after in zip(gc_before, gc_after)
        ],
    }


def main() -> int:
    actual_commit = _git("rev-parse", "HEAD")
    core_blob = _git("hash-object", "src/jamp/run.py")
    validation_errors: list[str] = []

    if actual_commit != TARGET_COMMIT:
        validation_errors.append("target_commit_mismatch")
    if core_blob != FROZEN_CORE_BLOB:
        validation_errors.append("frozen_core_blob_mismatch")

    rows = [_run_lap(index) for index in range(1, N + 1)]
    tails = [
        int(row["index"])
        for row in rows
        if float(row["component_sum_ms"]) > CONTRACT_MS
    ]
    historical = {
        str(index): next(row for row in rows if int(row["index"]) == index)
        for index in HISTORICAL_TAILS
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "target_commit": TARGET_COMMIT,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "frozen_core_blob": core_blob,
        "n_laps": N,
        "contract_ms": CONTRACT_MS,
        "measurement_boundary": (
            "same canonical G4 boundary as historical EXP-19 sweep: "
            "wall/cpu immediately around canonical_g4()"
        ),
        "gc_delta_semantics": (
            "gc.get_stats()[generation]['collections'] after - before each "
            "canonical G4 lap"
        ),
        "historical_tail_indices": list(HISTORICAL_TAILS),
        "observed_tail_indices": tails,
        "rows": rows,
        "historical_rows": historical,
        "summary": {
            "tail_count": len(tails),
            "wall_p50_ms": statistics.median(float(r["wall_ms"]) for r in rows),
            "cpu_p50_ms": statistics.median(float(r["cpu_ms"]) for r in rows),
            "component_sum_p50_ms": statistics.median(
                float(r["component_sum_ms"]) for r in rows
            ),
            "max_abs_wall_cpu_delta_ms": max(
                abs(float(r["wall_cpu_delta_ms"])) for r in rows
            ),
            "laps_with_any_gc_collection": [
                int(r["index"])
                for r in rows
                if any(int(v) > 0 for v in r["gc_delta_collections"])
            ],
        },
        "validation_errors": validation_errors,
        "status": "VERIFIED" if not validation_errors and len(rows) == N else "INCONCLUSIVE",
    }

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    for index in HISTORICAL_TAILS:
        row = historical[str(index)]
        print(
            f"historical_lap={index} "
            f"wall_ms={row['wall_ms']:.6f} "
            f"cpu_ms={row['cpu_ms']:.6f} "
            f"acyclic_ms={row['acyclic_ms']:.6f} "
            f"reachable_ms={row['reachable_ms']:.6f} "
            f"gc_delta={row['gc_delta_collections']}"
        )

    return 0 if payload["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
