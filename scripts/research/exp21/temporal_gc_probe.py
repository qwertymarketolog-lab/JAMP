"""Read-only temporal GC probe for the canonical EXP-21 workload.

This is research instrumentation only. It does not modify JAMP runtime/core
code, GC thresholds, enablement, or collection policy. The probe installs a
temporary gc.callbacks observer and records events whose monotonic timestamps
fall inside each is_acyclic() measurement boundary.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

EXPERIMENT_ID = "EXP-21-TEMPORAL-GC-PROBE-V1"
WORKLOAD_SPEC_ID = "EXP-21-PHASE0-G4-CANONICAL-V1"
WORKLOAD_DEFINITION_HASH = (
    "f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
)
FROZEN_CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
DEFAULT_LAPS = 40
DEFAULT_SEED = 2140
ARTIFACT = Path("artifacts/research/exp21_temporal_gc_probe.json")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _canonical_workload() -> ObservationAdjacencyGraph:
    edges = [
        ObservationRelation(str(i), str(i + 1), "adjacent", {})
        for i in range(10_000)
    ]
    edges.extend(
        ObservationRelation(str(i), str(i + 10_000), "adjacent", {})
        for i in range(10_000)
    )
    return ObservationAdjacencyGraph(tuple(edges))


def _cpu_model() -> str | None:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        return None
    return None


def _affinity() -> list[int] | None:
    getter = getattr(os, "sched_getaffinity", None)
    return sorted(getter(0)) if getter else None


def run(target_commit: str, laps: int, seed: int) -> dict[str, Any]:
    errors: list[str] = []
    actual_commit = _git("rev-parse", "HEAD")
    core_blob = _git("hash-object", "src/jamp/run.py")
    if not target_commit:
        errors.append("target_commit_missing")
    if target_commit != actual_commit:
        errors.append("target_commit_mismatch")
    if core_blob != FROZEN_CORE_BLOB:
        errors.append("frozen_core_blob_mismatch")
    if laps < 1:
        errors.append("laps_invalid")

    graph = _canonical_workload()
    if len(graph._edges) != 20_000:
        errors.append("workload_edge_count_mismatch")
    if len(graph._idx_to_node) != 20_000:
        errors.append("workload_node_count_mismatch")

    events: list[dict[str, Any]] = []
    previous_callbacks = list(gc.callbacks)
    gc_enabled_before = gc.isenabled()
    thresholds_before = gc.get_threshold()
    counts_before = gc.get_count()

    def callback(phase: str, info: dict[str, Any]) -> None:
        events.append(
            {
                "t_ns": time.perf_counter_ns(),
                "phase": phase,
                "generation": info.get("generation"),
                "collected": info.get("collected"),
                "uncollectable": info.get("uncollectable"),
            }
        )

    gc.callbacks.append(callback)
    observations: list[dict[str, Any]] = []
    try:
        for i in range(laps):
            before_events = len(events)
            start_ns = time.perf_counter_ns()
            cpu_start_ns = time.process_time_ns()
            acyclic = graph.is_acyclic()
            end_ns = time.perf_counter_ns()
            cpu_end_ns = time.process_time_ns()

            reachable = graph.reachable("0")
            lap_events = [
                e for e in events[before_events:] if start_ns <= e["t_ns"] <= end_ns
            ]
            observations.append(
                {
                    "index": i,
                    "acyclic_start_ns": start_ns,
                    "acyclic_end_ns": end_ns,
                    "acyclic_ms": (end_ns - start_ns) / 1_000_000.0,
                    "acyclic_cpu_ms": (cpu_end_ns - cpu_start_ns) / 1_000_000.0,
                    "acyclic_wall_cpu_delta_ms": (
                        (end_ns - start_ns) - (cpu_end_ns - cpu_start_ns)
                    )
                    / 1_000_000.0,
                    "acyclic": acyclic,
                    "reachable_count": len(reachable),
                    "gc_events_inside_acyclic": lap_events,
                    "gc_event_count": len(lap_events),
                    "gc_generations_inside_acyclic": [
                        e["generation"] for e in lap_events
                    ],
                    "gc_start_generations_inside_acyclic": [
                        e["generation"] for e in lap_events if e["phase"] == "start"
                    ],
                    "gc_stop_generations_inside_acyclic": [
                        e["generation"] for e in lap_events if e["phase"] == "stop"
                    ],
                }
            )
    finally:
        gc.callbacks[:] = previous_callbacks

    gc_enabled_after = gc.isenabled()
    thresholds_after = gc.get_threshold()
    counts_after = gc.get_count()
    if gc_enabled_before != gc_enabled_after:
        errors.append("gc_enabled_state_changed")
    if thresholds_before != thresholds_after:
        errors.append("gc_thresholds_changed")
    if gc.callbacks != previous_callbacks:
        errors.append("gc_callbacks_not_restored")

    inside = [o for o in observations if o["gc_event_count"]]
    starts = [o for o in observations if o["gc_start_generations_inside_acyclic"]]
    stops = [o for o in observations if o["gc_stop_generations_inside_acyclic"]]
    tails = [o for o in observations if o["acyclic_ms"] > 15.0]

    status = "VERIFIED" if not errors else "INCONCLUSIVE"
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "target_commit": target_commit,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "experiment_seed": seed,
        "n_laps": laps,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runner": {
            "name": os.environ.get("RUNNER_NAME", ""),
            "os": platform.platform(),
            "arch": platform.machine(),
            "kernel": platform.release(),
            "python": platform.python_version(),
            "cpu_model": _cpu_model(),
            "cpu_count_visible": os.cpu_count(),
            "cpu_affinity": _affinity(),
        },
        "gc_observer_contract": {
            "policy_changed": False,
            "gc_enabled_before": gc_enabled_before,
            "gc_enabled_after": gc_enabled_after,
            "thresholds_before": thresholds_before,
            "thresholds_after": thresholds_after,
            "counts_before": counts_before,
            "counts_after": counts_after,
            "counts_reset": False,
            "callbacks_restored": gc.callbacks == previous_callbacks,
            "clock": "time.perf_counter_ns",
            "event_scope": "events with t_ns inside [acyclic_start_ns, acyclic_end_ns]",
        },
        "observations": observations,
        "summary": {
            "tail_indices_wall_gt_15ms": [o["index"] for o in tails],
            "laps_with_gc_event_inside_acyclic": [o["index"] for o in inside],
            "laps_with_gc_start_inside_acyclic": [o["index"] for o in starts],
            "laps_with_gc_stop_inside_acyclic": [o["index"] for o in stops],
            "gc_event_count_inside_acyclic_total": sum(
                o["gc_event_count"] for o in observations
            ),
        },
        "validation_errors": errors,
        "status": status,
        "frozen_core_blob": core_blob,
        "interpretation": {
            "observed": [
                "per-lap is_acyclic monotonic boundaries",
                "gc callback start/stop events inside or outside those boundaries",
                "per-lap wall/cpu timing",
            ],
            "verified": [
                "exact target commit" if "target_commit_mismatch" not in errors else "none",
                "Frozen Core identity" if core_blob == FROZEN_CORE_BLOB else "none",
                "canonical workload identity" if not any(
                    e.endswith("mismatch") for e in errors
                ) else "none",
            ],
            "inferred": [],
            "unknown": [
                "whether observed GC events cause latency tails",
                "whether callback instrumentation changes absolute timing",
                "whether events outside is_acyclic explain tails",
            ],
        },
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-commit", required=True)
    parser.add_argument("--laps", type=int, default=DEFAULT_LAPS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    artifact = run(args.target_commit, args.laps, args.seed)
    print(json.dumps(artifact, indent=2, sort_keys=True))
    return 0 if artifact["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
