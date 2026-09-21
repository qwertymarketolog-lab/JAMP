"""Research-only Allocation Profile for the canonical EXP-21 G4 workload.

Scope:
- graph construction is untimed;
- only g.is_acyclic() and g.reachable("0") are profiled;
- no JAMP core/runtime code is modified;
- allocation measurements are descriptive profiling evidence, not causal
  wall-clock proof.

The profiler itself adds measurement overhead. Peak memory and allocation
frames therefore must not be interpreted as an isolated causal explanation
of the G4 latency contract.
"""

from __future__ import annotations

import gc
import hashlib
import json
import os
import platform
import subprocess
import sys
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

WORKLOAD_SPEC_ID = "EXP-21-PHASE2-ALLOCATION-PROFILE-G4-V1"

CANONICAL_WORKLOAD_DEFINITION = """from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

edges = [(str(i), str(i + 1)) for i in range(10_000)]
edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
relations = tuple(
    ObservationRelation(source, target, "adjacent", {}) for source, target in edges
)
g = ObservationAdjacencyGraph(relations)

_ = g.is_acyclic()
_ = g.reachable("0")
"""

WORKLOAD_DEFINITION_HASH = hashlib.sha256(
    CANONICAL_WORKLOAD_DEFINITION.encode("utf-8")
).hexdigest()

OUTPUT = Path("artifacts/research/exp_alloc_profile_results.json")


def resolve_target_commit() -> str:
    env_sha = os.getenv("TARGET_COMMIT", "").strip()
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()

    if env_sha:
        if len(env_sha) != 40 or any(
            char not in "0123456789abcdefABCDEF" for char in env_sha
        ):
            raise RuntimeError("TARGET_COMMIT must be a 40-character hexadecimal SHA")
        if actual != env_sha:
            raise RuntimeError(
                f"TARGET_COMMIT mismatch: expected {env_sha}, actual {actual}"
            )
        return env_sha

    if len(actual) != 40:
        raise RuntimeError("git rev-parse HEAD returned an invalid SHA")
    return actual


def build_canonical_graph() -> ObservationAdjacencyGraph:
    edges = [(str(i), str(i + 1)) for i in range(10_000)]
    edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
    relations = tuple(
        ObservationRelation(source, target, "adjacent", {}) for source, target in edges
    )
    return ObservationAdjacencyGraph(relations)


def target(graph: ObservationAdjacencyGraph) -> None:
    if graph.is_acyclic() is not True:
        raise AssertionError("fixed G4 graph must be acyclic")
    graph.reachable("0")


def main() -> int:
    # Untimed setup and neutral GC stabilization.
    graph = build_canonical_graph()
    gc.enable()
    gc.collect(2)

    # tracemalloc is started before the profiling window. The profiler's own
    # bookkeeping is measurement overhead and is explicitly not causal proof.
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()
    blocks_before = sys.getallocatedblocks()
    objects_before = len(gc.get_objects())

    target(graph)

    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    blocks_after = sys.getallocatedblocks()
    objects_after = len(gc.get_objects())

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    top_frames = []
    for stat in snapshot_after.compare_to(snapshot_before, "lineno")[:20]:
        if stat.size_diff <= 0 and stat.count_diff <= 0:
            continue
        frame = stat.traceback[0]
        top_frames.append(
            {
                "file": str(Path(frame.filename).as_posix()),
                "line": frame.lineno,
                "size_diff_bytes": stat.size_diff,
                "count_diff": stat.count_diff,
            }
        )

    top_frame = top_frames[0] if top_frames else None

    payload = {
        "experiment": "EXP-21-PHASE2-ALLOCATION-PROFILE",
        "status": "PROFILED",
        "target_commit": resolve_target_commit(),
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "workload": {
            "edge_count": 20_000,
            "chain_edges": 10_000,
            "offset_edges": 10_000,
            "measured_operations": ["g.is_acyclic()", 'g.reachable("0")'],
        },
        "alloc_metrics": {
            "delta_blocks": blocks_after - blocks_before,
            "peak_memory_bytes": peak_bytes,
            "current_memory_bytes": current_bytes,
            "objects_count_delta": objects_after - objects_before,
            "top_frame": top_frame,
            "top_frames": top_frames,
        },
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "frozen_core_delta_zero": True,
        "epistemic_boundary": {
            "wall_clock_causality": "NOT_ESTABLISHED",
            "profiler_overhead": "PRESENT",
            "interpretation": (
                "Allocation metrics identify observed memory/allocation activity "
                "inside the profiled window; they do not by themselves establish "
                "that allocation activity causes the G4 wall-clock delay."
            ),
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(json.dumps({
        "artifact": str(OUTPUT),
        "target_commit": payload["target_commit"],
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "delta_blocks": payload["alloc_metrics"]["delta_blocks"],
        "peak_memory_bytes": payload["alloc_metrics"]["peak_memory_bytes"],
        "objects_count_delta": payload["alloc_metrics"]["objects_count_delta"],
        "top_frame": top_frame,
        "frozen_core_delta_zero": True,
    }, indent=2, sort_keys=True))
    print("artifact_sha256:")
    subprocess.run(["sha256sum", str(OUTPUT)], check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
