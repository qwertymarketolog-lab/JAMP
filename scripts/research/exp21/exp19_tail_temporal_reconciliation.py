"""EXP-21 exact EXP-19 tail temporal reconciliation.

The workload and measurement boundary are executed from TARGET_COMMIT itself.
Only this observer is materialized from the workflow revision. The observer uses
a preallocated event buffer so its callback does not append dict/list objects
during the measured region.
"""

from __future__ import annotations

import contextlib
import gc
import hashlib
import json
import platform
import statistics
import subprocess
import time
from array import array
from pathlib import Path
from unittest.mock import patch

from research.exp19.adjacency_graph import ObservationAdjacencyGraph

TARGET_COMMIT = "8c6b6a40f019d727a1ef630975a2691a390affd6"
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
REFERENCE_TAILS = [2, 15, 22, 35]
N = 40
CONTRACT_MS = 15.0
WORKLOAD_ID = "EXP-19-CANONICAL-G4-TAIL-TRIGGER-V1"
REAL_PERF_NS = time.perf_counter_ns
REAL_CPU_NS = time.process_time_ns
MAX_GC_EVENTS = 20_000

GC_TS = array("q", [0]) * MAX_GC_EVENTS
GC_GEN = array("b", [0]) * MAX_GC_EVENTS
GC_PHASE = array("b", [0]) * MAX_GC_EVENTS
GC_EVENT_COUNT = 0


def _gc_callback(phase: str, info: dict[str, int]) -> None:
    global GC_EVENT_COUNT
    index = GC_EVENT_COUNT
    if index >= MAX_GC_EVENTS:
        return
    GC_TS[index] = REAL_PERF_NS()
    GC_GEN[index] = int(info.get("generation", -1))
    GC_PHASE[index] = 1 if phase == "start" else 2
    GC_EVENT_COUNT = index + 1


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _gc_counts() -> tuple[int, int, int]:
    return tuple(int(item["collections"]) for item in gc.get_stats())


def _relation_graph(edges: list[tuple[str, str]]) -> ObservationAdjacencyGraph:
    from research.exp19.observation_relation import ObservationRelation

    return ObservationAdjacencyGraph(
        tuple(ObservationRelation(source, target, "adjacent", {}) for source, target in edges)
    )


def _canonical_g4() -> None:
    edges = [(str(i), str(i + 1)) for i in range(10_000)]
    edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
    graph = _relation_graph(edges)
    assert graph.is_acyclic() is True
    graph.reachable("0")


def _events(
    start_index: int,
    end_index: int,
    start_ns: int,
    end_ns: int,
) -> list[dict[str, int | str]]:
    result: list[dict[str, int | str]] = []
    for index in range(start_index, end_index):
        timestamp = int(GC_TS[index])
        if start_ns <= timestamp <= end_ns:
            result.append(
                {
                    "ts_ns": timestamp,
                    "generation": int(GC_GEN[index]),
                    "phase": "start" if GC_PHASE[index] == 1 else "stop",
                }
            )
    return result


def _workload_definition_hash() -> str:
    payload = (
        "edges=[(str(i),str(i+1)) for i in range(10000)];"
        "edges.extend((str(i),str(i+10000)) for i in range(10000));"
        "operations=is_acyclic(),reachable('0')"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    validation_errors: list[str] = []

    if _git("rev-parse", "HEAD") != TARGET_COMMIT:
        validation_errors.append("target_commit_mismatch")

    frozen_blob = _git("hash-object", "src/jamp/run.py")
    if frozen_blob != FROZEN_CORE_BLOB:
        validation_errors.append("frozen_core_blob_mismatch")

    source_blobs = {}
    for path in (
        "research/exp19/adjacency_graph.py",
        "research/exp19/observation_relation.py",
        "tests/research/exp19/test_adjacency_graph.py",
        "tests/research/exp19/ci_tail_trigger_probe.py",
    ):
        source_blobs[path] = _git("rev-parse", f"HEAD:{path}")

    rows: list[dict[str, object]] = []
    callback_installed = False
    original_acyclic = ObservationAdjacencyGraph.is_acyclic
    original_reachable = ObservationAdjacencyGraph.reachable

    try:
        gc.callbacks.append(_gc_callback)
        callback_installed = True

        for index in range(N):
            gc_before = _gc_counts()
            event_start_index = GC_EVENT_COUNT
            lap: dict[str, int] = {}

            def traced_acyclic(
                self: ObservationAdjacencyGraph,
                lap: dict[str, int] = lap,
            ) -> bool:
                lap["acyclic_start_ns"] = REAL_PERF_NS()
                try:
                    return original_acyclic(self)
                finally:
                    lap["acyclic_end_ns"] = REAL_PERF_NS()
                    lap["acyclic_ns"] = (
                        lap["acyclic_end_ns"] - lap["acyclic_start_ns"]
                    )

            def traced_reachable(
                self: ObservationAdjacencyGraph,
                start_id: str,
                lap: dict[str, int] = lap,
            ) -> frozenset[str]:
                lap["reachable_start_ns"] = REAL_PERF_NS()
                try:
                    return original_reachable(self, start_id)
                finally:
                    lap["reachable_end_ns"] = REAL_PERF_NS()
                    lap["reachable_ns"] = (
                        lap["reachable_end_ns"] - lap["reachable_start_ns"]
                    )

            wall_start_ns = REAL_PERF_NS()
            cpu_start_ns = REAL_CPU_NS()
            with (
                patch.object(
                    ObservationAdjacencyGraph, "is_acyclic", traced_acyclic
                ),
                patch.object(
                    ObservationAdjacencyGraph, "reachable", traced_reachable
                ),
                contextlib.suppress(AssertionError),
            ):
                _canonical_g4()
            wall_end_ns = REAL_PERF_NS()
            cpu_end_ns = REAL_CPU_NS()
            event_end_index = GC_EVENT_COUNT

            gc_after = _gc_counts()
            gc_delta = tuple(
                after - before
                for after, before in zip(gc_after, gc_before, strict=True)
            )

            acyclic_events = _events(
                event_start_index,
                event_end_index,
                lap["acyclic_start_ns"],
                lap["acyclic_end_ns"],
            )
            reachable_events = _events(
                event_start_index,
                event_end_index,
                lap["reachable_start_ns"],
                lap["reachable_end_ns"],
            )
            canonical_events = _events(
                event_start_index,
                event_end_index,
                wall_start_ns,
                wall_end_ns,
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
                    "wall_call_ms": (wall_end_ns - wall_start_ns) / 1_000_000,
                    "cpu_call_ms": (cpu_end_ns - cpu_start_ns) / 1_000_000,
                    "wall_cpu_delta_ms": (
                        (wall_end_ns - wall_start_ns)
                        - (cpu_end_ns - cpu_start_ns)
                    )
                    / 1_000_000,
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
                gc.callbacks.remove(_gc_callback)

    elapsed = [float(row["canonical_elapsed_ms"]) for row in rows]
    tails = [
        int(row["i"])
        for row in rows
        if float(row["canonical_elapsed_ms"]) > CONTRACT_MS
    ]

    reference_rows = {
        index: next(row for row in rows if int(row["i"]) == index)
        for index in REFERENCE_TAILS
    }

    result = {
        "status": "VERIFIED" if not validation_errors else "FAILED_VALIDATION",
        "target_commit": TARGET_COMMIT,
        "frozen_core_blob": frozen_blob,
        "workload_id": WORKLOAD_ID,
        "workload_definition_hash": _workload_definition_hash(),
        "n": len(rows),
        "contract_ms": CONTRACT_MS,
        "measurement_boundary": {
            "outer": "wall_start/cpu_start -> canonical_g4() -> wall_end/cpu_end",
            "acyclic": "inside ObservationAdjacencyGraph.is_acyclic",
            "reachable": "inside ObservationAdjacencyGraph.reachable",
            "canonical_elapsed": "acyclic + reachable",
            "observer": "gc.callbacks only; no threshold/enablement/policy change",
        },
        "reference_tail_indices": REFERENCE_TAILS,
        "observed_tail_indices": tails,
        "reference_indices_that_remain_tails": [
            index for index in REFERENCE_TAILS if index in tails
        ],
        "reference_rows": reference_rows,
        "gc_event_laps_canonical": [
            int(row["i"]) for row in rows if row["gc_events_in_canonical"]
        ],
        "gc_event_laps_acyclic": [
            int(row["i"]) for row in rows if row["gc_events_in_acyclic"]
        ],
        "gc_event_laps_reachable": [
            int(row["i"]) for row in rows if row["gc_events_in_reachable"]
        ],
        "gc_event_count_total": GC_EVENT_COUNT,
        "gc_enabled_after": gc.isenabled(),
        "gc_callbacks_restored": _gc_callback not in gc.callbacks,
        "gc_thresholds_after": list(gc.get_threshold()),
        "p50_ms": statistics.median(elapsed),
        "p95_ms": statistics.quantiles(elapsed, n=20, method="inclusive")[-1],
        "max_ms": max(elapsed),
        "source_blobs_at_target": source_blobs,
        "runner": {
            "os": platform.platform(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "cpu_count": __import__("os").cpu_count(),
        },
        "validation_errors": validation_errors,
        "rows": rows,
    }

    output = Path(
        "artifacts/research/exp21_exp19_tail_temporal_reconciliation.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        key: result[key]
        for key in (
            "status",
            "target_commit",
            "frozen_core_blob",
            "workload_id",
            "workload_definition_hash",
            "n",
            "reference_tail_indices",
            "observed_tail_indices",
            "reference_indices_that_remain_tails",
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
    for index in REFERENCE_TAILS:
        print("REFERENCE_ROW", json.dumps(reference_rows[index], sort_keys=True))
    return 0 if result["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
