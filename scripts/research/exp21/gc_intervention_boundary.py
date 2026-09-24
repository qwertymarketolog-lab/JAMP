"""EXP-21 GC intervention boundary: exact EXP-19 workload, paired N=40.

CONTROL keeps normal GC enabled. INTERVENTION disables cyclic GC only for the
exact measured EXP-19 operation boundary, then restores the prior GC state.
Frozen Core and workload are untouched.
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
from pathlib import Path
from unittest.mock import patch

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from tests.research.exp19.test_adjacency_graph import (
    test_g4_large_graph_is_linear_scale as canonical_g4,
)

TARGET_COMMIT = "8c6b6a40f019d727a1ef630975a2691a390affd6"
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
WORKLOAD_ID = "EXP-19-CANONICAL-G4-TAIL-TRIGGER-V1"
WORKLOAD_HASH = "f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
N = 40
THRESHOLD_MS = 15.0
REAL_PERF = time.perf_counter
REAL_CPU = time.process_time


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def gc_counts() -> tuple[int, int, int]:
    return tuple(int(x["collections"]) for x in gc.get_stats())


def run_condition(intervention: bool, lap_index: int, order_index: int) -> dict:
    before = gc_counts()
    threshold_before = list(gc.get_threshold())
    enabled_before = gc.isenabled()
    lap: dict[str, int] = {}
    original_acyclic = ObservationAdjacencyGraph.is_acyclic
    original_reachable = ObservationAdjacencyGraph.reachable

    def traced_acyclic(self: ObservationAdjacencyGraph) -> bool:
        start = REAL_PERF()
        try:
            return original_acyclic(self)
        finally:
            lap["acyclic_ns"] = int((REAL_PERF() - start) * 1_000_000_000)

    def traced_reachable(
        self: ObservationAdjacencyGraph, start_id: str
    ) -> frozenset[str]:
        start = REAL_PERF()
        try:
            return original_reachable(self, start_id)
        finally:
            lap["reachable_ns"] = int((REAL_PERF() - start) * 1_000_000_000)

    if intervention:
        gc.disable()
    try:
        wall_start = REAL_PERF()
        cpu_start = REAL_CPU()
        with (
            patch.object(ObservationAdjacencyGraph, "is_acyclic", traced_acyclic),
            patch.object(ObservationAdjacencyGraph, "reachable", traced_reachable),
            contextlib.suppress(AssertionError),
        ):
            canonical_g4()
        wall_end = REAL_PERF()
        cpu_end = REAL_CPU()
    finally:
        enabled_during = gc.isenabled()
        if intervention and enabled_before:
            gc.enable()
        elif intervention and not enabled_before:
            gc.disable()

    after = gc_counts()
    threshold_after = list(gc.get_threshold())
    if "acyclic_ns" not in lap or "reachable_ns" not in lap:
        raise RuntimeError("missing_component_timing")

    return {
        "condition": "gc_intervention" if intervention else "control",
        "lap": lap_index,
        "order_index": order_index,
        "gc_enabled_before": enabled_before,
        "gc_enabled_during": enabled_during,
        "gc_enabled_after": gc.isenabled(),
        "gc_thresholds_before": threshold_before,
        "gc_thresholds_after": threshold_after,
        "gc_gen0": after[0] - before[0],
        "gc_gen1": after[1] - before[1],
        "gc_gen2": after[2] - before[2],
        "gc_total_events": sum(after[i] - before[i] for i in range(3)),
        "acyclic_ms": lap["acyclic_ns"] / 1_000_000,
        "reachable_ms": lap["reachable_ns"] / 1_000_000,
        "canonical_elapsed_ms": (
            lap["acyclic_ns"] + lap["reachable_ns"]
        ) / 1_000_000,
        "wall_call_ms": (wall_end - wall_start) * 1000,
        "cpu_call_ms": (cpu_end - cpu_start) * 1000,
        "wall_cpu_delta_ms": ((wall_end - wall_start) - (cpu_end - cpu_start)) * 1000,
    }


def main() -> int:
    errors: list[str] = []
    if git("rev-parse", "HEAD") != TARGET_COMMIT:
        errors.append("target_commit_mismatch")
    frozen = git("hash-object", "src/jamp/run.py")
    if frozen != FROZEN_CORE_BLOB:
        errors.append("frozen_core_blob_mismatch")

    rows: list[dict] = []
    for lap in range(1, N + 1):
        # Normalize cyclic-GC state outside the measured boundary.
        gc.collect()
        first_intervention = lap % 2 == 0
        first = run_condition(first_intervention, lap, 0)
        gc.collect()
        second = run_condition(not first_intervention, lap, 1)
        rows.extend([first, second])
        if not first["gc_enabled_after"] or not second["gc_enabled_after"]:
            errors.append(f"gc_not_restored_lap_{lap}")

    by_lap = {i: {} for i in range(1, N + 1)}
    for row in rows:
        by_lap[row["lap"]][row["condition"]] = row

    paired = []
    for lap in range(1, N + 1):
        c = by_lap[lap]["control"]
        x = by_lap[lap]["gc_intervention"]
        paired.append(
            {
                "lap": lap,
                "control_ms": c["canonical_elapsed_ms"],
                "intervention_ms": x["canonical_elapsed_ms"],
                "delta_ms": x["canonical_elapsed_ms"] - c["canonical_elapsed_ms"],
                "control_acyclic_ms": c["acyclic_ms"],
                "intervention_acyclic_ms": x["acyclic_ms"],
                "delta_acyclic_ms": x["acyclic_ms"] - c["acyclic_ms"],
                "control_reachable_ms": c["reachable_ms"],
                "intervention_reachable_ms": x["reachable_ms"],
                "delta_reachable_ms": x["reachable_ms"] - c["reachable_ms"],
                "control_gen0": c["gc_gen0"],
                "control_gen1": c["gc_gen1"],
                "control_gen2": c["gc_gen2"],
                "intervention_gen0": x["gc_gen0"],
                "intervention_gen1": x["gc_gen1"],
                "intervention_gen2": x["gc_gen2"],
                "control_wall_cpu_delta_ms": c["wall_cpu_delta_ms"],
                "intervention_wall_cpu_delta_ms": x["wall_cpu_delta_ms"],
            }
        )

    control = [p["control_ms"] for p in paired]
    intervention = [p["intervention_ms"] for p in paired]
    deltas = [p["delta_ms"] for p in paired]
    result = {
        "status": "VERIFIED" if not errors else "FAILED_VALIDATION",
        "target_commit": TARGET_COMMIT,
        "frozen_core_blob": frozen,
        "workload_id": WORKLOAD_ID,
        "workload_definition_hash": WORKLOAD_HASH,
        "n": N,
        "contract_ms": THRESHOLD_MS,
        "measurement_boundary": "wall_start/cpu_start -> canonical_g4() -> wall_end/cpu_end",
        "conditions": "CONTROL=normal GC; INTERVENTION=gc.disable() only inside measured boundary; prior state restored",
        "order": "intervention first on even laps, control first on odd laps",
        "intervention_scope": "GC policy only; workload and Frozen Core unchanged",
        "paired_summary": {
            "control_p50_ms": statistics.median(control),
            "intervention_p50_ms": statistics.median(intervention),
            "control_p95_ms": statistics.quantiles(control, n=20, method="inclusive")[-1],
            "intervention_p95_ms": statistics.quantiles(intervention, n=20, method="inclusive")[-1],
            "control_tails": [i + 1 for i, x in enumerate(control) if x > THRESHOLD_MS],
            "intervention_tails": [i + 1 for i, x in enumerate(intervention) if x > THRESHOLD_MS],
            "median_delta_intervention_minus_control_ms": statistics.median(deltas),
            "mean_delta_intervention_minus_control_ms": statistics.fmean(deltas),
            "positive_pairs": sum(x > 0 for x in deltas),
            "negative_pairs": sum(x < 0 for x in deltas),
            "zero_pairs": sum(x == 0 for x in deltas),
            "max_abs_delta_ms": max(abs(x) for x in deltas),
        },
        "validation_errors": errors,
        "rows": rows,
        "paired_rows": paired,
        "runner": {
            "os": platform.platform(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "cpu_count": __import__("os").cpu_count(),
        },
        "interpretation": {
            "observed": ["paired per-lap wall/cpu/GC evidence"],
            "verified": ["target identity", "Frozen Core identity", "N=40", "intervention restoration"],
            "inferred": [],
            "unknown": ["causal attribution of tails until paired intervention evidence is analyzed"],
        },
    }
    out = Path("artifacts/research/exp21_gc_intervention_boundary.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["paired_summary"], indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
