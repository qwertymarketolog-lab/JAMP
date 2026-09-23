"""EXP-21 exact-boundary reconciliation: EXP-19 tail-trigger + temporal GC observer.

Read-only probe. The measured application boundary is intentionally identical
to tests/research/exp19/ci_tail_trigger_probe.py at TARGET_COMMIT.
"""

from __future__ import annotations

import contextlib
import gc
import hashlib
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

TARGET_COMMIT = "8c6b6a40f019d727a1ef630975a2691a390affd6"
WORKLOAD = "EXP-19-CANONICAL-G4-TAIL-TRIGGER-V1"
CONTRACT_MS = 15.0
N = 40
REAL_PERF_COUNTER = time.perf_counter
REAL_PROCESS_TIME = time.process_time

SOURCE_PATHS = (
    "src/jamp/run.py",
    "research/exp19/adjacency_graph.py",
    "research/exp19/observation_relation.py",
    "tests/research/exp19/test_adjacency_graph.py",
    "tests/research/exp19/ci_tail_trigger_probe.py",
)


def _git(ref_path: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"{TARGET_COMMIT}:{ref_path}"],
        text=True,
    ).strip()


def _head_blob(ref_path: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{ref_path}"],
        text=True,
    ).strip()


def _gc_counts() -> tuple[int, int, int]:
    return tuple(int(item["collections"]) for item in gc.get_stats())


def _hash_workload() -> str:
    source = subprocess.check_output(
        ["git", "show", f"{TARGET_COMMIT}:tests/research/exp19/test_adjacency_graph.py"],
    )
    return hashlib.sha256(source).hexdigest()


def _events_in(
    events: list[dict[str, int | str]],
    start_ns: int,
    end_ns: int,
) -> list[dict[str, int | str]]:
    return [event for event in events if start_ns <= int(event["ts_ns"]) <= end_ns]


def main() -> None:
    repo_root = Path.cwd()
    del repo_root

    validation_errors: list[str] = []
    for path in SOURCE_PATHS:
        target_blob = _git(path)
        head_blob = _head_blob(path)
        if target_blob != head_blob:
            validation_errors.append(
                f"source_drift:{path}:{target_blob}!={head_blob}"
            )

    frozen_blob = _git("src/jamp/run.py")
    if frozen_blob != "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a":
        validation_errors.append(f"frozen_core_target_blob:{frozen_blob}")

    rows: list[dict[str, object]] = []
    gc_events: list[dict[str, int | str]] = []
    original_acyclic = ObservationAdjacencyGraph.is_acyclic
    original_reachable = ObservationAdjacencyGraph.reachable
    callback_installed = False

    def gc_callback(phase: str, info: dict[str, int]) -> None:
        gc_events.append(
            {
                "ts_ns": REAL_PERF_COUNTER() * 1_000_000_000,
                "phase": phase,
                "generation": int(info.get("generation", -1)),
                "collected": int(info.get("collected", -1)),
                "uncollectable": int(info.get("uncollectable", -1)),
            }
        )

    try:
        gc.callbacks.append(gc_callback)
        callback_installed = True

        for index in range(N):
            gc_before = _gc_counts()
            lap: dict[str, int] = {}
            interval_events_start = len(gc_events)

            def traced_acyclic(
                self: ObservationAdjacencyGraph,
                lap: dict[str, int] = lap,
            ) -> bool:
                start = REAL_PERF_COUNTER()
                lap["acyclic_start_ns"] = int(start * 1_000_000_000)
                try:
                    return original_acyclic(self)
                finally:
                    lap["acyclic_end_ns"] = int(
                        REAL_PERF_COUNTER() * 1_000_000_000
                    )
                    lap["acyclic_ns"] = (
                        lap["acyclic_end_ns"] - lap["acyclic_start_ns"]
                    )

            def traced_reachable(
                self: ObservationAdjacencyGraph,
                start_id: str,
                lap: dict[str, int] = lap,
            ) -> frozenset[str]:
                start = REAL_PERF_COUNTER()
                lap["reachable_start_ns"] = int(start * 1_000_000_000)
                try:
                    return original_reachable(self, start_id)
                finally:
                    lap["reachable_end_ns"] = int(
                        REAL_PERF_COUNTER() * 1_000_000_000
                    )
                    lap["reachable_ns"] = (
                        lap["reachable_end_ns"] - lap["reachable_start_ns"]
                    )

            wall_start = REAL_PERF_COUNTER()
            cpu_start = REAL_PROCESS_TIME()
            with (
                patch.object(
                    ObservationAdjacencyGraph, "is_acyclic", traced_acyclic
                ),
                patch.object(
                    ObservationAdjacencyGraph, "reachable", traced_reachable
                ),
                contextlib.suppress(AssertionError),
            ):
                canonical_g4()
            wall_end = REAL_PERF_COUNTER()
            cpu_end = REAL_PROCESS_TIME()

            wall_ns = int((wall_end - wall_start) * 1_000_000_000)
            cpu_ns = int((cpu_end - cpu_start) * 1_000_000_000)
            gc_after = _gc_counts()
            gc_delta = tuple(
                after - before
                for after, before in zip(gc_after, gc_before, strict=True)
            )

            lap_events = gc_events[interval_events_start:]
            acyclic_events = _events_in(
                lap_events,
                lap["acyclic_start_ns"],
                lap["acyclic_end_ns"],
            )
            reachable_events = _events_in(
                lap_events,
                lap["reachable_start_ns"],
                lap["reachable_end_ns"],
            )
            canonical_events = _events_in(
                lap_events,
                int(wall_start * 1_000_000_000),
                int(wall_end * 1_000_000_000),
            )

            rows.append(
                {
                    "i": index + 1,
                    "acyclic_ms": lap["acyclic_ns"] / 1_000_000,
                    "reachable_ms": lap["reachable_ns"] / 1_000_000,
                    "canonical_elapsed_ms": (
                        lap["acyclic_ns"] + lap["reachable_ns"]
                    )
                    / 1_000_000,
                    "wall_call_ms": wall_ns / 1_000_000,
                    "cpu_call_ms": cpu_ns / 1_000_000,
                    "wall_cpu_delta_ms": (wall_ns - cpu_ns) / 1_000_000,
                    "gc_gen0": gc_delta[0],
                    "gc_gen1": gc_delta[1],
                    "gc_gen2": gc_delta[2],
                    "gc_events_in_acyclic": acyclic_events,
                    "gc_events_in_reachable": reachable_events,
                    "gc_events_in_canonical": canonical_events,
                }
            )
    finally:
        if callback_installed:
            with contextlib.suppress(ValueError):
                gc.callbacks.remove(gc_callback)

    elapsed = [float(row["canonical_elapsed_ms"]) for row in rows]
    tails = [
        int(row["i"]) for row in rows if float(row["canonical_elapsed_ms"]) > CONTRACT_MS
    ]
    tail_rows = [row for row in rows if int(row["i"]) in tails]
    event_tails = [
        int(row["i"]) for row in rows if row["gc_events_in_canonical"]
    ]
    event_acyclic = [
        int(row["i"]) for row in rows if row["gc_events_in_acyclic"]
    ]
    event_reachable = [
        int(row["i"]) for row in rows if row["gc_events_in_reachable"]
    ]

    result = {
        "status": "VERIFIED" if not validation_errors else "FAILED_VALIDATION",
        "target_commit": TARGET_COMMIT,
        "workload_id": WORKLOAD,
        "workload_definition_hash": _hash_workload(),
        "measurement_boundary": {
            "outer": "wall_start/cpu_start -> canonical_g4() -> wall_end/cpu_end",
            "acyclic": "inside patched ObservationAdjacencyGraph.is_acyclic",
            "reachable": "inside patched ObservationAdjacencyGraph.reachable",
            "canonical_elapsed": "acyclic + reachable",
            "contract_ms": CONTRACT_MS,
        },
        "n": len(rows),
        "tail_indices": tails,
        "tail_count": len(tails),
        "tail_indices_reference": [2, 15, 22, 35],
        "tails_match_reference": tails == [2, 15, 22, 35],
        "gc_event_laps_canonical": event_tails,
        "gc_event_laps_acyclic": event_acyclic,
        "gc_event_laps_reachable": event_reachable,
        "gc_event_count_total": len(gc_events),
        "gc_enabled_after": gc.isenabled(),
        "gc_callbacks_restored": gc_callback not in gc.callbacks,
        "gc_thresholds_after": list(gc.get_threshold()),
        "gc_counts_after": list(_gc_counts()),
        "p50_ms": statistics.median(elapsed),
        "p95_ms": statistics.quantiles(elapsed, n=20, method="inclusive")[-1],
        "max_ms": max(elapsed),
        "validation_errors": validation_errors,
        "rows": rows,
    }

    output = Path("artifacts/research/exp21_exp19_tail_temporal_reconciliation.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({
        key: result[key]
        for key in (
            "status",
            "target_commit",
            "workload_id",
            "workload_definition_hash",
            "n",
            "tail_indices",
            "tail_count",
            "tail_indices_reference",
            "tails_match_reference",
            "gc_event_laps_canonical",
            "gc_event_laps_acyclic",
            "gc_event_laps_reachable",
            "gc_event_count_total",
            "p50_ms",
            "p95_ms",
            "max_ms",
            "validation_errors",
        )
    }, indent=2, sort_keys=True))
    for row in tail_rows:
        print("TAIL", json.dumps(row, sort_keys=True))


if __name__ == "__main__":
    main()
